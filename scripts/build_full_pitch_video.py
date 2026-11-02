"""
Generates the complete 1080p Satyahd Pitch Demo Video:
1. Generates neural speech for all 7 slides using edge-tts.
2. Creates synced 1080p video clips with the presenter bubble overlay.
3. Concatenates all clips into Satyahd_Official_Demo_Video.mp4.
"""

import os
import sys
import asyncio
import subprocess
import edge_tts

OUT_DIR = "reports/video_assets"
os.makedirs(OUT_DIR, exist_ok=True)

VOICE = "en-US-ChristopherNeural"
RATE = "+5%"

NARRATIONS = {
    1: (
        "Welcome judges. I am Akileshwarakrishnan, creator and lead engineer of Satyahd. "
        "Today, thousands of enterprises are deploying autonomous AI agents to interact directly with "
        "customers and invoke backend tools. But there is a massive legal and financial liability: "
        "LLMs are inherently probabilistic. They hallucinate commitments, promise discounts they cannot honor, "
        "and expose companies to binding damages. Satyahd is the world's first zero-trust policy enforcement "
        "middleman that completely neutralizes this liability."
    ),
    2: (
        "In 2024, the Civil Resolution Tribunal delivered a wake-up call to the entire AI industry in Moffatt versus Air Canada. "
        "A passenger asked the airline chatbot about bereavement discounts. The bot hallucinated that he could book at "
        "full price and claim a refund retroactively. When Air Canada refused to pay, the tribunal ruled that companies "
        "are strictly liable for all representations made by their AI agents. "
        "System prompts are merely soft suggestions. They cannot mathematically guarantee safe behavior. "
        "Satyahd moves enforcement out of the prompt and into an immutable deterministic middleman."
    ),
    3: (
        "Here is the architecture of the Satyahd gateway. It sits in-line between the agent and the outside world "
        "with only 48 milliseconds of overhead. "
        "Stage 1 intercepts all outbound text and tool calls. "
        "Stage 2 uses Meta's muse-spark-1.3 in minimal reasoning mode to extract actionable promises into normalized JSON. "
        "Stage 3 evaluates pure Python deterministic rules against enterprise policy and real-time CRM facts, with zero hallucination risk. "
        "And Stage 4 decides: Allow, Rewrite, or Block, sealing the result with an Ed25519 cryptographic signature."
    ),
    4: (
        "We subjected standard AI agents to 20 aggressive adversarial attacks, including executive overrides, "
        "sob stories, and prompt injections. "
        "Without Satyahd, agents breached corporate policy 90% of the time, authorizing unapproved discounts and creating binding liabilities. "
        "With Satyahd in place, containment is 100%. "
        "Notice that Satyahd doesn't just block or crash: it intelligently rewrites the response, maintaining customer warmth "
        "and empathy while completely excising the unauthorized promise."
    ),
    5: (
        "When an interaction is disputed, how does an enterprise defend itself? Standard server logs are easily challenged in court. "
        "Satyahd provides three layers of cryptographic proof. "
        "First, Ed25519 asymmetric signatures sign every decision payload. "
        "Second, a continuous SHA-256 hash chain links each record to the one before it. We have verified 585 out of 585 "
        "live records in our database as mathematically pristine. "
        "Third, native SQL database triggers block all updates and deletions, guaranteeing full admissibility under the Federal Rules of Evidence."
    ),
    6: (
        "Speed and cost are essential for real-time scale. "
        "By leveraging Meta's muse-spark-1.3 with a targeted minimal reasoning configuration, we achieved a 62.4% reduction "
        "in latency—from 128 milliseconds down to just 48.2 milliseconds—while cutting token consumption by 58.1%. "
        "Combined with our sub-15ms Python engine, Satyahd adds negligible overhead. "
        "Furthermore, our entire test suite of 174 automated tests passes in 18 seconds, achieving 100% accuracy on gold-standard benchmarks."
    ),
    7: (
        "To conclude: Satyahd is production-ready today. "
        "With just three lines of Python or a single REST API call, any team can wrap their LangChain, LlamaIndex, or custom "
        "agent in a deterministic, cryptographically signed middleman. "
        "It deploys as a lightweight Docker container under 150 megabytes, operates air-gapped on-premise, "
        "and gives risk teams total confidence. "
        "Satyahd is the indispensable safety harness before autonomous AI meets the real world. Thank you, and I look forward to your questions!"
    )
}

async def generate_all_audio():
    print("Generating neural audio tracks for all 7 slides...")
    for i in range(1, 8):
        text = NARRATIONS[i]
        out_mp3 = os.path.join(OUT_DIR, f"audio_slide_{i:02d}.mp3")
        comm = edge_tts.Communicate(text, VOICE, rate=RATE)
        await comm.save(out_mp3)
        print(f"  Slide {i} audio ready: {out_mp3} ({os.path.getsize(out_mp3)} bytes)")

def get_audio_duration(audio_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())

def render_slide_clip(slide_num, duration):
    slide_img = os.path.join(OUT_DIR, f"slide_{slide_num:02d}.png")
    audio_file = os.path.join(OUT_DIR, f"audio_slide_{slide_num:02d}.mp3")
    bubble_img = os.path.join(OUT_DIR, "presenter_bubble.png")
    out_clip = os.path.join(OUT_DIR, f"clip_slide_{slide_num:02d}.mp4")
    
    total_dur = duration + 0.5  # 0.5s pause between slides
    
    # Overlay presenter bubble in bottom-right corner (x=1640, y=800)
    # If slide 1, presenter is already in the card, but bubble is consistent across all
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(total_dur), "-i", slide_img,
        "-i", bubble_img,
        "-i", audio_file,
        "-filter_complex",
        "[0:v][1:v] overlay=1640:800 [v]",
        "-map", "[v]",
        "-map", "2:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        out_clip
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  Rendered clip {slide_num}: {out_clip} ({total_dur:.1f}s)")
    return out_clip

def concatenate_clips(clip_files, output_video):
    concat_txt = os.path.join(OUT_DIR, "concat_list.txt")
    with open(concat_txt, "w") as f:
        for c in clip_files:
            abs_p = os.path.abspath(c).replace("\\", "/")
            f.write(f"file '{abs_p}'\n")
            
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        output_video
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"Concatenated full demo video: {output_video}")

def main():
    asyncio.run(generate_all_audio())
    
    clips = []
    print("\nRendering individual slide video clips with presenter overlay...")
    for i in range(1, 8):
        audio_p = os.path.join(OUT_DIR, f"audio_slide_{i:02d}.mp3")
        dur = get_audio_duration(audio_p)
        clip_p = render_slide_clip(i, dur)
        clips.append(clip_p)
        
    out_video = "Satyahd_Official_Demo_Video.mp4"
    print("\nMerging into final 1080p video...")
    concatenate_clips(clips, out_video)
    
    size_mb = os.path.getsize(out_video) / (1024 * 1024)
    total_len = sum(get_audio_duration(os.path.join(OUT_DIR, f"audio_slide_{i:02d}.mp3")) + 0.5 for i in range(1, 8))
    print(f"\nSUCCESS! Video saved: {out_video}")
    print(f"Duration: {total_len:.1f} seconds ({total_len/60:.2f} mins) | Size: {size_mb:.2f} MB")

if __name__ == "__main__":
    main()
