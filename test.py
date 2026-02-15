from servo_control import ServoController
import time


def main():
    servo = ServoController(18, 50)
    try:
        print("Setting 90°", flush=True)
        servo.set_angle(90)
        time.sleep(2)

        print("Setting 45°", flush=True)
        servo.set_angle(180)
        time.sleep(2)

        print("Setting 0°", flush=True)
        servo.set_angle(0)
        time.sleep(2)

    finally:
        servo.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())