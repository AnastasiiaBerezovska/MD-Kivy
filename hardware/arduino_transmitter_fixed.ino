// Transmitter 
// Flash this to the ESP32 with the MPU6050 accelerometer
#include <esp_now.h>
#include <WiFi.h>
#include <Wire.h>

// I2C address of the MPU-6050
const int MPU = 0x68;
int16_t AcX, AcY, AcZ, Tmp, GyX, GyY, GyZ;

// IMPORTANT: Replace with your RECEIVER's MAC Address
// To find it: Flash receiver code first, open Serial Monitor, and run this command:
// WiFi.macAddress() in the receiver's setup
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};  // replace with the receiver's MAC address

// Structure to send data (must match receiver)
typedef struct struct_message {
  int16_t AcX;
  int16_t AcY;
  int16_t AcZ;
} struct_message;

struct_message myData;
esp_now_peer_info_t peerInfo;

// Callback when data is sent
void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("Send Status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

void setup() {
  // Initialize I2C communication
  Wire.begin();
  
  // Initialize MPU6050
  Wire.beginTransmission(MPU);
  Wire.write(0x6B);  // PWR_MGMT_1 register
  Wire.write(0);     // Wake up MPU6050
  Wire.endTransmission(true);
  
  // Initialize Serial Monitor
  Serial.begin(115200);
  
  // Set device as Wi-Fi Station
  WiFi.mode(WIFI_STA);
  
  // Print MAC address (use this for the receiver's broadcastAddress)
  Serial.print("Transmitter MAC Address: ");
  Serial.println(WiFi.macAddress());
  
  // Init ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }
  
  // Register send callback
  esp_now_register_send_cb(OnDataSent);
  
  // Register peer
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;
  
  // Add peer
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }
  
  Serial.println("Transmitter Ready");
}

void loop() {
  // Read accelerometer data
  Wire.beginTransmission(MPU);
  Wire.write(0x3B);  // Starting register for accelerometer
  Wire.endTransmission(false);
  Wire.requestFrom(MPU, 6, true);
  
  myData.AcX = Wire.read() << 8 | Wire.read();
  myData.AcY = Wire.read() << 8 | Wire.read();
  myData.AcZ = Wire.read() << 8 | Wire.read();
  
  // Send data via ESP-NOW
  esp_err_t result = esp_now_send(broadcastAddress, (uint8_t *) &myData, sizeof(myData));
  
  if (result == ESP_OK) {
    Serial.print("Sent: X=");
    Serial.print(myData.AcX);
    Serial.print(" Y=");
    Serial.print(myData.AcY);
    Serial.print(" Z=");
    Serial.println(myData.AcZ);
  } else {
    Serial.println("Error sending");
  }
  
  delay(100);  // Send data every 100ms (10 times per second)
}
