"""Load one explicit dotenv file without overriding terminal or Docker settings."""

import os
from pathlib import Path

from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PATH_KEYS = (
    "PILLBOX_DB",
    "PILLBOX_AUTH_FILE",
    "MQTT_CA_FILE",
    "MQTT_CERT_FILE",
    "MQTT_KEY_FILE",
)
BOOL_KEYS = (
    "PILLBOX_LOAD_ENV",
    "PILLBOX_MQTT_AUTOSTART",
    "PILLBOX_HTTP_INGEST",
    "PILLBOX_REQUIRE_REGISTERED_DEVICES",
    "MQTT_TLS",
)


def project_path(value, root=PROJECT_ROOT):
    path = Path(value).expanduser()
    return path if path.is_absolute() else Path(root) / path


def load_environment(environ=None, root=PROJECT_ROOT):
    env = os.environ if environ is None else environ
    if env.get("PILLBOX_LOAD_ENV", "1") not in ("0", "1"):
        raise ValueError("PILLBOX_LOAD_ENV must be 0 or 1")
    selected = env.get("PILLBOX_ENV_FILE")
    path = project_path(selected or "gateway/.env", root)
    if env.get("PILLBOX_LOAD_ENV", "1") == "1":
        if selected and not path.is_file():
            raise FileNotFoundError(f"Configured env file does not exist: {path}")
        if path.is_file():
            # Keep passwords containing $, # and ${...} literal, never evaluate shell code.
            for key, value in dotenv_values(
                path, encoding="utf-8-sig", interpolate=False
            ).items():
                if (
                    value is not None
                    and key not in ("PILLBOX_ENV_FILE", "PILLBOX_LOAD_ENV")
                    and (key.startswith(("PILLBOX_", "MQTT_")) or key == "PORT")
                ):
                    env.setdefault(key, value)
    if env.get("PILLBOX_MODE", "local") not in ("local", "mqtt"):
        raise ValueError("PILLBOX_MODE must be local or mqtt")
    for key in BOOL_KEYS:
        if key in env and env[key] not in ("0", "1"):
            raise ValueError(f"{key} must be 0 or 1")
    for key in ("PORT", "MQTT_PORT", "PILLBOX_SMTP_PORT"):
        if key in env:
            try:
                valid = 1 <= int(env[key]) <= 65535
            except (ValueError, TypeError):
                valid = False
            if not valid:
                raise ValueError(f"{key} must be an integer from 1 to 65535")
    for key in PATH_KEYS:
        if env.get(key):
            env[key] = str(project_path(env[key], root).resolve())
    return path if env.get("PILLBOX_LOAD_ENV", "1") == "1" and path.is_file() else None


if __name__ == "__main__":
    loaded = load_environment()
    print(f"Env file: {loaded or 'none (terminal/defaults)'}")
    for key, default in (
        ("PILLBOX_MODE", "local"),
        ("PILLBOX_DB", str(PROJECT_ROOT / "gateway/data/pillbox.db")),
        ("PILLBOX_AUTH_FILE", "not configured"),
        ("PILLBOX_BIND", "127.0.0.1"),
        ("PORT", "5000"),
        ("PILLBOX_MQTT_AUTOSTART", "0"),
        ("MQTT_HOST", "localhost"),
        ("MQTT_PORT", "1883"),
        ("MQTT_TLS", "0"),
    ):
        print(f"{key}={os.getenv(key, default)}")
