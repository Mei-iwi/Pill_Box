import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gateway.config import load_environment


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "gateway").mkdir()
        self.path = self.root / "gateway/.env"

    def tearDown(self):
        self.temp.cleanup()

    def write(self, text):
        self.path.write_text(text, encoding="utf-8-sig")

    def test_file_defaults_and_terminal_docker_precedence(self):
        self.write("PORT=5001\nMQTT_HOST=file-broker\nPILLBOX_MODE=local\n")
        env = {"MQTT_HOST": "docker-broker"}
        self.assertEqual(load_environment(env, self.root), self.path)
        self.assertEqual(env["PORT"], "5001")
        self.assertEqual(env["MQTT_HOST"], "docker-broker")

    def test_paths_resolve_against_project_not_working_directory(self):
        self.write(
            "PILLBOX_DB=gateway/data/one.db\nPILLBOX_AUTH_FILE=gateway/users.json\nMQTT_CA_FILE=certs/ca.crt\n"
        )
        env = {}
        load_environment(env, self.root)
        self.assertEqual(env["PILLBOX_DB"], str(self.root / "gateway/data/one.db"))
        self.assertEqual(
            env["PILLBOX_AUTH_FILE"], str(self.root / "gateway/users.json")
        )
        self.assertEqual(env["MQTT_CA_FILE"], str(self.root / "certs/ca.crt"))

    def test_password_special_characters_are_literal(self):
        self.write('MQTT_PASSWORD="abc#${HOME}$ secret"\nMQTT_USER=test\n')
        env = {}
        load_environment(env, self.root)
        self.assertEqual(env["MQTT_PASSWORD"], "abc#${HOME}$ secret")

    def test_selected_profile_and_disabled_file_loading(self):
        profile = self.root / "gateway/.env.wokwi"
        profile.write_text("PILLBOX_MODE=mqtt\nMQTT_PORT=1883\n", encoding="utf-8")
        env = {"PILLBOX_ENV_FILE": "gateway/.env.wokwi"}
        self.assertEqual(load_environment(env, self.root), profile)
        self.assertEqual(env["PILLBOX_MODE"], "mqtt")
        env = {"PILLBOX_ENV_FILE": "missing.env", "PILLBOX_LOAD_ENV": "0"}
        self.assertIsNone(load_environment(env, self.root))
        self.assertNotIn("PILLBOX_MODE", env)

    def test_missing_explicit_file_fails_but_default_is_optional(self):
        self.assertIsNone(load_environment({}, self.root))
        with self.assertRaises(FileNotFoundError):
            load_environment({"PILLBOX_ENV_FILE": "missing.env"}, self.root)

    def test_invalid_ports_flags_and_mode_fail_without_echoing_secrets(self):
        for key, value in [
            ("PORT", "0"),
            ("MQTT_PORT", "65536"),
            ("PILLBOX_SMTP_PORT", "not-a-port"),
            ("MQTT_TLS", "yes"),
            ("PILLBOX_MODE", "other"),
        ]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError) as error:
                    load_environment(
                        {key: value, "MQTT_PASSWORD": "private-secret"}, self.root
                    )
                self.assertIn(key, str(error.exception))
                self.assertNotIn("private-secret", str(error.exception))

    def test_no_import_side_effects_or_arbitrary_shell_settings(self):
        self.write(
            "PATH=bad\nHOME=bad\nPILLBOX_ENV_FILE=recursive.env\nPILLBOX_LOAD_ENV=0\nPORT=5001\n"
        )
        env = {}
        before = dict(os.environ)
        load_environment(env, self.root)
        self.assertEqual(dict(os.environ), before)
        for key in ("PATH", "HOME", "PILLBOX_ENV_FILE", "PILLBOX_LOAD_ENV"):
            self.assertNotIn(key, env)

    def test_factory_with_test_config_does_not_load_user_dotenv(self):
        from gateway.app import create_app

        with (
            patch.dict(os.environ, {"PILLBOX_MQTT_AUTOSTART": "0"}),
            patch("gateway.app.load_environment") as loader,
        ):
            create_app({"DB_PATH": str(self.root / "test.db")})
            loader.assert_not_called()

    def test_normal_factory_reads_env_before_database_and_auth(self):
        from gateway.app import create_app

        def populate():
            os.environ["PILLBOX_DB"] = str(self.root / "factory.db")
            os.environ["PILLBOX_MQTT_AUTOSTART"] = "0"

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("gateway.app.load_environment", side_effect=populate),
        ):
            app = create_app()
            self.assertEqual(app.config["DB_PATH"], str(self.root / "factory.db"))

    def test_launcher_cli_overrides_env_and_routes_without_network(self):
        from gateway.__main__ import main

        with (
            patch.dict(os.environ, {}, clear=True),
            patch(
                "sys.argv",
                ["gateway", "--mode", "mqtt", "--port", "5002", "--env-file", "my.env"],
            ),
            patch("gateway.__main__.load_environment") as loader,
            patch("gateway.app.main") as mqtt,
            patch("gateway.local_system.main") as local,
        ):
            main()
            loader.assert_called_once()
            self.assertEqual(os.environ["PORT"], "5002")
            self.assertEqual(os.environ["PILLBOX_ENV_FILE"], "my.env")
            mqtt.assert_called_once_with()
            local.assert_not_called()
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("sys.argv", ["gateway"]),
            patch("gateway.__main__.load_environment"),
            patch("gateway.local_system.main") as local,
        ):
            main()
            local.assert_called_once_with([])

    def test_local_runner_uses_configured_auth_port_and_cli_database(self):
        from gateway.local_system import main
        from gateway.db import connect, init_db

        database = self.root / "local.db"
        init_db(database)
        with connect(database) as db:
            db.execute(
                "INSERT INTO app_settings VALUES ('dataset_profile','care-training-v1')"
            )
        app = Mock()
        app.extensions = {"local_fleet": Mock()}
        identities = {"token": {"role": "admin"}}
        env = {
            "PILLBOX_DB": str(self.root / "wrong.db"),
            "PORT": "5010",
            "PILLBOX_BIND": "127.0.0.1",
            "PILLBOX_AUTH_FILE": str(self.root / "custom-auth.json"),
            "PILLBOX_MQTT_AUTOSTART": "1",
        }
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gateway.local_system.load_environment"),
            patch(
                "gateway.local_system.create_accounts", return_value=identities
            ) as accounts,
            patch("gateway.local_system.create_local_app", return_value=app) as create,
        ):
            main(["--db", str(database), "--port", "5011"])
            self.assertEqual(os.environ["PILLBOX_MQTT_AUTOSTART"], "0")
            accounts.assert_called_once_with(self.root / "custom-auth.json")
            create.assert_called_once_with(database, identities)
            app.run.assert_called_once_with(
                host="127.0.0.1",
                port=5011,
                debug=False,
                use_reloader=False,
                load_dotenv=False,
            )

    def test_accounts_cli_uses_configured_file(self):
        from gateway.accounts import main

        target = self.root / "custom-accounts.json"
        with (
            patch.dict(os.environ, {"PILLBOX_AUTH_FILE": str(target)}, clear=True),
            patch("sys.argv", ["accounts", "create"]),
            patch("gateway.accounts.load_environment"),
            patch("gateway.accounts.create_accounts") as create,
        ):
            main()
            create.assert_called_once_with(str(target))

    def test_local_http_ingest_can_be_disabled_in_configuration(self):
        from gateway.local_system import create_local_app

        identities = {"a" * 24: dict(actor_id="ADMIN", role="admin", devices=[])}
        with patch.dict(
            os.environ,
            {"PILLBOX_HTTP_INGEST": "0", "PILLBOX_MQTT_AUTOSTART": "0"},
            clear=True,
        ):
            app = create_local_app(str(self.root / "http.db"), identities)
            self.assertFalse(app.config["HTTP_INGEST_ENABLED"])

    def test_checked_in_templates_load_and_local_default_is_offline(self):
        from gateway.config import PROJECT_ROOT

        for name, mode, autostart in [
            (".env.example", "local", "0"),
            (".env.local.example", "local", "0"),
            (".env.wokwi.example", "mqtt", "1"),
        ]:
            with self.subTest(profile=name):
                env = {"PILLBOX_ENV_FILE": "gateway/" + name}
                load_environment(env)
                self.assertEqual(env["PILLBOX_MODE"], mode)
                self.assertEqual(env["PILLBOX_MQTT_AUTOSTART"], autostart)
                self.assertEqual(
                    env["PILLBOX_AUTH_FILE"],
                    str(PROJECT_ROOT / "gateway/auth.local.json"),
                )
        self.assertEqual(
            (PROJECT_ROOT / "gateway/.env.example").read_bytes(),
            (PROJECT_ROOT / "gateway/.env.local.example").read_bytes(),
        )

    def test_notifications_cli_reads_db_but_never_enables_send_from_env(self):
        from gateway.notifications import main

        target = self.root / "notifications.db"
        with (
            patch.dict(
                os.environ,
                {"PILLBOX_DB": str(target), "PILLBOX_SMTP_HOST": "configured.invalid"},
                clear=True,
            ),
            patch("sys.argv", ["notifications"]),
            patch("gateway.notifications.load_environment"),
            patch("gateway.notifications.dispatch") as dispatch,
        ):
            main()
            dispatch.assert_called_once_with(target, send=False)


if __name__ == "__main__":
    unittest.main()
