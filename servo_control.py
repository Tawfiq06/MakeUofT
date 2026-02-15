import RPi.GPIO as GPIO
import time


class ServoController:
    def __init__(self, pin: int, frequency: int = 50):
        self.pin = pin
        self.freq = frequency

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)

        self.pwm = GPIO.PWM(self.pin, self.freq)
        self.pwm.start(0)

    def set_angle(self, angle: float):
        if angle < 0 or angle > 180:
            raise ValueError("Angle must be between 0 and 180")

        # Typical servo expects ~50 Hz pulses with ~1.0–2.0 ms high time.
        # At 50 Hz, period is 20 ms, so duty range is about 5%–10%.
        min_duty = 2.5
        max_duty = 12.5
        duty = min_duty + (angle / 180.0) * (max_duty - min_duty)

        # Send PWM long enough for the servo to actually move.
        self.pwm.ChangeDutyCycle(duty)
        time.sleep(1.0)

    def cleanup(self):
        # Stop PWM first, then cleanup GPIO.
        try:
            if hasattr(self, "pwm") and self.pwm is not None:
                self.pwm.stop()
        finally:
            self.pwm = None
            GPIO.cleanup()
