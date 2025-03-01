#include "Wire.h"
#include <VL53L0X.h>
#include "esp_task_wdt.h"

#define intLED 8

VL53L0X sensor;

const float DISTANCE_THRESHOLD = 600.0;  // mm

void setup() {
  Serial.begin(115200);
  Wire.begin(6, 5);  // Specify SDA and SCL pins explicitly
  delay(500);
  Serial.println("Initializing...");

  pinMode(intLED, OUTPUT);  // Use the defined intLED pin

  // Initialize the sensor
  sensor.setTimeout(1000);

  if (!sensor.init()) {
    Serial.println("Failed to initialize sensor! Restarting...");
    while (1) {}  // Halt the program if the sensor fails to initialize
  }

  sensor.startContinuous();
  Serial.println("Sensor initialized successfully.");
}

void loop() {
  float distance;
  float elapsedTime;

  // Continuously read sensor data
  elapsedTime = millis() / 1000.0;  // Calculate elapsed time in seconds
  distance = sensor.readRangeContinuousMillimeters();

  // Only send data if the distance is below the threshold
  if (distance < DISTANCE_THRESHOLD) {
    // Send data without the word 'spacer', just time and distance
    Serial.print(elapsedTime, 3);  // Print elapsed time with 3 decimal places
    Serial.print(" ");             // Add a space separator
    Serial.println(distance);      // Print distance and move to the next line
  }

  // Optional: Add a small delay to avoid overloading the serial buffer
  //delay(100);
}