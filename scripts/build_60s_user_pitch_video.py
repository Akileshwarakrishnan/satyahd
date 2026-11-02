"""
Builds the 60-second (1-minute) Demo Pitch Video using the User's Cloned Voice (F5-TTS).
- 127-word tight script across 7 slides
- Speaks at natural 1.0x speed (no audio speeding up)
- Overlays the presenter avatar bubble with glowing ring
- 1080p high definition output (H.264 / AAC)
"""

import os
import sys
import subprocess
import time

os.environ['MPLCONFIGDIR'] = os.path.abspath('reports/video_assets/mpl_cache')
sys.path.insert(0, os.getcwd())

import torch
from f5_tts.api import F5TTS

OUT_DIR = os.path.abspath('reports/video_assets/v3_60s_cloned')
os.makedirs(OUT_DIR, exist_ok=True)

ref_wav_10s = os.path.abspath('reports/video_assets/ref_user_10s.wav')
ref_text = "Hey, hello, hi, how are you? Yeah, we have participated on the meta hackathon and this we want to do all these."

# 60-Second Tight Script (Total ~127 words, ~60s at 1.0x natural speed)
SCRIPT_60S = {
    1: "Hello judges! I am Akileshwarakrishnan, creator of Satyahd—a zero-trust guardrail protecting businesses from AI chatbot liabilities.",
    2: "Chatbots hallucinate rogue commitments. In 2024, Air Canada was held strictly liable when their chatbot promised unauthorized bereavement discounts.",
    3: "Satyahd solves this. Outgoing drafts are parsed by Meta's muse-spark and verified by deterministic pure-Python rules in under fifty milliseconds.",
    4: "Tested against twenty aggressive haggling attacks, Satyahd delivered 100% containment, safely bounding discounts to authorized corporate caps.",
    5: "Every decision is signed with an Ed25519 digital key and sealed into an append-only continuous SHA-256 hash chain.",
    6: "Using Meta's muse-spark in minimal reasoning mode, we cut latency by 62% while preserving brand warmth.",
    7: "Satyahd connects to any chatbot via MCP or REST in five lines of code. Thank you for your time!"
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
    print("  🎬 BUILDING 60-SECOND PITCH VIDEO WITH USER'S CLONED NATURAL VOICE")
    print("=" * 70)

    print("\n[Step 1/3] Initializing F5TTS on CUDA GPU...")
    t0 = time.time()
    f5tts = F5TTS(device="cuda" if torch.cuda.is_available() else "cpu")
    print(f"F5TTS initialized in {time.time() - t0:.1f}s")

    # 1. Synthesize audio for all 7 slides
    print("\n[Step 2/3] Synthesizing 7 short voiceover clips at natural speed...")
    slide_durations = {}
    total_audio_dur = 0.0

    for i in range(1, 8):
        text = SCRIPT_60S[i]
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
            speed=1.0  # Natural 1.0x speed, no rush
        )
        dur = get_audio_duration(out_wav)
        slide_durations[i] = dur
        total_audio_dur += dur
        print(f"  Slide {i} ready: {dur:.1f}s (inference took {time.time() - t_infer:.1f}s)")

    print(f"\n--> Total Raw Voiceover Duration: {total_audio_dur:.1f} seconds (Target: ~60s)")

    # 2. Render 1080p Video Clips
    print("\n[Step 3/3] Rendering 1080p clips with presenter avatar and merging...")
    clips = []
    bubble_img = os.path.abspath("reports/video_assets/presenter_bubble.png")

    for i in range(1, 8):
        audio_p = os.path.join(OUT_DIR, f"slide_{i:02d}.wav")
        slide_img = os.path.abspath(f"reports/video_assets/slide_{i:02d}.png")
        out_clip = os.path.join(OUT_DIR, f"clip_{i:02d}.mp4")

        # Slight 0.15s buffer for clean transition
        dur = slide_durations[i] + 0.15
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

    target_video_60s = "Satyahd_Official_Pitch_Video_60s.mp4"
    main_video = "Satyahd_Official_Pitch_Video_UserVoice.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        target_video_60s
    ]
    subprocess.run(cmd, check=True)

    # Copy to main video name so all existing references use this new 60s cut
    import shutil
    shutil.copy2(target_video_60s, main_video)

    final_dur = get_audio_duration(target_video_60s)
    file_size_mb = os.path.getsize(target_video_60s) / (1024 * 1024)

    print("\n" + "=" * 70)
    print(f"  🎉 SUCCESS! 60-SECOND PITCH VIDEO GENERATED:")
    print(f"  • File:     {target_video_60s}")
    print(f"  • Duration: {final_dur:.1f} seconds")
    print(f"  • Size:     {file_size_mb:.2f} MB (1080p HD)")
    print(f"  • Voice:    Your Cloned Natural Voice (1.0x speed, no rushing)")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
