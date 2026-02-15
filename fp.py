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

def to_mono(x: np.ndarray) -> np.ndarray: #transform audio to mono and normalizes (Meaning no sample peak is bigger than 1)
    x = x.astype(np.float32) ##force convert audio into float32 type
    if x.ndim == 2: #if array is 2d (meaning stereo), average both channels and copy back into array with 1D
            x = np.mean(x, axis=1)
    m = np.max(np.abs(x)) + 1e-9 #find the absolute amplitude + a small number in case amplitude is 0
    return x / m #divide the audio array by m to convert amplitude range to [-1, 1]

def peaks_from_audio(x: np.ndarray, sr: int, n_fft: int = 1024, hop: int = 256, top_k_per_frame: int = 5):
    #n_fft is size of window(how many samples per slice), hop is how many samples you step forward per frame, 
    # top_k is how many peak frequencies we keep from each time frame
    ''' for the audios, for each time frame, 
    keep the top K# frequency chunks
    (The smaller these) intervals +accuracy -speed '''
    f, t, Z = stft(x, fs = sr, nperseg = n_fft, noverlap = n_fft-hop, padded = False, boundary = None)
    mag = np.abs(Z) #performs fourier transform to split the signal into overlapping windows, we take the magnitude of the complex-valued result
    
    peaks = [] #array to store the local maxima peaks
    for ti in range(mag.shape[1]): #take a vertical slice of sample at time frame 'ti'. Takes all frequencies at that time for all the sample
        col = mag[:, ti]
        k = min(top_k_per_frame, len(col)) 
        idx = np.argpartition(col, -k)[-k:] #numpy function finds indices of peaks 
        idx = idx[np.argsort(col[idx])[::-1]] #then we sort them in descending magnitude

        for fi in idx: 
            if col[fi] > 0:
                peaks.append((ti, int(fi))) #store these peaks in this time frame in the index 
                                            #as we iterate through sample in peaks[], a 2D output array as [(time frame index, frequency bin)]
    return peaks

def hashes_from_peaks(peaks,
                      fan_value: int = 6, #how many future peaks it pairs it with(n+1,n+2 etc)
                      dt_min: int = 1, #minimum step size for pairing
                      dt_max: int = 80): #maximum step size for pairing
    """
    Create Shazam-style hashes: (f1, f2, dt) packed into an int.
    Returns: list of (hash, anchor_time)
    """
    peaks = sorted(peaks) #sort peaks by chronological time
    hashes = [] #create output array

    for i, (t1, f1) in enumerate(peaks): # for each peak, treat it as an anchor and find 'fan_value' # of pairs
        for j in range(1, fan_value + 1):
            if i + j >= len(peaks):
                break
            t2, f2 = peaks[i + j]
            dt = t2 - t1
            if dt_min <= dt <= dt_max:
                h = (f1 & 0x3FF) | ((f2 & 0x3FF) << 10) | ((dt & 0x3FF) << 20)
                hashes.append((int(h), int(t1))) #if step between pairs is within range, store this hash into the output array with (hash, anchor_time_frame aka time 0 at that frame)
    return hashes
    
           