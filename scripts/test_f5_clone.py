"""
Tests F5-TTS zero-shot voice cloning using the user's real voice recording.
"""

import os
import sys
import soundfile as sf
import torch

os.environ['MPLCONFIGDIR'] = os.path.abspath('reports/video_assets/mpl_cache')

from f5_tts.api import F5TTS

# Extract first 10 seconds of user voice at 24kHz
wav_in = os.path.abspath('reports/video_assets/user_voice.wav')
audio_data, sr = sf.read(wav_in)

ref_wav_10s = os.path.abspath('reports/video_assets/ref_user_10s.wav')
sf.write(ref_wav_10s, audio_data[:sr*10], sr)
print(f'Reference audio saved: {ref_wav_10s} (10 seconds)')

ref_text = "Hey, hello, hi, how are you? Yeah, we have participated on the meta hackathon and this we want to do all these."
gen_text = "Hello judges! I am Akileshwarakrishnan, creator of Satyahd. Satyahd is the first zero-trust gateway that air-gaps AI agents from business liability."

out_test = os.path.abspath('reports/video_assets/cloned_test_slide1.wav')

print("Initializing F5TTS on CUDA...")
f5tts = F5TTS(device="cuda" if torch.cuda.is_available() else "cpu")

print("Cloning user voice for Slide 1...")
f5tts.infer(
    ref_file=ref_wav_10s,
    ref_text=ref_text,
    gen_text=gen_text,
    file_wave=out_test,
    speed=1.05
)

print(f"SUCCESS! Cloned speech generated: {out_test}")
print(f"File size: {os.path.getsize(out_test)} bytes")
