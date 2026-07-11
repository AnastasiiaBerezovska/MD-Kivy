// Receiver - forwards wireless data to the Python app
// This code receives wireless data from transmitter and sends to Python via USB serial
#include <esp_now.h>
#include <WiFi.h>

// Structure to receive data (must match transmitter)
typedef struct struct_message {
  int16_t AcX;
  int16_t AcY;
  int16_t AcZ;
} struct_message;

// Create struct instance
struct_message myData;

// Callback function executed when data is received
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  memcpy(&myData, incomingData, sizeof(myData));
  
  // Print in the exact format the Python app parses:
  // Format: "X = value | Y = value | Z = value" (all on ONE line)
  Serial.print("X = ");
  Serial.print(myData.AcX);
  Serial.print(" | Y = ");
  Serial.print(myData.AcY);
  Serial.print(" | Z = ");
  Serial.println(myData.AcZ);
}

void setup() {
  // IMPORTANT: Use 9600 baud to match Python app default
  Serial.begin(9600);
  
  // Set device as Wi-Fi Station
  WiFi.mode(WIFI_STA);
  
  // Initialize ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  
  // Register receive callback (once, in setup)
  esp_now_register_recv_cb(OnDataRecv);
  
  Serial.println("Receiver Ready - Waiting for data...");
}

void loop() {
  // Nothing to do here; the receive callback handles the data
  delay(10);
}