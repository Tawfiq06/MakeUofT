"""
recognize.py — Song Recognition Engine

This script identifies an audio clip by matching it
against the fingerprint database we have installed in our DB

What it does:
- Loads a query WAV file
- Generates fingerprint hashes
- Looks up matching hashes in the database
- Computes time offset differences:
      offset = t_database - t_query
- Uses offset voting (histogram) to determine best match
- Returns the song with the highest aligned hash count

This script performs the actual song recognition.
"""

import os
import json
import time
from collections import defaultdict
import soundfile as sf

import numpy as np
from scipy.signal import resample_poly

# Safe import for PySerial (for Arduino audio streaming)
try:
    import serial  # pyserial
except Exception:
    serial = None

from servo_control import ServoController

from fp import to_mono, peaks_from_audio, hashes_from_peaks

DB_DIR = "db"
LOVE_SONG = 'Bad Bunny - Baile Inolvidable'
# MUST match build_db.py parameters
N_FFT = 1024
HOP = 256
TOP_K_PER_FRAME = 5
FAN_VALUE = 6
DT_MAX = 80
MIN_MATCH_SCORE = 200  # below this, treat as not recognized


# Serial mic streaming (Arduino) settings
SERIAL_DEFAULT_PORT = "/dev/serial0"  # often maps to ttyS0 on Raspberry Pi
SERIAL_BAUD = 500000
SERIAL_RECORD_SECONDS = 15
SERIAL_TARGET_SR = 8000

def load_db():  # loads the database at /db into memory
    with open(os.path.join(DB_DIR, "songs.json"), "r") as f:
        songs = json.load(f)

    with open(os.path.join(DB_DIR, "index.json"), "r") as f:
        packed = json.load(f)

    index = {}
    for h, postings in packed:
        index[int(h)] = [(int(sid), int(t)) for sid, t in postings]
    return songs, index


# Helper: Record raw int16 PCM streamed from Arduino over UART and write to WAV
def record_serial_to_wav(
    out_wav: str,
    port: str = SERIAL_DEFAULT_PORT,
    seconds: int = SERIAL_RECORD_SECONDS,
    baud: int = SERIAL_BAUD,
    sr: int = SERIAL_TARGET_SR,
    timeout_s: float = 0.2,
    start_wait_s: float = 3600.0,
    chunk_size: int = 4096,
    require_marker: bool = False,
):
    """Record raw 16-bit signed PCM streamed over serial and save to a WAV.

    Protocol from UnoMicDriver.ino:
      - On button press: starts streaming little-endian int16 PCM at 8 kHz for `seconds`
      - (Optional) may send ASCII markers like b"STRT" / b"DONE" if present in the sketch

    We trigger recording on the first arriving audio bytes (button press), then read exactly
    sr*seconds samples (2 bytes each), and write PCM_16 WAV.
    """
    if serial is None:
        raise RuntimeError("pyserial not installed. Run: python3 -m pip install pyserial")

    os.makedirs(os.path.dirname(out_wav) or ".", exist_ok=True)

    total_samples = int(sr) * int(seconds)
    total_bytes = total_samples * 2  # int16

    with serial.Serial(port, baudrate=baud, timeout=timeout_s) as ser:
        # Start clean
        try:
            ser.reset_input_buffer()
        except Exception:
            pass

        # 1) Wait for button-triggered stream (first audio bytes).
        # If the sketch sends "STRT", we ignore it unless require_marker=True.
        t0 = time.time()
        prebuf = bytearray()
        window = bytearray()
        marker = b"STRT"

        while time.time() - t0 < start_wait_s:
            chunk = ser.read(512)
            if not chunk:
                continue
            prebuf += chunk

            # Track last 4 bytes to optionally detect STRT
            for b in chunk:
                window.append(b)
                if len(window) > 4:
                    window = window[-4:]

            if require_marker:
                if bytes(window) == marker:
                    # After marker, start fresh for audio payload
                    prebuf = bytearray()
                    break
            else:
                # Trigger as soon as we see any data
                break

        if require_marker and bytes(window) != marker:
            raise RuntimeError(
                f"Did not receive start marker 'STRT' from {port} within {start_wait_s}s."
            )

        if not prebuf and not require_marker:
            raise RuntimeError(
                f"No serial audio received from {port} within {start_wait_s}s."
            )

        # Start timer once audio bytes have begun arriving
        capture_t0 = time.time()  # start timing once audio bytes have begun arriving
        # 2) Align to int16 boundary and start the audio payload buffer
        buf = bytearray(prebuf)
        if len(buf) % 2 == 1:
            extra = ser.read(1)
            if extra:
                buf.extend(extra)
            else:
                # If we can't align, drop the last byte
                buf = buf[:-1]

        # Keep only the most recent bytes if we accidentally buffered too much before starting
        if len(buf) > total_bytes:
            buf = buf[-total_bytes:]

        consecutive_timeouts = 0
        while len(buf) < total_bytes:
            want = min(chunk_size, total_bytes - len(buf))
            chunk = ser.read(want)
            if chunk:
                buf.extend(chunk)
                consecutive_timeouts = 0
            else:
                consecutive_timeouts += 1
                if consecutive_timeouts >= 10:
                    break

        if len(buf) < total_bytes:
            raise RuntimeError(
                f"Timed out reading serial audio. Got {len(buf)} of {total_bytes} bytes from {port}."
            )

        capture_t1 = time.time()
        elapsed = max(1e-6, capture_t1 - capture_t0)
        samples_captured = len(buf) // 2
        measured_sr = int(round(samples_captured / elapsed))

        # Guardrails: keep measured SR in a sane band so a brief stall doesn't produce nonsense
        if measured_sr < 4000 or measured_sr > 20000:
            measured_sr = int(sr)

        # 3) Optionally consume DONE marker (non-fatal)
        try:
            end_window = bytearray()
            t1 = time.time()
            while time.time() - t1 < 1.0:
                b = ser.read(1)
                if not b:
                    break
                end_window += b
                if len(end_window) > 4:
                    end_window = end_window[-4:]
                if bytes(end_window) == b"DONE":
                    break
        except Exception:
            pass

    pcm = np.frombuffer(buf, dtype=np.int16)

    # Use the measured sample rate so playback speed/pitch is correct.
    # `recognize()` will resample to 8 kHz afterward.
    try:
        used_sr = measured_sr  # computed above
    except NameError:
        used_sr = int(sr)

    print(f"[serial] captured {samples_captured} samples in {elapsed:.3f}s -> sr≈{used_sr} Hz")
    sf.write(out_wav, pcm, used_sr, subtype="PCM_16")
    return out_wav

def recognize(query_wav, songs=None, index=None, return_fields: bool = False):
    if songs is None or index is None:
        songs, index = load_db()

    x, sr = sf.read(query_wav)
    x = to_mono(x)

    # Automatically resample query to 8kHz to match database
    TARGET_SR = 8000
    if sr != TARGET_SR:
        x = resample_poly(x, TARGET_SR, sr).astype(np.float32)
        sr = TARGET_SR

    peaks = peaks_from_audio(x, sr, n_fft=N_FFT, hop=HOP, top_k_per_frame=TOP_K_PER_FRAME)
    hashes = hashes_from_peaks(peaks, fan_value=FAN_VALUE, dt_max=DT_MAX)

    votes = defaultdict(int)  # (song_id, offset) -> count
    for h, t_q in hashes:
        postings = index.get(int(h))
        if not postings:
            continue
        for song_id, t_db in postings:
            offset = t_db - t_q
            votes[(song_id, offset)] += 1

    if not votes:
        return None

    # Pick the single best-aligned match across all (song_id, offset)
    (best_song_id, best_offset), best_score = max(votes.items(), key=lambda kv: kv[1])

    if return_fields:
        title, artist, full_title = get_title_artist(best_song_id, songs)
        return {
            "song_id": best_song_id,
            "score": best_score,
            "offset": best_offset,
            "title": title,
            "artist": artist,
            "full_title": full_title,
        }

    return best_song_id, best_score  # backward-compatible

def title_output(full_title: str):
    """Split a display title into (artist, title) when possible."""
    if not isinstance(full_title, str):
        return "", ""

    for sep in (" - ", " – ", " — "):
        if sep in full_title:
            artist, title = full_title.split(sep, 1)
            return artist.strip(), title.strip()

    return "", full_title.strip()

def get_title_artist(song_id: int, songs: list) -> tuple[str, str, str]:
    """Return (title, artist, full_title) for a song id from songs.json."""
    if song_id is None or songs is None:
        return "", "", ""
    try:
        full_title = songs[song_id].get("title", "")
    except Exception:
        full_title = ""

    artist, title = title_output(full_title)
    if not title:
        title = full_title
    return title, artist, full_title

def handle_result(res: dict | None):
    """Given a recognize(..., return_fields=True) result dict, drive OLED + servo behavior."""
    servo = None
    try:
        servo = ServoController(18, 50)

        if res is None or res.get("score", 0) < MIN_MATCH_SCORE:
            score = 0 if res is None else res.get("score", 0)
            print(f"Not recognized (score={score})")
            try:
                from oled_display import display_song
                display_song("Not recognized", "")
            except Exception as e:
                print(f"[OLED] skipped: {e}")
            print("Not the love song")
            return

        print(f"Match: {res['full_title']} (score={res['score']})")
        if res.get("artist") and res.get("title"):
            print(f"Artist: {res['artist']}, Song Title: {res['title']}")
        else:
            print(f"Song Title: {res['full_title']}")

        try:
            from oled_display import display_song
            display_song(res.get("title", ""), res.get("artist", ""))
        except Exception as e:
            print(f"[OLED] skipped: {e}")

        if res.get("full_title") == LOVE_SONG:
            servo.set_angle(90)
        else:
            print("Not the love song")

    finally:
        if servo is not None:
            servo.cleanup()

if __name__ == "__main__":
    import sys

    # Usage:
    #   python3 recognize.py queries/clip.wav
    #   python3 recognize.py --serial [/dev/serial0] [seconds]
    #   python3 recognize.py --serial-loop [/dev/serial0] [seconds]

    if len(sys.argv) < 2:
        print("Usage:\n  python3 recognize.py queries/clip.wav\n  python3 recognize.py --serial [/dev/serial0] [seconds]\n  python3 recognize.py --serial-loop [/dev/serial0] [seconds]")
        raise SystemExit(1)

    query_path = sys.argv[1]

    if query_path == "--serial":
        port = sys.argv[2] if len(sys.argv) >= 3 else SERIAL_DEFAULT_PORT
        seconds = int(sys.argv[3]) if len(sys.argv) >= 4 else SERIAL_RECORD_SECONDS
        query_path = os.path.join("queries", "serial_capture.wav")
        print(f"Recording {seconds}s from Arduino on {port} at {SERIAL_BAUD} baud...")
        record_serial_to_wav(query_path, port=port, seconds=seconds)
        print(f"Saved: {query_path}")

        res = recognize(query_path, return_fields=True)
        handle_result(res)

    elif query_path == "--serial-loop":
        port = sys.argv[2] if len(sys.argv) >= 3 else SERIAL_DEFAULT_PORT
        seconds = int(sys.argv[3]) if len(sys.argv) >= 4 else SERIAL_RECORD_SECONDS
        query_path = os.path.join("queries", "serial_capture.wav")

        print(f"Serial loop armed. Press the Arduino button to start a {seconds}s capture.")
        while True:
            try:
                print(f"Waiting for 'STRT' on {port}...")
                record_serial_to_wav(
                    query_path,
                    port=port,
                    seconds=seconds,
                    start_wait_s=3600,
                    require_marker=False,
                )
                print(f"Saved: {query_path}")

                res = recognize(query_path, return_fields=True)
                handle_result(res)

                # Ready for the next button press
                time.sleep(0.2)
                continue
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[serial-loop] {e}")
                # small pause to avoid spam if wiring is loose
                time.sleep(0.5)

    else:
        res = recognize(query_path, return_fields=True)
        handle_result(res)