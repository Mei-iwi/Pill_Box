"""Certificate-verified MQTT settings, shared by Gateway and synthetic clients."""

import os
import ssl
from pathlib import Path


def configure_mqtt(client, env=None):
    env = os.environ if env is None else env
    tls = env.get("MQTT_TLS", "0") == "1"
    user, password = env.get("MQTT_USER", ""), env.get("MQTT_PASSWORD", "")
    if bool(user) != bool(password):
        raise ValueError("MQTT_USER and MQTT_PASSWORD must both be set")
    if env.get("PILLBOX_DEPLOYMENT") == "care" and (not tls or not user):
        raise ValueError("care deployment requires MQTT_TLS=1 and MQTT credentials")
    if user:
        client.username_pw_set(user, password)
    if tls:
        ca = env.get("MQTT_CA_FILE")
        cert, key = env.get("MQTT_CERT_FILE"), env.get("MQTT_KEY_FILE")
        if bool(cert) != bool(key):
            raise ValueError("MQTT_CERT_FILE and MQTT_KEY_FILE must both be set")
        for file in (ca, cert, key):
            if file and not Path(file).is_file():
                raise ValueError("MQTT certificate file does not exist")
        context = ssl.create_default_context(cafile=ca or None)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        if cert:
            context.load_cert_chain(cert, key)
        client.tls_set_context(context)
        # No insecure toggle: hostname and CA verification stay enabled.
