#include "communication/WifiManager.h"
#include "config/AppConfig.h"
#include <Arduino.h>
#include <WiFi.h>

#if defined(PILLBOX_SIMULATION)
#undef PILLBOX_WIFI_SSID
#undef PILLBOX_WIFI_PASSWORD
#define PILLBOX_WIFI_SSID "Wokwi-GUEST"
#define PILLBOX_WIFI_PASSWORD ""
#elif __has_include("config/Secrets.h")
#include "config/Secrets.h"
#else
#define PILLBOX_WIFI_SSID ""
#define PILLBOX_WIFI_PASSWORD ""
#endif

void WifiManager::begin() {
    WiFi.mode(WIFI_STA);
    started_ = true;
    WiFi.begin(PILLBOX_WIFI_SSID, PILLBOX_WIFI_PASSWORD);
    lastAttempt_ = millis();
}

void WifiManager::update() {
    if (!started_) return;
    if (WiFi.status() == WL_CONNECTED) return;
    if (millis() - lastAttempt_ >= AppConfig::WIFI_RETRY_MS) {
        WiFi.disconnect();
        WiFi.begin(PILLBOX_WIFI_SSID, PILLBOX_WIFI_PASSWORD);
        lastAttempt_ = millis();
    }
}

bool WifiManager::connected() const { return started_ && WiFi.status() == WL_CONNECTED; }
