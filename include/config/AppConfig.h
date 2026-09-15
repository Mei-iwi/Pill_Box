#pragma once

#include <stdint.h>

#if __has_include("config/Secrets.h")
#include "config/Secrets.h"
#endif

namespace AppConfig {
constexpr char DEVICE_ID[] = "PB01";
#ifdef PILLBOX_SIMULATION
constexpr char MQTT_HOST[] = "test.mosquitto.org";
constexpr uint16_t MQTT_PORT = 1883;
#elif defined(PILLBOX_MQTT_HOST)
constexpr char MQTT_HOST[] = PILLBOX_MQTT_HOST;
constexpr uint16_t MQTT_PORT = PILLBOX_MQTT_PORT;
#else
constexpr char MQTT_HOST[] = "192.168.1.100";
constexpr uint16_t MQTT_PORT = 1883;
#endif
constexpr uint32_t WIFI_RETRY_MS = 10000;
constexpr uint32_t MQTT_RETRY_MS = 5000;
constexpr uint32_t HEARTBEAT_MS = 20000;
constexpr uint32_t ENVIRONMENT_PUBLISH_MS = 60000;
constexpr uint32_t DHT_READ_MS = 10000;
constexpr uint8_t OFFLINE_QUEUE_CAPACITY = 16;
constexpr float DEMO_MAX_TEMPERATURE_C = 30.0f;
constexpr float DEMO_MAX_HUMIDITY_PERCENT = 70.0f;
}
