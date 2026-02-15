# button_trigger.py
import sys
import subprocess
import serial

BAUD = 921600
STOP_MARK = b"STOP\n"
START_LINE = b"START\n"

def wait_for_start(ser: serial.Serial):
    # START is sent as a clean text line before binary PCM begins
    while True:
        line = ser.readline()
        if not line:
            continue
        if line.strip() == b"START":
            return

def wait_for_stop_in_binary(ser: serial.Serial):
    # After START, ESP32 streams binary PCM, then prints STOP\n.
    # We can't reliably use readline() during binary, so scan raw bytes.
    tail = b""
    while True:
        chunk = ser.read(4096)
        if not chunk:
            continue
        tail = (tail + chunk)[-32:]  # keep a small rolling buffer
        if STOP_MARK in tail:
            return

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 button_trigger.py /dev/ttyACM0 queries/whisper1.wav")
        return 1

    port = sys.argv[1]
    query_wav = sys.argv[2]

    # Open serial
    with serial.Serial(port, BAUD, timeout=0.2) as ser:
        # Clear any junk already buffered
        ser.reset_input_buffer()
        print(f"[button] listening on {port} @ {BAUD}...", flush=True)

        while True:
            print("[button] waiting for START...", flush=True)
            wait_for_start(ser)
            print("[button] got START, waiting for STOP...", flush=True)

            wait_for_stop_in_binary(ser)
            print("[button] got STOP -> running recognize", flush=True)

            # Trigger recognition on a known query wav (for now)
            subprocess.run(["python3", "recognize.py", query_wav], check=False)

            # Clean buffer so we don't instantly retrigger
            ser.reset_input_buffer()

if __name__ == "__main__":
    raise SystemExit(main())