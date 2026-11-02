"""
Resumes generation of cloned slides (skips already generated slides 1-5,
synthesizes 6-7, renders all 7 video clips, and produces final video).
"""

import os
import sys
import subprocess
import torch

os.environ['MPLCONFIGDIR'] = os.path.abspath('reports/video_assets/mpl_cache')
sys.path.insert(0, os.getcwd())

from f5_tts.api import F5TTS
from scripts.tight_script import TIGHT_SCRIPT

OUT_AUDIO_DIR = os.path.abspath('reports/video_assets/cloned_audio')
os.makedirs(OUT_AUDIO_DIR, exist_ok=True)

ref_wav_10s = os.path.abspath('reports/video_assets/ref_user_10s.wav')
ref_text = "Hey, hello, hi, how are you? Yeah, we have participated on the meta hackathon and this we want to do all these."

def get_audio_duration(audio_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", audio_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())

def main():
    # 1. Check which slides need audio synthesis
    missing_slides = []
    for i in range(1, 8):
        wav_file = os.path.join(OUT_AUDIO_DIR, f"slide_{i:02d}.wav")
        if not os.path.exists(wav_file) or os.path.getsize(wav_file) < 10000:
            missing_slides.append(i)
        else:
            print(f"Slide {i} audio already exists: {wav_file} ({os.path.getsize(wav_file)} bytes)")
            
    if missing_slides:
        print(f"\nInitializing F5TTS on CUDA to synthesize remaining slides: {missing_slides}...")
        f5tts = F5TTS(device="cuda" if torch.cuda.is_available() else "cpu")
        
        for i in missing_slides:
            text = TIGHT_SCRIPT[i]
            out_wav = os.path.join(OUT_AUDIO_DIR, f"slide_{i:02d}.wav")
            print(f"\n[Slide {i}/7] Synthesizing cloned voice on GPU...")
            f5tts.infer(
                ref_file=ref_wav_10s,
                ref_text=ref_text,
                gen_text=text,
                file_wave=out_wav,
                speed=1.05
            )
            print(f"  Slide {i} ready: {out_wav} ({os.path.getsize(out_wav)} bytes)")
    else:
        print("\nAll 7 audio files already synthesized!")
        
    # 2. Render Video Clips for all 7 slides
    clips = []
    print("\n--- Rendering 1080p Video Clips ---")
    for i in range(1, 8):
        audio_p = os.path.join(OUT_AUDIO_DIR, f"slide_{i:02d}.wav")
        dur = get_audio_duration(audio_p)
        
        slide_img = os.path.abspath(f"reports/video_assets/slide_{i:02d}.png")
        bubble_img = os.path.abspath("reports/video_assets/presenter_bubble.png")
        out_clip = os.path.join(OUT_AUDIO_DIR, f"clip_{i:02d}.mp4")
        
        total_dur = dur + 0.35
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-t", str(total_dur), "-i", slide_img,
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
        print(f"  Rendered clip {i}: {out_clip} ({total_dur:.1f}s)")
        clips.append(out_clip)
        
    out_video = "Satyahd_Official_Pitch_Video_UserVoice.mp4"
    print("\n--- Merging into Final Presentation Video ---")
    concat_txt = os.path.join(OUT_AUDIO_DIR, "concat_list.txt")
    with open(concat_txt, "w") as f:
        for c in clips:
            abs_p = os.path.abspath(c).replace("\\", "/")
            f.write(f"file '{abs_p}'\n")
            
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        out_video
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    size_mb = os.path.getsize(out_video) / (1024 * 1024)
    total_len = sum(get_audio_duration(os.path.join(OUT_AUDIO_DIR, f"slide_{i:02d}.wav")) + 0.35 for i in range(1, 8))
    print(f"\n=======================================================")
    print(f"SUCCESS! Cloned Voice Presentation Video Complete!")
    print(f"Output: {out_video}")
    print(f"Duration: {total_len:.1f}s ({total_len/60:.2f} mins) | Size: {size_mb:.2f} MB")
    print(f"=======================================================")

if __name__ == "__main__":
    main()
