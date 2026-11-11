"""Local TLS/CONNACK test endpoint. Does not claim Mosquitto ACL validation."""

import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

import paho.mqtt.client as mqtt

from gateway.mqtt_config import configure_mqtt


@unittest.skipUnless(
    shutil.which("openssl"), "OpenSSL needed for isolated TLS certificates"
)
class MqttTlsSocketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.cert = Path(cls.temp.name) / "localhost.crt"
        cls.key = Path(cls.temp.name) / "localhost.key"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-sha256",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost",
                "-keyout",
                str(cls.key),
                "-out",
                str(cls.cert),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def endpoint(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(5)
        port = listener.getsockname()[1]
        accepted = threading.Event()
        errors = []
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert, self.key)

        def serve():
            try:
                with listener:
                    conn, _ = listener.accept()
                    with context.wrap_socket(conn, server_side=True) as tls:
                        tls.settimeout(4)
                        packet = tls.recv(2048)
                        if not packet or packet[0] != 0x10:
                            raise AssertionError("expected MQTT CONNECT inside TLS")
                        tls.sendall(b"\x20\x02\x00\x00")
                        accepted.set()
                        tls.recv(1024)
            except (ssl.SSLError, ConnectionResetError):
                pass  # Expected for the negative certificate tests.
            except (OSError, AssertionError) as exc:
                errors.append(exc)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        return port, thread, accepted, errors

    def test_trusted_certificate_can_complete_mqtt_connect(self):
        port, thread, accepted, errors = self.endpoint()
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        configure_mqtt(client, {"MQTT_TLS": "1", "MQTT_CA_FILE": str(self.cert)})
        connected = threading.Event()
        client.on_connect = lambda *args: connected.set()
        client.connect("localhost", port, 10)
        client.loop_start()
        try:
            self.assertTrue(connected.wait(4))
            self.assertTrue(accepted.is_set())
        finally:
            client.disconnect()
            client.loop_stop()
            thread.join(5)
        self.assertFalse(errors)

    def test_unknown_ca_is_rejected(self):
        port, thread, accepted, errors = self.endpoint()
        client = Mock()
        configure_mqtt(client, {"MQTT_TLS": "1"})
        context = client.tls_set_context.call_args.args[0]
        with (
            socket.create_connection(("127.0.0.1", port)) as raw,
            self.assertRaises(ssl.SSLCertVerificationError),
        ):
            context.wrap_socket(raw, server_hostname="localhost")
        thread.join(5)
        self.assertFalse(accepted.is_set())
        self.assertFalse(errors)

    def test_wrong_hostname_is_rejected(self):
        port, thread, accepted, errors = self.endpoint()
        client = Mock()
        configure_mqtt(client, {"MQTT_TLS": "1", "MQTT_CA_FILE": str(self.cert)})
        context = client.tls_set_context.call_args.args[0]
        with (
            socket.create_connection(("127.0.0.1", port)) as raw,
            self.assertRaises(ssl.SSLCertVerificationError),
        ):
            context.wrap_socket(raw, server_hostname="127.0.0.1")
        thread.join(5)
        self.assertFalse(accepted.is_set())
        self.assertFalse(errors)
