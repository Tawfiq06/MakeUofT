const int micPin = A0;
const int buttonPin = 7;
const int recordingLedPin = 8;

const int sampleRate = 8000;   // 8khz
unsigned long lastSampleTime = 0;
unsigned long sampleInterval = 1000000UL / sampleRate;

unsigned long sampleCount = 0;
unsigned long maxSamples = (unsigned long) sampleRate * 15;  // 15 seconds

bool recording = false;

void setup() {
  Serial.begin(500000);
  pinMode(buttonPin, INPUT_PULLUP);
  pinMode(recordingLedPin, OUTPUT);
  digitalWrite(recordingLedPin, LOW);
}

void loop() {

  if (digitalRead(buttonPin) == LOW && !recording) {
    recording = true;
    sampleCount = 0;
    digitalWrite(recordingLedPin, HIGH);
    delay(200);
  }

  if (recording) {
    unsigned long currentTime = micros();

    if (currentTime - lastSampleTime >= sampleInterval) {
      lastSampleTime = currentTime;

      // Read 10-bit ADC
      int adc = analogRead(micPin);

      // Convert to signed 16-bit PCM
      int16_t pcm = (adc - 512) << 6;  
      // Explanation:
      // (adc - 512) gives signed -512 to +511
      // <<6 scales to roughly -32768 to +32704

      // Send raw binary (2 bytes)
      Serial.write((uint8_t*)&pcm, 2);

      sampleCount++;

      if (sampleCount >= maxSamples) {
        recording = false;
        digitalWrite(recordingLedPin, LOW);
      }
    }
  }
}
