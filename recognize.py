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

from fp import to_mono, peaks_from_audio, hashes_from_peaks

DB_DIR = "db"

# MUST match build_db.py parameters
N_FFT = 1024
HOP = 256
TOP_K_PER_FRAME = 5
FAN_VALUE = 6
DT_MAX = 80

def load_db(): #loads the database at /db into memory
    with open(os.path.join(DB_DIR, "songs.json"), "r") as f: #loads song metadata. Ex. songs[0] = {id:0, title:"Grover Washington - Just The Two Of Us"}
        songs = json.load(f)

    with open(os.path.join(DB_DIR, "index.json"), "r") as f: #loads packed fingrerprint indeces
        packed = json.load(f)

    index = {} #copy index from .json into index for matching algorithm
    for h, postings in packed:
        index[int(h)] = [(int(sid), int(t)) for sid, t in postings]
    return songs, index

def recognize(query_wav, songs, index):
    x, sr = sf.read(query_wav) #loads the query clip
    x = to_mono(x) #normalizes the query clip

    # Automatically resample query to 8kHz to match database
    TARGET_SR = 8000
    if sr != TARGET_SR:
        x = resample_poly(x, TARGET_SR, sr).astype(np.float32)
        sr = TARGET_SR

    peaks = peaks_from_audio(x, sr, n_fft=N_FFT, hop=HOP, top_k_per_frame=TOP_K_PER_FRAME) #finds peaks of query clip
    hashes = hashes_from_peaks(peaks, fan_value=FAN_VALUE, dt_max=DT_MAX) #transforms peaks per frame to hashes per index

    votes = defaultdict(int)  # (song_id, offset) -> count. It counts how many fingerprints align in time
    for h, t_q in hashes: #for every hash in the query clip, look through database for potential matches
        postings = index.get(int(h)) # if it finds matching peaks, get index and use it as anchor for hash
        if not postings:
            continue
        for song_id, t_db in postings:
            offset = t_db - t_q
            votes[(song_id, offset)] += 1 #count successful matches in time frame

    if not votes:
        return None

    (best_song_id, best_offset), best_score = max(votes.items(), key=lambda kv: kv[1])
    return best_song_id, best_score #choose timeframe from song that best matches query clip's fingerprints. Returns song

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 recognize.py queries/clip.wav")
        raise SystemExit(1)

    songs, index = load_db()
    res = recognize(sys.argv[1], songs, index)

    if res is None:
        print("No match.")
    else:
        song_id, score = res
        print(f"Match: {songs[song_id]['title']} (score={score})")