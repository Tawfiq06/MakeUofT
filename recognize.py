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

from fp import to_mono, peaks_from_audio, hashes_from_peaks