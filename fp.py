"""
fp.py — Fingerprinting Module

This file contains the core audio fingerprinting logic.

What it does:
- Converts audio to mono
- Generate a spectrogram 
- Extract the most significant frequency peaks from each time frame (tbd the length)
- Create combinatorial hashes from peak pairs. We then send these to a hash table

Input:
    Raw PCM audio (from WAV file or microphone)

Output:
    List of (hash, time_anchor) pairs
"""

import numpy as np
from scipy.signal import stft