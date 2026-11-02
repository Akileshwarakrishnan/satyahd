"""
Builds the condensed, punchy (~2.5 min) pitch video:
- Uses en-IN-PrabhatNeural (energetic 21yo Indian male engineer)
- Boosts audio volume with volume=2.0 and loudnorm filter
- Overlays the presenter avatar bubble with glowing ring
- Exports full standalone master narration audio for talking head tools
"""

import os
import sys
sys.path.insert(0, os.getcwd())
import asyncio
import subprocess
import edge_tts
from scripts.tight_script import TIGHT_SCRIPT

OUT_DIR = "reports/video_assets/v2_indian"
os.makedirs(OUT_DIR, exist_ok=True)

VOICE = "en-IN-PrabhatNeural"
RATE = "+14%"
PITCH = "+2Hz"
VOLUME = "+50%"

async def generate_audio():
    print("Generating loud, youthful Indian voice audio (en-IN-PrabhatNeural)...")
    full_text_list = []
    
    for i in range(1, 8):
        text = TIGHT_SCRIPT[i]
        full_text_list.append(text)
        out_mp3 = os.path.join(OUT_DIR, f"audio_slide_{i:02d}.mp3")
        comm = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, volume=VOLUME)
        await comm.save(out_mp3)
        print(f"  Slide {i} ready: {out_mp3}")
        
    # Also generate full concatenated master narration audio
    master_text = " ... ".join(full_text_list)
    master_mp3 = "satyahd_full_pitch_indian_voice.mp3"
    comm_master = edge_tts.Communicate(master_text, VOICE, rate=RATE, pitch=PITCH, volume=VOLUME)
    await comm_master.save(master_mp3)
    print(f"Master voiceover exported: {master_mp3}")

def get_audio_duration(audio_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())

def render_slide_clip(slide_num, duration):
    slide_img = os.path.abspath(f"reports/video_assets/slide_{slide_num:02d}.png")
    audio_file = os.path.abspath(os.path.join(OUT_DIR, f"audio_slide_{slide_num:02d}.mp3"))
    bubble_img = os.path.abspath("reports/video_assets/presenter_bubble.png")
    out_clip = os.path.abspath(os.path.join(OUT_DIR, f"clip_slide_{slide_num:02d}.mp4"))
    
    total_dur = duration + 0.35
    
    # Apply audio filter: volume boost + normalization so speech is loud and clear
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-t", str(total_dur), "-i", slide_img,
        "-i", bubble_img,
        "-i", audio_file,
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
    print(f"Concatenated final video: {output_video}")

def main():
    asyncio.run(generate_audio())
    
    clips = []
    print("\nRendering video clips with loud audio and presenter bubble...")
    for i in range(1, 8):
        audio_p = os.path.join(OUT_DIR, f"audio_slide_{i:02d}.mp3")
        dur = get_audio_duration(audio_p)
        clip_p = render_slide_clip(i, dur)
        clips.append(clip_p)
        
    out_video = "Satyahd_Pitch_Video_IndianVoice_Loud.mp4"
    print("\nMerging into final 1080p video...")
    concatenate_clips(clips, out_video)
    
    size_mb = os.path.getsize(out_video) / (1024 * 1024)
    total_len = sum(get_audio_duration(os.path.join(OUT_DIR, f"audio_slide_{i:02d}.mp3")) + 0.35 for i in range(1, 8))
    print(f"\nSUCCESS! High-volume Indian voice pitch video created: {out_video}")
    print(f"Duration: {total_len:.1f}s ({total_len/60:.2f} mins) | Size: {size_mb:.2f} MB")

if __name__ == "__main__":
    main()
