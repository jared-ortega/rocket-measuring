#include "HX711.h"

const int DOUT = 3;
const int CLK  = 2;
const int RATE = 4;  // HX711 RATE pin → conectar al pin D4 del Arduino

HX711 balanza;

void setup() {
  // Forzar 80 SPS antes de inicializar el HX711
  pinMode(RATE, OUTPUT);
  digitalWrite(RATE, HIGH);  // HIGH = 80 SPS | LOW = 10 SPS (default)
  delay(10);

  Serial.begin(115200);
  balanza.begin(DOUT, CLK);
  balanza.set_scale(-105.1428);
  balanza.tare();
}

void loop() {
  if (balanza.is_ready()) {
    Serial.println(balanza.get_units(1), 3);
  }
}
