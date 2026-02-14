const int micPin = 34;        // ADC pin connected to mic output
const int buttonPin = 25;     // Push button to start recording
const int recordingLedPin = 26;        // Recording indicator LED

// Audio ADC
const int sampleRate = 16000; // 16 kHz sample rate
unsigned long lastSampleTime = 0;
unsigned long sampleInterval = 1000000 / sampleRate; //in microseconds
int sampleCount = 0;
int maxSamples = sampleRate * 15; // To record 15 seconds

bool recording = false;

void setup(){
  Serial.begin(921600); // start USB serial
  pinMode(buttonPin, INPUT_PULLUP); // button pressed is LOW
  pinMode(recordingLedPin, OUTPUT);
  digitalWrite(recordingLedPin, LOW);
  analogReadResolution(12); // 12-bit ADC (0-4095)
}

void loop() {
  /**** CHECK IF BUTTON IS PRESSED ****/
  if (digitalRead(buttonPin) == LOW && !recording){
    recording = true;
    sampleCount = 0;
    Serial.println("START");
    digitalWrite(recordingLedPin, HIGH); // LED is now ON
    delay(200); // for button debounce
  }

  /**** RECORD AUDIO IF TRIGGERED ****/
  if (recording){
    unsigned long currentTime = micros();
    if (currentTime - lastSampleTime >= sampleInterval){
      lastSampleTime = currentTime;

      // Read and send sample as binary
      int16_t sample = analogRead(micPin) - 2048; // 12-bit mid-point 
      sample <<= 4;    //scale to 16-bit signed
      Serial.write((uint8_t*)&sample, 2);

      sampleCount++;

      // Blink LED every second
      if (sampleCount % sampleRate == 0){
        digitalWrite(recordingLedPin, !digitalRead(recordingLedPin));
      }

      if (sampleCount >= maxSamples) {
        recording = false;
        Serial.println("STOP");
        digitalWrite(recordingLedPin, LOW);
      }
    }
  }
 
}