import asyncio
import edge_tts
import os
import subprocess

async def test_prabhat():
    text = "I'm Akileshwarakrishnan. Companies are deploying AI customer chatbots everywhere. But chatbots easily make unauthorized promises and fake discounts, creating serious legal damages for businesses."
    comm = edge_tts.Communicate(text, "en-IN-PrabhatNeural", rate="+6%", pitch="+0Hz")
    out_file = "reports/video_assets/test_prabhat_slide1.mp3"
    await comm.save(out_file)
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", out_file]).decode().strip())
    print(f"Generated {out_file}: {dur:.2f}s, {os.path.getsize(out_file)} bytes")

if __name__ == "__main__":
    asyncio.run(test_prabhat())
