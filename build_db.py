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

from fp import to_mono, peaks_from_audio, hashes_from_peaks