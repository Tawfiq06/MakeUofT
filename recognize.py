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
from collections import defaultdict
import soundfile as sf

import numpy as np
from scipy.signal import resample_poly

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

def load_db():  # loads the database at /db into memory
    with open(os.path.join(DB_DIR, "songs.json"), "r") as f:
        songs = json.load(f)

    with open(os.path.join(DB_DIR, "index.json"), "r") as f:
        packed = json.load(f)

    index = {}
    for h, postings in packed:
        index[int(h)] = [(int(sid), int(t)) for sid, t in postings]
    return songs, index

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

    (best_song_id, best_offset), best_score = max(votes.items(), key=lambda kv: kv[1])

    if return_fields:
        title, artist, full_title = get_title_artist(best_song_id, songs)
        return {
            "song_id": best_song_id,
            "score": best_score,
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

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 recognize.py queries/clip.wav")
        raise SystemExit(1)

    res = recognize(sys.argv[1], return_fields=True)

    servo = None
    try:
        servo = ServoController(18, 50)

        if res is None or res.get("score", 0) < MIN_MATCH_SCORE:
            # Low-confidence or no match
            score = 0 if res is None else res.get("score", 0)
            print(f"Not recognized (score={score})")

            # Try OLED (optional)
            try:
                from oled_display import display_song  # local import avoids circular import
                display_song("Not recognized", "")
            except Exception as e:
                print(f"[OLED] skipped: {e}")

            # Servo / love-song behavior
            print("Not the love song")

        else:
            print(f"Match: {res['full_title']} (score={res['score']})")
            if res.get("artist") and res.get("title"):
                print(f"Artist: {res['artist']}, Song Title: {res['title']}")
            else:
                print(f"Song Title: {res['full_title']}")

            # Try OLED (optional)
            try:
                from oled_display import display_song  # local import avoids circular import
                display_song(res.get("title", ""), res.get("artist", ""))
            except Exception as e:
                print(f"[OLED] skipped: {e}")

            if res['full_title'] == LOVE_SONG:
                servo.set_angle(90)
            else:
                print("Not the love song")

    finally:
        if servo is not None:
            servo.cleanup()