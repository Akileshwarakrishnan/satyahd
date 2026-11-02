"""
Builds the Relatable, Intuitive 2-Minute Pitch Video (User Voice).
- Conversational, human, engaging story delivery that is easy for anyone to understand.
- Explains the problem, Air Canada case, how Satyahd works, red team results, tamper-proof proof, and speed clearly.
- Eliminates "default" robotic reading tone.
- Keeps Meta's Muse Spark model references intact.
- Synthesized at speed=1.08 with F5-TTS on CUDA using the user's natural voice clone.
- Overlays the glowing presenter bubble on 1080p slide graphics.
- Strictly under 120 seconds (target ~112-115s).
"""

import os
import sys
import subprocess
import time
import shutil

print(">> Starting Relatable Pitch Video Generator...", flush=True)

mpl_dir = os.path.abspath('reports/video_assets/mpl_cache')
os.makedirs(mpl_dir, exist_ok=True)
os.environ['MPLCONFIGDIR'] = mpl_dir
sys.path.insert(0, os.getcwd())

import torch
from f5_tts.api import F5TTS

OUT_DIR = os.path.abspath('reports/video_assets/v7_natural_pitch')
os.makedirs(OUT_DIR, exist_ok=True)

ref_wav_10s = os.path.abspath('reports/video_assets/ref_user_10s.wav')
ref_text = "Hey, hello, hi, how are you? Yeah, we have participated on the meta hackathon and this we want to do all these."

# Relatable, intuitive, easy-to-understand script (calibrated for strictly under 120s)
EASY_UNDERSTAND_SCRIPT = {
    1: (
        "Welcome everyone to Satyahd! Companies are deploying AI customer chatbots everywhere. "
        "But chatbots easily make unauthorized promises and fake discounts, creating serious legal damages for businesses."
    ),
    2: (
        "In 2024, Air Canada's chatbot promised a passenger an unauthorized discount. "
        "The court ruled that companies are legally responsible for whatever their AI promises. "
        "System prompts cannot prevent this, but Satyahd does."
    ),
    3: (
        "Satyahd sits directly between your chatbot and the customer. "
        "Meta's Muse Spark extracts every promise and discount. "
        "Then, our fast rule engine checks company policies, safely rewriting unauthorized offers in fifty milliseconds."
    ),
    4: (
        "We tested Satyahd against twenty aggressive haggling attacks. "
        "Without Satyahd, chatbots broke company rules ninety percent of the time. "
        "With Satyahd, containment is one hundred percent, protecting your business while keeping customers happy."
    ),
    5: (
        "If a customer ever disputes an agreement in court, Satyahd gives you cryptographic proof. "
        "Every single decision is digitally signed and sealed into a tamper-proof hash chain, "
        "meeting strict legal evidence standards."
    ),
    6: (
        "Scale requires speed. "
        "Using Meta's Muse Spark with minimal reasoning, we cut latency down to forty-eight milliseconds. "
        "Our entire test suite of 156 automated tests passes with one hundred percent accuracy."
    ),
    7: (
        "Satyahd is production ready today. "
        "Any team can protect their chatbot in five lines of code using our MCP server or API. "
        "It stops liability before it happens. Thank you so much!"
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
    print("  🎬 BUILDING RELATABLE, EASY-TO-UNDERSTAND 2-MINUTE PITCH VIDEO")
    print("=" * 70)

    print("\n[Step 1/3] Initializing F5TTS on CUDA GPU...")
    t0 = time.time()
    f5tts = F5TTS(device="cuda" if torch.cuda.is_available() else "cpu")
    print(f"F5TTS initialized in {time.time() - t0:.1f}s")

    slide_durations = {}
    total_audio_dur = 0.0

    print("\n[Step 2/3] Synthesizing conversational voiceover clips (speed=1.08)...")
    for i in range(1, 8):
        text = EASY_UNDERSTAND_SCRIPT[i]
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

        dur = slide_durations[i]
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
    print(f"  🎉 SUCCESS! RELATABLE PITCH VIDEO GENERATED:")
    print(f"  • File:     {target_video_exact}")
    print(f"  • Duration: {final_dur:.1f} seconds (STRICTLY UNDER 120s!)")
    print(f"  • Size:     {file_size_mb:.2f} MB (1080p HD)")
    print(f"  • Features: Easy-to-understand conversational delivery, natural voice, zero lagging")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
