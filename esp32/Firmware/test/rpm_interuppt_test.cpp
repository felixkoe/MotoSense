#include <Arduino.h>

volatile uint32_t count = 0;

void IRAM_ATTR isr() { count++; }

void setup() {
    Serial.begin(115200);
    pinMode(27, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(27), isr, FALLING);
}

void loop() {
    delay(1000);
    Serial.println(count);
}