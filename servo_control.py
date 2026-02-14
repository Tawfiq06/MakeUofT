import RPI.GPIO as GPIO
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
        
        duty = 2 + (angle / 18) #simple conversion: 0-180 -> 2-12 duty cycle
        self.pwm.ChangeDutyCycle(duty)
        time.sleep(0.5)
        self.pwm.ChangeDutyCycle(0) #stop sending pwm to hold postion

    def cleanup(self):
        self.pwm.stop()
        GPIO.cleanup()
