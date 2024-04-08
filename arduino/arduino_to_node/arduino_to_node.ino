#include "HX711.h"
// const int DOUT=A1;
// const int CLK=A0;

const int DOUT = 3;
const int CLK = 2;

int percent = 0;
int prevPercent = 0;

HX711 balanza;
void setup() {
  Serial.begin(9600);
  balanza.begin(DOUT, CLK);
  // Serial.print("Lectura del valor del ADC:  ");
  //Serial.println(balanza.read());
  // Serial.println("No ponga ningun  objeto sobre la balanza");
  // Serial.println("Destarando...");
  // Serial.println("...");
  //balanza.set_scale(-103.65652);  // Establecemos la escala
  //balanza.tare(20);               //El peso actual es considerado Tara.

  balanza.set_scale(-105.1428);  
  balanza.tare();               

  //Serial.println("Listo para pesar");
}

void loop() {
  // percent = round(analogRead(0) / 1024.00 * 100);
  // if(percent != prevPercent) {
  //   Serial.println(percent);
  //   prevPercent = percent;
  // }
  // delay(100);
  //Serial.print("Peso: ");
  Serial.print(balanza.get_units(1), 3);
  Serial.println();
  delay(2500);
}
