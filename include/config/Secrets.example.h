#pragma once

// Copy to Secrets.h locally and fill in credentials. Never commit Secrets.h.
#define PILLBOX_DEVICE_ID "PB01"
#define PILLBOX_SCHEDULE_PREFIX "" // PB01: empty; provisioned PB03: "PB03_"
#define PILLBOX_WIFI_SSID "your-wifi"
#define PILLBOX_WIFI_PASSWORD "your-password"
#define PILLBOX_MQTT_HOST "test.mosquitto.org"
#define PILLBOX_MQTT_PORT 1883
#define PILLBOX_MQTT_USER ""
#define PILLBOX_MQTT_PASSWORD ""
// Private broker: set host/port/user/password, enable TLS and paste the public CA PEM.
// The hostname must match the broker certificate. Never use setInsecure().
#define PILLBOX_MQTT_TLS 0
#define PILLBOX_NTP_SERVER "pool.ntp.org" // Replace with a trusted LAN NTP server when needed.
// #define PILLBOX_MQTT_CA_CERT R"PEM(-----BEGIN CERTIFICATE-----
// ... trusted CA certificate ...
// -----END CERTIFICATE-----
// )PEM"
