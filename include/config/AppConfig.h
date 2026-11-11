#pragma once

#include <stdint.h>

#if __has_include("config/Secrets.h")
#include "config/Secrets.h"
#endif

#ifndef PILLBOX_DEVICE_ID
#define PILLBOX_DEVICE_ID "PB01"
#endif
#ifndef PILLBOX_MQTT_TLS
#define PILLBOX_MQTT_TLS 0
#endif
#ifndef PILLBOX_MQTT_USER
#define PILLBOX_MQTT_USER ""
#endif
#ifndef PILLBOX_MQTT_PASSWORD
#define PILLBOX_MQTT_PASSWORD ""
#endif
#if PILLBOX_MQTT_TLS && !defined(PILLBOX_MQTT_CA_CERT)
#error "TLS requires PILLBOX_MQTT_CA_CERT with the trusted broker CA PEM"
#endif

constexpr bool validDeviceId(const char* id) {
    return !*id || (((*id>='A' && *id<='Z') || (*id>='a' && *id<='z') ||
        (*id>='0' && *id<='9') || *id=='_' || *id=='-') && validDeviceId(id+1));
}

namespace AppConfig {
constexpr char DEVICE_ID[] = PILLBOX_DEVICE_ID;
static_assert(sizeof(DEVICE_ID)>1 && sizeof(DEVICE_ID)<=33 && validDeviceId(DEVICE_ID), "Use a device ID of 1-32 letters, digits, underscores or hyphens");
#if defined(PILLBOX_MQTT_HOST)
constexpr char MQTT_HOST[] = PILLBOX_MQTT_HOST;
#elif defined(PILLBOX_SIMULATION)
constexpr char MQTT_HOST[] = "test.mosquitto.org";
#else
constexpr char MQTT_HOST[] = "192.168.1.100";
#endif
#ifdef PILLBOX_MQTT_PORT
constexpr uint16_t MQTT_PORT = PILLBOX_MQTT_PORT;
#elif PILLBOX_MQTT_TLS
constexpr uint16_t MQTT_PORT = 8883;
#else
constexpr uint16_t MQTT_PORT = 1883;
#endif
#ifdef PILLBOX_NTP_SERVER
constexpr char NTP_SERVER[] = PILLBOX_NTP_SERVER;
#else
constexpr char NTP_SERVER[] = "pool.ntp.org";
#endif
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t MQTT_RETRY_MS = 2000;
constexpr uint16_t MQTT_KEEPALIVE_SECONDS = 60;
constexpr uint32_t HEARTBEAT_MS = 5000;
constexpr uint32_t ENVIRONMENT_PUBLISH_MS = 2000;
constexpr uint32_t DHT_READ_MS = 2000;
constexpr uint8_t OFFLINE_QUEUE_CAPACITY = 16;
constexpr float DEMO_MAX_TEMPERATURE_C = 30.0f;
constexpr float DEMO_MAX_HUMIDITY_PERCENT = 70.0f;
constexpr float ENVIRONMENT_HYSTERESIS = 2.0f;
constexpr uint8_t ENVIRONMENT_CONFIRM_SAMPLES = 3;
}
