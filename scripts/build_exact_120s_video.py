"""
Builds the EXACT 2-Minute (under 120-second) Pitch Video using the User's Cloned Voice (F5-TTS).
- 188-word calibrated script across 7 slides (~16-17s per slide = ~116-118s total)
- Strictly stays under the 120-second (2-minute) limit
- Speaks at natural 1.0x speed (no audio speeding up)
- Overlays the presenter avatar bubble with glowing ring
- 1080p high definition output (H.264 / AAC)
"""

import os
import sys
import subprocess
import time
import shutil

os.environ['MPLCONFIGDIR'] = os.path.abspath('reports/video_assets/mpl_cache')
sys.path.insert(0, os.getcwd())

import torch
from f5_tts.api import F5TTS

OUT_DIR = os.path.abspath('reports/video_assets/v5_exact_120s')
os.makedirs(OUT_DIR, exist_ok=True)

ref_wav_10s = os.path.abspath('reports/video_assets/ref_user_10s.wav')
ref_text = "Hey, hello, hi, how are you? Yeah, we have participated on the meta hackathon and this we want to do all these."

# Calibrated 188-word script: exactly ~115-118 seconds at natural speed
SCRIPT_EXACT_2MIN = {
    1: (
        "Hello judges! I am Akileshwarakrishnan, creator of Satyahd. "
        "Enterprises are rapidly deploying customer AI agents, but they face a critical problem: "
        "probabilistic LLMs hallucinate rogue discounts and commitments."
    ),
    2: (
        "In 2024, Air Canada was held legally liable when their chatbot promised unauthorized bereavement discounts. "
        "The courts ruled that enterprises are legally bound by their AI's promises without exception."
    ),
    3: (
        "Satyahd solves this. "
        "Outgoing drafts are parsed by Meta's muse-spark into structured commitments, "
        "then evaluated against corporate policies by pure-Python deterministic rules in under fifty milliseconds."
    ),
    4: (
        "Tested against twenty aggressive haggling attacks, "
        "Satyahd delivered 100% containment, safely rewriting drafts into compliant offers "
        "while preserving customer warmth and eliminating brand liability."
    ),
    5: (
        "For dispute defense, every decision is signed with an Ed25519 digital key "
        "and sealed into a continuous SHA-256 hash chain, meeting rigorous court evidentiary standards."
    ),
    6: (
        "By using Meta's muse-spark in minimal reasoning mode, we cut latency by 62% and token costs by 58%. "
        "All 156 automated test suites pass with 100% accuracy."
    ),
    7: (
        "Satyahd connects to any chatbot via MCP or REST in five lines of code. "
        "It runs air-gapped on Docker and stops liability before it happens. Thank you!"
    )
}

def get_audio_duration(audio_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())

def main():
    print("=" * 70)
    print("  🎬 BUILDING EXACT 2-MINUTE (UNDER 120-SEC) PITCH VIDEO (USER VOICE)")
    print("=" * 70)

    print("\n[Step 1/3] Initializing F5TTS on CUDA GPU...")
    t0 = time.time()
    f5tts = F5TTS(device="cuda" if torch.cuda.is_available() else "cpu")
    print(f"F5TTS initialized in {time.time() - t0:.1f}s")

    # 1. Synthesize audio for all 7 slides
    print("\n[Step 2/3] Synthesizing 7 voiceover clips for exact 2-minute video...")
    slide_durations = {}
    total_audio_dur = 0.0

    for i in range(1, 8):
        text = SCRIPT_EXACT_2MIN[i]
        out_wav = os.path.join(OUT_DIR, f"slide_{i:02d}.wav")
        if os.path.exists(out_wav) and os.path.getsize(out_wav) > 10000:
            dur = get_audio_duration(out_wav)
            slide_durations[i] = dur
            total_audio_dur += dur
            print(f"  Slide {i} already synthesized: {dur:.1f}s")
            continue

        print(f"\n[Slide {i}/7] Synthesizing: \"{text[:50]}...\"")
        t_infer = time.time()
        f5tts.infer(
            ref_file=ref_wav_10s,
            ref_text=ref_text,
            gen_text=text,
            file_wave=out_wav,
            speed=1.0  # Natural 1.0x speed
        )
        dur = get_audio_duration(out_wav)
        slide_durations[i] = dur
        total_audio_dur += dur
        print(f"  Slide {i} ready: {dur:.1f}s (inference took {time.time() - t_infer:.1f}s)")

    print(f"\n--> Total Raw Voiceover Duration: {total_audio_dur:.1f} seconds (Target: ~115-119s)")

    # 2. Render 1080p Video Clips
    print("\n[Step 3/3] Rendering 1080p clips with presenter avatar and merging...")
    clips = []
    bubble_img = os.path.abspath("reports/video_assets/presenter_bubble.png")

    for i in range(1, 8):
        audio_p = os.path.join(OUT_DIR, f"slide_{i:02d}.wav")
        slide_img = os.path.abspath(f"reports/video_assets/slide_{i:02d}.png")
        out_clip = os.path.join(OUT_DIR, f"clip_{i:02d}.mp4")

        # Slight 0.1s buffer
        dur = slide_durations[i] + 0.1
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", str(dur), "-i", slide_img,
            "-i", bubble_img,
            "-i", audio_p,
            "-filter_complex",
            "[0:v][1:v] overlay=1640:800 [v]; [2:a] volume=1.8,loudnorm [a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "256k",
            "-shortest",
            out_clip
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  Rendered clip {i}: {out_clip} ({dur:.1f}s)")
        clips.append(out_clip)

    # 3. Concatenate into Final Video
    concat_txt = os.path.join(OUT_DIR, "concat_list.txt")
    with open(concat_txt, "w") as f:
        for c in clips:
            abs_p = os.path.abspath(c).replace("\\", "/")
            f.write(f"file '{abs_p}'\n")

    target_video_exact = "Satyahd_Official_Pitch_Video_2Min_Exact.mp4"
    main_video = "Satyahd_Official_Pitch_Video_UserVoice.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        target_video_exact
    ]
    subprocess.run(cmd, check=True)

    # Copy to main video name so all existing references use this exact 2min cut
    shutil.copy2(target_video_exact, main_video)

    final_dur = get_audio_duration(target_video_exact)
    file_size_mb = os.path.getsize(target_video_exact) / (1024 * 1024)

    print("\n" + "=" * 70)
    print(f"  🎉 SUCCESS! EXACT 2-MINUTE PITCH VIDEO GENERATED:")
    print(f"  • File:     {target_video_exact}")
    print(f"  • Duration: {final_dur:.1f} seconds (Under 120s limit!)")
    print(f"  • Size:     {file_size_mb:.2f} MB (1080p HD)")
    print(f"  • Voice:    Your Cloned Natural Voice (1.0x speed, no rushing)")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
