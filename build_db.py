"""
build_db.py — Database Builder

This script builds the fingerprint database from the songs we download
and upload from youtube/spotify or whatever. This is basically our internal
song database.

What it does:
- Loads WAV files from songs_wav/
- Convert audio to mono and normalize
- Generate most important dB peaks and hashes using fp.py
- Store hashes in an index:
      hash -> [(song_id, time_offset), ...]
- Save the index and song metadata into db/

This script is run once to create the searchable database.
"""
import os
import json
from collections import defaultdict
import soundfile as sf
import re

import numpy as np
from scipy.signal import resample_poly

from fp import to_mono, peaks_from_audio, hashes_from_peaks

SONGS_DIR = "songs_wav_8k"
DB_DIR = "db"

# Fingerprint parameters
N_FFT = 1024
HOP = 256
TOP_K_PER_FRAME = 5
FAN_VALUE = 6
DT_MAX = 80

def main():
    os.makedirs(DB_DIR, exist_ok=True)

    index = defaultdict(list)   # hash -> list[(song_id, t_anchor)]
    songs = []                  # metadata of song list

    song_files = sorted([f for f in os.listdir(SONGS_DIR) if f.lower().endswith(".wav")])
    if not song_files:
        print(f"No .wav files found in {SONGS_DIR}/")
        return

    for song_id, fn in enumerate(song_files):
        path = os.path.join(SONGS_DIR, fn)
        x, sr = sf.read(path)
        x = to_mono(x)

        # Automatically resample all songs to 8kHz for consistent fingerprinting
        TARGET_SR = 8000
        if sr != TARGET_SR:
            x = resample_poly(x, TARGET_SR, sr).astype(np.float32)
            sr = TARGET_SR

        peaks = peaks_from_audio(x, sr, n_fft=N_FFT, hop=HOP, top_k_per_frame=TOP_K_PER_FRAME)
        hashes = hashes_from_peaks(peaks, fan_value=FAN_VALUE, dt_max=DT_MAX)

        for h, t_anchor in hashes:
            index[int(h)].append((song_id, int(t_anchor)))

        def _spacify_camel(text: str) -> str:
            return re.sub(r'(?<!^)(?=[A-Z])', ' ', text)

        base_name = os.path.splitext(fn)[0]
        if "_" in base_name:
            artist_part, song_part = base_name.split("_", 1)
            artist_part = _spacify_camel(artist_part)
            song_part = _spacify_camel(song_part)
            display_title = f"{artist_part} - {song_part}"
        else:
            display_title = _spacify_camel(base_name)

        songs.append({
            "id": song_id,
            "title": display_title,
            "file": fn,
            "sr": sr
        })

        print(f"Indexed {fn}: sr={sr} peaks={len(peaks)} hashes={len(hashes)}")

    with open(os.path.join(DB_DIR, "songs.json"), "w") as f:
        json.dump(songs, f, indent=2)

    packed = [[h, postings] for h, postings in index.items()]
    with open(os.path.join(DB_DIR, "index.json"), "w") as f:
        json.dump(packed, f)

    print(f"\nDone. songs={len(songs)} unique_hashes={len(index)}")
    print(f"DB saved to {DB_DIR}/songs.json and {DB_DIR}/index.json")

if __name__ == "__main__":
    main()