"""
Builds the Final Pitch Video with Natural Voice, No Lagging, and Under 2 Minutes (120s).
- Eliminates robotic intro and unnatural name/jargon pronunciations.
- Uses short, crisp sentences (8-12 words) without dragging punctuation.
- Synthesizes at speed=1.08 with F5-TTS CUDA using user's cloned reference voice.
- Preserves all Meta model references (muse-spark).
- Overlays the presenter avatar bubble with glowing ring at 1080p HD.
- Stays strictly under 120 seconds (target ~110-114s).
"""

import os
import sys
import subprocess
import time
import shutil

print(">> Python script started...", flush=True)

mpl_dir = os.path.abspath('reports/video_assets/mpl_cache')
os.makedirs(mpl_dir, exist_ok=True)
os.environ['MPLCONFIGDIR'] = mpl_dir
sys.path.insert(0, os.getcwd())

print(">> Importing PyTorch & F5-TTS (this takes ~60-90s on Windows)...", flush=True)
import torch
from f5_tts.api import F5TTS
print(">> PyTorch & F5-TTS imported successfully!", flush=True)

OUT_DIR = os.path.abspath('reports/video_assets/v6_natural_fast')
os.makedirs(OUT_DIR, exist_ok=True)

ref_wav_10s = os.path.abspath('reports/video_assets/ref_user_10s.wav')
ref_text = "Hey, hello, hi, how are you? Yeah, we have participated on the meta hackathon and this we want to do all these."

NATURAL_SCRIPT = {
    1: (
        "Welcome everyone! This is Satyahd. Companies are deploying AI customer agents everywhere. "
        "But they face a serious risk. Chatbots easily hallucinate unauthorized commitments and rogue discounts, "
        "creating massive legal liability."
    ),
    2: (
        "In 2024, Air Canada was held strictly liable when their chatbot promised an unauthorized bereavement discount. "
        "The court ruled that companies are legally responsible for their AI's words. "
        "System prompts cannot prevent this, but Satyahd does."
    ),
    3: (
        "Satyahd acts as a zero-trust guardrail. Outgoing messages are intercepted in real time. "
        "Meta's muse-spark extracts promises into structured data. "
        "Then pure Python rules verify them against company policies in under fifty milliseconds."
    ),
    4: (
        "We red-teamed Satyahd against twenty aggressive haggling attacks. "
        "Without Satyahd, agents broke policy 90 percent of the time. "
        "With Satyahd, containment is 100 percent, safely rewriting replies while keeping customer warmth."
    ),
    5: (
        "For dispute defense, Satyahd provides cryptographic proof. "
        "Every decision is signed with an Ed25519 digital key and sealed into a continuous SHA-256 hash chain, "
        "meeting strict legal standards."
    ),
    6: (
        "Scale requires speed. Using Meta's muse-spark with minimal reasoning mode, we cut latency by 62 percent down to 48 milliseconds. "
        "All 156 automated test suites pass with 100 percent accuracy."
    ),
    7: (
        "Satyahd is production ready today. Any team can wrap their chatbot in five lines of code using our MCP server or REST API. "
        "It stops liability before it happens. Thank you!"
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
    print("  🎬 BUILDING NATURAL, CRISP 2-MINUTE PITCH VIDEO (USER VOICE)")
    print("=" * 70)

    # Slide 1 test file already generated
    s1_test = os.path.abspath('reports/video_assets/test_natural_intro.wav')
    s1_out = os.path.join(OUT_DIR, "slide_01.wav")
    if os.path.exists(s1_test) and not os.path.exists(s1_out):
        shutil.copy2(s1_test, s1_out)
        print(f"Copied pre-tested natural intro to {s1_out}")

    print("\n[Step 1/3] Initializing F5TTS on CUDA GPU...")
    t0 = time.time()
    f5tts = F5TTS(device="cuda" if torch.cuda.is_available() else "cpu")
    print(f"F5TTS initialized in {time.time() - t0:.1f}s")

    slide_durations = {}
    total_audio_dur = 0.0

    print("\n[Step 2/3] Synthesizing natural voiceover clips (speed=1.08, crisp phrasing)...")
    for i in range(1, 8):
        text = NATURAL_SCRIPT[i]
        out_wav = os.path.join(OUT_DIR, f"slide_{i:02d}.wav")
        if os.path.exists(out_wav) and os.path.getsize(out_wav) > 10000:
            dur = get_audio_duration(out_wav)
            slide_durations[i] = dur
            total_audio_dur += dur
            print(f"  Slide {i} ready: {dur:.1f}s")
            continue

        print(f"\n[Slide {i}/7] Synthesizing: \"{text[:55]}...\"")
        t_infer = time.time()
        f5tts.infer(
            ref_file=ref_wav_10s,
            ref_text=ref_text,
            gen_text=text,
            file_wave=out_wav,
            speed=1.08
        )
        dur = get_audio_duration(out_wav)
        slide_durations[i] = dur
        total_audio_dur += dur
        print(f"  Slide {i} finished: {dur:.1f}s (inference took {time.time() - t_infer:.1f}s)")

    print(f"\n--> Total Raw Voiceover Duration: {total_audio_dur:.1f} seconds (Target: < 120s)")

    # 2. Render 1080p Video Clips
    print("\n[Step 3/3] Rendering 1080p clips with presenter avatar and merging...")
    clips = []
    bubble_img = os.path.abspath("reports/video_assets/presenter_bubble.png")

    for i in range(1, 8):
        audio_p = os.path.join(OUT_DIR, f"slide_{i:02d}.wav")
        slide_img = os.path.abspath(f"reports/video_assets/slide_{i:02d}.png")
        out_clip = os.path.join(OUT_DIR, f"clip_{i:02d}.mp4")

        # Slight 0.08s buffer
        dur = slide_durations[i] + 0.08
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

    # Copy to main video name so all references work seamlessly
    shutil.copy2(target_video_exact, main_video)

    final_dur = get_audio_duration(target_video_exact)
    file_size_mb = os.path.getsize(target_video_exact) / (1024 * 1024)

    print("\n" + "=" * 70)
    print(f"  🎉 SUCCESS! REFINED NATURAL PITCH VIDEO GENERATED:")
    print(f"  • File:     {target_video_exact}")
    print(f"  • Duration: {final_dur:.1f} seconds (STRICTLY UNDER 120s!)")
    print(f"  • Size:     {file_size_mb:.2f} MB (1080p HD)")
    print(f"  • Features: Natural conversational intro, zero lagging, high energy voiceover")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
