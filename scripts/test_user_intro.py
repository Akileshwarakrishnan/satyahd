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

print("Initializing F5TTS on CUDA...", flush=True)
t0 = time.time()
f5tts = F5TTS(device="cuda" if torch.cuda.is_available() else "cpu")
print(f"F5TTS ready in {time.time()-t0:.1f}s", flush=True)

test_text = "I'm Akileshwarakrishnan. Welcome to Satyahd."
out_wav = os.path.abspath('reports/video_assets/test_akilesh_intro.wav')

t1 = time.time()
f5tts.infer(
    ref_file=ref_wav_10s,
    ref_text=ref_text,
    gen_text=test_text,
    file_wave=out_wav,
    speed=1.08
)
print(f"Synthesized in {time.time()-t1:.1f}s: {out_wav}", flush=True)

cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", out_wav]
dur = float(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip())
print(f"Duration: {dur:.2f}s", flush=True)
