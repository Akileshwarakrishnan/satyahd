"""
Replaces Slide 1 audio with the normal introduction, re-renders clip_01.mp4,
and re-concatenates all 7 clips into Satyahd_Official_Pitch_Video_UserVoice.mp4.
"""

import os
import shutil
import subprocess

OUT_AUDIO_DIR = os.path.abspath('reports/video_assets/cloned_audio')
norm_wav = os.path.join(OUT_AUDIO_DIR, 'slide_01_normal.wav')
dest_wav = os.path.join(OUT_AUDIO_DIR, 'slide_01.wav')

# 1. Replace slide_01.wav
shutil.copy2(norm_wav, dest_wav)
print(f"Replaced slide_01.wav with normal intro ({os.path.getsize(dest_wav)} bytes)")

# 2. Get duration
cmd = [
    "ffprobe", "-v", "error", "-show_entries", "format=duration",
    "-of", "default=noprint_wrappers=1:nokey=1", dest_wav
]
dur = float(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip())
print(f"Slide 1 audio duration: {dur:.1f}s")

# 3. Re-render clip_01.mp4
slide_img = os.path.abspath("reports/video_assets/slide_01.png")
bubble_img = os.path.abspath("reports/video_assets/presenter_bubble.png")
out_clip = os.path.join(OUT_AUDIO_DIR, "clip_01.mp4")

total_dur = dur + 0.35
cmd = [
    "ffmpeg", "-y",
    "-loop", "1", "-t", str(total_dur), "-i", slide_img,
    "-i", bubble_img,
    "-i", dest_wav,
    "-filter_complex",
    "[0:v][1:v] overlay=1640:800 [v]; [2:a] volume=1.8,loudnorm [a]",
    "-map", "[v]",
    "-map", "[a]",
    "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "256k",
    "-shortest",
    out_clip
]
subprocess.run(cmd, check=True)
print(f"Re-rendered clip_01.mp4 ({total_dur:.1f}s)")

# 4. Re-concatenate all 7 clips
clips = [os.path.join(OUT_AUDIO_DIR, f"clip_{i:02d}.mp4") for i in range(1, 8)]
concat_txt = os.path.join(OUT_AUDIO_DIR, "concat_list.txt")
with open(concat_txt, "w") as f:
    for c in clips:
        abs_p = os.path.abspath(c).replace("\\", "/")
        f.write(f"file '{abs_p}'\n")
        
out_video = "Satyahd_Official_Pitch_Video_UserVoice.mp4"
cmd = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_txt,
    "-c", "copy",
    out_video
]
subprocess.run(cmd, check=True)

size_mb = os.path.getsize(out_video) / (1024 * 1024)
print(f"\nSUCCESS! Updated video saved: {out_video} ({size_mb:.2f} MB)")
