"""
Tests the natural human intro for Slide 1 with F5TTS at speed=1.08.
"""

import os
import sys
import subprocess
import time

os.environ['MPLCONFIGDIR'] = os.path.abspath('reports/video_assets/mpl_cache')
sys.path.insert(0, os.getcwd())

import torch
from f5_tts.api import F5TTS

ref_wav_10s = os.path.abspath('reports/video_assets/ref_user_10s.wav')
ref_text = "Hey, hello, hi, how are you? Yeah, we have participated on the meta hackathon and this we want to do all these."

natural_intro = (
    "Welcome everyone! This is Satyahd. Companies are deploying AI customer agents everywhere. "
    "But they face a serious risk. Chatbots easily hallucinate unauthorized commitments and rogue discounts, "
    "creating massive legal liability."
)

out_test = os.path.abspath('reports/video_assets/test_natural_intro.wav')

print("Initializing F5TTS on CUDA...")
f5tts = F5TTS(device="cuda" if torch.cuda.is_available() else "cpu")

print("Synthesizing natural intro...")
t0 = time.time()
f5tts.infer(
    ref_file=ref_wav_10s,
    ref_text=ref_text,
    gen_text=natural_intro,
    file_wave=out_test,
    speed=1.08
)
print(f"Done in {time.time()-t0:.1f}s!")

cmd = [
    "ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1", out_test
]
dur = float(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip())
print(f"Generated natural intro duration: {dur:.2f} seconds ({os.path.getsize(out_test)} bytes)")
