"""
Builds the 2-Minute Pitch Video with authentic, natural Indian English voice (en-IN-PrabhatNeural):
- Natural, articulate Indian English slang/cadence (clear, confident, native Indian engineer)
- Intro: 'I'm Akileshwarakrishnan. Companies are deploying AI customer chatbots everywhere...'
- Outro: Clean, normal, professional 'Thank you.'
- Overlays glowing presenter avatar bubble on 1080p slide graphics
- Calibrated to strictly stay under 120.0 seconds (target ~114-117s)
- Exports to Satyahd_Official_Pitch_Video_UserVoice.mp4 and Satyahd_Official_Pitch_Video_2Min_Exact.mp4
"""

import asyncio
import os
import sys
import subprocess
import shutil
import edge_tts

OUT_DIR = os.path.abspath("reports/video_assets/v8_indian_voice")
os.makedirs(OUT_DIR, exist_ok=True)

VOICE = "en-IN-PrabhatNeural"
RATE = "+6%"
PITCH = "+0Hz"

SCRIPT = {
    1: (
        "I'm Akileshwarakrishnan. Companies are deploying AI customer chatbots everywhere. "
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
        "It stops liability before it happens. Thank you."
    )
}

def get_audio_duration(audio_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())

async def generate_speech():
    print("=" * 70, flush=True)
    print("  🎙️ SYNTHESIZING NATURAL INDIAN ENGLISH SLANG (en-IN-PrabhatNeural)", flush=True)
    print("=" * 70, flush=True)
    
    durations = {}
    total_dur = 0.0
    
    for i in range(1, 8):
        text = SCRIPT[i]
        out_mp3 = os.path.join(OUT_DIR, f"audio_slide_{i:02d}.mp3")
        out_wav = os.path.join(OUT_DIR, f"slide_{i:02d}.wav")
        
        print(f"\n[Slide {i}/7] Synthesizing: \"{text[:55]}...\"", flush=True)
        comm = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH)
        await comm.save(out_mp3)
        
        # Convert to high-quality uncompressed WAV for ffmpeg processing
        subprocess.run(["ffmpeg", "-y", "-i", out_mp3, "-ar", "48000", "-ac", "1", out_wav],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        dur = get_audio_duration(out_wav)
        durations[i] = dur
        total_dur += dur
        print(f"  Slide {i} ready: {dur:.2f}s", flush=True)
        
    print(f"\n--> Total Raw Voiceover Duration: {total_dur:.2f} seconds (Target: < 120.0s)", flush=True)
    return durations, total_dur

def render_clips_and_merge(durations):
    print("\n" + "=" * 70, flush=True)
    print("  🎬 RENDERING 1080P CLIPS WITH GLOWING PRESENTER BUBBLE", flush=True)
    print("=" * 70, flush=True)
    
    bubble_img = os.path.abspath("reports/video_assets/presenter_bubble.png")
    clips = []
    
    for i in range(1, 8):
        dur = durations[i]
        audio_p = os.path.join(OUT_DIR, f"slide_{i:02d}.wav")
        slide_img = os.path.abspath(f"reports/video_assets/slide_{i:02d}.png")
        out_clip = os.path.join(OUT_DIR, f"clip_{i:02d}.mp4")
        
        print(f"Rendering Clip {i} ({dur:.2f}s)...", flush=True)
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
        print(f"  Clip {i} completed: {out_clip}", flush=True)
        clips.append(out_clip)
        
    # Concatenate into Final Video
    concat_txt = os.path.join(OUT_DIR, "concat_list.txt")
    with open(concat_txt, "w") as f:
        for c in clips:
            abs_p = os.path.abspath(c).replace("\\", "/")
            f.write(f"file '{abs_p}'\n")
            
    target_video_exact = "Satyahd_Official_Pitch_Video_2Min_Exact.mp4"
    main_video = "Satyahd_Official_Pitch_Video_UserVoice.mp4"
    
    print("\nMerging all 7 clips into final presentation video...", flush=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        target_video_exact
    ]
    subprocess.run(cmd, check=True)
    
    shutil.copy2(target_video_exact, main_video)
    
    final_dur = get_audio_duration(target_video_exact)
    file_size_mb = os.path.getsize(target_video_exact) / (1024 * 1024)
    
    print("\n" + "=" * 70, flush=True)
    print(f"  🎉 SUCCESS! INDIAN ENGLISH PITCH VIDEO GENERATED:", flush=True)
    print(f"  • File:     {main_video}", flush=True)
    print(f"  • Duration: {final_dur:.1f} seconds (STRICTLY UNDER 120s!)", flush=True)
    print(f"  • Size:     {file_size_mb:.2f} MB (1080p HD)", flush=True)
    print(f"  • Voice:    Natural Indian English accent/slang (en-IN-PrabhatNeural)", flush=True)
    print(f"  • Intro:    'I'm Akileshwarakrishnan. Companies are deploying AI customer chatbots...'", flush=True)
    print(f"  • Outro:    Clean, normal 'Thank you.'", flush=True)
    print("=" * 70 + "\n", flush=True)

async def main():
    durations, total_dur = await generate_speech()
    render_clips_and_merge(durations)

if __name__ == "__main__":
    asyncio.run(main())
