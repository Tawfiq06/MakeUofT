const int micPin = A0;
const int buttonPin = 7;
const int recordingLedPin = 8;

const int sampleRate = 8000;   // 8khz
unsigned long lastSampleTime = 0;
unsigned long sampleInterval = 1000000UL / sampleRate;

unsigned long sampleCount = 0;
unsigned long maxSamples = (unsigned long) sampleRate * 15;  // 15 seconds

bool recording = false;

// Debounce / edge detect for INPUT_PULLUP button
bool lastButtonPressed = false;
unsigned long lastButtonChangeMs = 0;
const unsigned long debounceMs = 40;

void setup() {
  Serial.begin(500000);
  pinMode(buttonPin, INPUT_PULLUP);
  pinMode(recordingLedPin, OUTPUT);
  digitalWrite(recordingLedPin, LOW);
}

void loop() {

  // Button is INPUT_PULLUP: pressed == LOW
  bool pressedNow = (digitalRead(buttonPin) == LOW);
  unsigned long nowMs = millis();

  // debounce
  if (pressedNow != lastButtonPressed) {
    lastButtonChangeMs = nowMs;
    lastButtonPressed = pressedNow;
  }

  bool stablePressed = pressedNow && (nowMs - lastButtonChangeMs) > debounceMs;

  // Start recording only on a stable press while not already recording
  if (stablePressed && !recording) {
    recording = true;
    sampleCount = 0;
    digitalWrite(recordingLedPin, HIGH);

    // Burst the start marker so the Pi will catch it even if it opens serial slightly late
    for (int i = 0; i < 25; i++) {
      Serial.write("STRT", 4);
      delay(2);
    }

    // small guard delay before audio starts
    delay(20);
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

        // Tell the Pi the recording is complete (repeat to be robust)
        for (int i = 0; i < 10; i++) {
          Serial.write("DONE", 4);
          delay(2);
        }
      }
    }
  }
}
