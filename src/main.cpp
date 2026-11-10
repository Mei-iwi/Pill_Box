#include "app/AppController.h"
#include <Arduino.h>

AppController app;

void setup() { app.begin(); }
void loop() { app.update(); delay(5); } // Yield CPU to Wi-Fi/MQTT and the simulator.
