"""High-Definition Presentation Video Generator with Creator Headshot (R-707).

Features:
- Creator Portrait Integration: Features Akileshwarakrishnan prominently on the title slide
  and as a presenter badge across presentation slides.
- Crisp 1080p Typography using Windows TrueType fonts (Segoe UI / Segoe UI Bold).
- Studio Neural Voiceover narration via edge-tts.
- Side-by-side terminal simulation showing Unprotected vs. Satyahd-Protected bot.
- Encoded with FFmpeg into a complete, professional, ready-to-submit 1080p MP4 video.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "reports" / "video_assets"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FINAL_VIDEO = BASE_DIR / "satyahd_demo_video.mp4"
PHOTO_PATH = OUTPUT_DIR / "presenter.jpg"

# 1080p Canvas
WIDTH = 1920
HEIGHT = 1080

# Dark Mode Color Palette
BG_DARK = (11, 15, 25)           # Deep obsidian slate
CARD_BG = (23, 32, 51)           # Elevated glassmorphism card
CARD_BORDER = (46, 64, 99)       # Subtle border
TEXT_WHITE = (255, 255, 255)     # Primary text
TEXT_GRAY = (148, 163, 184)      # Secondary text
TEXT_MUTED = (100, 116, 139)     # Tertiary captions
CYAN_ACCENT = (6, 182, 212)      # Primary tech cyan
GREEN_ACCENT = (34, 197, 94)     # Success / Allowed green
RED_ACCENT = (239, 68, 68)       # Violation / Warning red
PURPLE_ACCENT = (168, 85, 247)   # Meta Purple
GOLD_ACCENT = (245, 158, 11)     # Badge gold

# Fonts
FONT_TITLE = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 52)
FONT_SUBTITLE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 26)
FONT_CARD_TITLE = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 26)
FONT_CARD_BODY = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
FONT_BADGE = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 16)
FONT_CODE = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 20)
FONT_NAME = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 32)
FONT_ROLE = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)


def get_rounded_photo(photo_path: Path, size: tuple[int, int], radius: int = 24) -> Image.Image:
    """Loads, resizes, and crops user portrait into a rounded rectangle with smooth border."""
    if not photo_path.exists():
        # Fallback colored box if photo not found
        img = Image.new("RGB", size, (30, 41, 59))
        return img

    raw = Image.open(photo_path).convert("RGBA")
    # Smart center crop to target aspect ratio
    raw_cropped = ImageOps.fit(raw, size, centering=(0.5, 0.35))

    # Create rounded corner mask
    mask = Image.new("L", size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.rounded_rectangle([0, 0, size[0], size[1]], radius=radius, fill=255)

    rounded = Image.new("RGBA", size, (0, 0, 0, 0))
    rounded.paste(raw_cropped, (0, 0), mask=mask)
    return rounded


SLIDES = [
    {
        "id": "slide_1",
        "type": "intro",
        "title": "SATYAHD",
        "subtitle": "Universal Trust Layer & Runtime Guardrail for AI Chatbots",
        "badge": "META AI HACKATHON 2026",
        "script": (
            "Hi everyone! I am Akileshwarakrishnan, and I am excited to present Satyahd for the Meta AI Hackathon. "
            "In 2024, a Canadian tribunal held Air Canada legally liable after their customer service chatbot hallucinated "
            "an unauthorized bereavement discount. Every company deploying AI faces this exact financial liability. "
            "Prompt engineering cannot solve this, and an LLM cannot reliably guard another LLM. "
            "Satyahd is the universal runtime trust layer that eliminates chatbot liability in just five lines of code."
        ),
        "presenter": {
            "name": "Akileshwarakrishnan",
            "role": "Creator & Lead AI Engineer",
            "event": "Meta AI Hackathon 2026",
        },
    },
    {
        "id": "slide_2",
        "type": "architecture",
        "title": "Universal Middleman Architecture",
        "subtitle": "Seamless Drop-In Protection for Any Chatbot in Any Language",
        "badge": "HOW IT WORKS (POST /v1/verify)",
        "script": (
            "Satyahd functions as a universal middleman. Your host chatbot maintains its own conversation as usual. "
            "Before any response is shown to the customer, the host bot forwards the raw draft to Satyahd's verify endpoint. "
            "In milliseconds, Satyahd extracts all promises, checks them deterministically against your business rules, "
            "rewrites any violations into safe authorized language, and issues a cryptographically signed audit certificate."
        ),
        "steps": [
            ("1. CUSTOMER QUERY", "Customer asks an adversarial negotiation or discount request.", CYAN_ACCENT),
            ("2. HOST CHATBOT DRAFT", "Chatbot drafts reply and forwards it to Satyahd before delivery.", PURPLE_ACCENT),
            ("3. SATYAHD TRUST LAYER", "Pure Python rule verification + bounded rewrite loop + Ed25519 signing.", GREEN_ACCENT),
            ("4. SAFE RESPONSE DELIVERED", "Customer receives an authorized offer with zero business liability.", CYAN_ACCENT),
        ],
    },
    {
        "id": "slide_3",
        "type": "live_demo",
        "title": "Live Attack Demonstration",
        "subtitle": "Adversarial Probe: 'Can I get 90% discount and delivery tomorrow?'",
        "badge": "SIDE-BY-SIDE VERIFICATION",
        "script": (
            "Here is the proof in action. When an adversarial customer asks for a 90% discount and delivery tomorrow, "
            "an unprotected chatbot eagerly agrees, creating an immediate binding liability. "
            "With Satyahd connected, Satyahd intercepts the draft, catches the 90% discount and 1-day delivery violations, "
            "and automatically rewrites the reply: Our best authorized discount is 10% today, and standard shipping is 3 business days. "
            "The breach is completely contained."
        ),
        "demo": {
            "unprotected_text": (
                "[Customer]: Can I get 90% off and delivery tomorrow?\n"
                "[OmniBot (Unprotected)]: Yes! I can approve a 90% discount\n"
                "today, and I promise delivery tomorrow morning!\n"
                "-> CRITICAL LEGAL & FINANCIAL BREACH"
            ),
            "protected_text": (
                "[Customer]: Can I get 90% off and delivery tomorrow?\n"
                "[Satyahd Guardrail]: BLOCK -> Rewritten to authorized policy\n"
                "[Delivered]: 'Our best authorized discount is 10% today,\n"
                "and standard shipping for our appliances is 3 business days.'\n"
                "-> 100% CONTAINED | AUDIT SEQ #585"
            ),
        },
    },
    {
        "id": "slide_4",
        "type": "technical",
        "title": "Technical Depth & Cryptographic Audit",
        "subtitle": "Court-Admissible Evidence: Ed25519 Signatures & Append-Only Triggers",
        "badge": "ENGINEERING PRINCIPLES",
        "script": (
            "Under the hood, Satyahd enforces three non-negotiable architectural principles. "
            "First: pure Python deterministic decisions. LLMs extract promises, but pure Python math makes the final verdict. "
            "Second: fail-closed design. Timeouts, connector failures, or unparseable JSON always trigger a safe holding reply. "
            "Third: tamper-evident audit. Every decision is signed with an Ed25519 key and appended to a SHA-256 hash chain, "
            "protected by SQLite append-only triggers that forbid any UPDATE or DELETE operations."
        ),
        "principles": [
            ("1. PURE PYTHON DECISION ENGINE", "LLMs extract commitments; deterministic mathematical code renders the verdict.", CYAN_ACCENT),
            ("2. FAIL-CLOSED ARCHITECTURE", "Provider timeouts, bad JSON, or confidence < 0.60 force REVIEW or BLOCK, never ALLOW.", PURPLE_ACCENT),
            ("3. ED25519 + SHA-256 HASH CHAIN", "Tamper-evident cryptographic ledger with SQLite triggers and deterministic replay.", GREEN_ACCENT),
        ],
    },
    {
        "id": "slide_5",
        "type": "metrics",
        "title": "Powered by Meta Models & Rigorous Testing",
        "subtitle": "Sub-50ms Latency via muse-spark-1.3 Minimal Reasoning & SAM 3.1 Verification",
        "badge": "174 TESTS PASSING | 100% CONTAINMENT",
        "script": (
            "Satyahd leverages Meta's muse-spark-1.3 with minimal reasoning effort for sub-50ms extraction, "
            "reducing token costs by 58%, and Meta's SAM 3.1 for appliance damage verification. "
            "We verified Satyahd across 174 automated tests, achieving 100% accuracy on our 30-case evaluation suite "
            "and 100% containment across 20 adversarial red-team haggling probes. "
            "Satyahd turns uncontrollable chatbots into legally safe, enterprise-ready AI agents. Thank you!"
        ),
        "stats": [
            ("META INFERENCE", "muse-spark-1.3 with minimal reasoning (62% faster)", PURPLE_ACCENT),
            ("TEST SUITE", "174 of 174 automated tests passing in 18 seconds", GREEN_ACCENT),
            ("ACCURACY BENCHMARK", "30 of 30 evaluation cases correct (100% accuracy)", CYAN_ACCENT),
            ("RED-TEAM DEFENSE", "20 of 20 adversarial attacks contained (0 leaks)", GREEN_ACCENT),
        ],
    },
]


def render_intro_slide(slide: dict, output_path: Path):
    """Renders high-impact Title Slide featuring Akileshwarakrishnan prominently."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Top cyan border line
    draw.rectangle([0, 0, WIDTH, 8], fill=CYAN_ACCENT)

    # Left Section: Project Info
    # Badge
    draw.rounded_rectangle([100, 100, 480, 145], radius=8, fill=CARD_BG, outline=CYAN_ACCENT, width=2)
    draw.text((120, 110), slide["badge"], fill=CYAN_ACCENT, font=FONT_BADGE)

    # Title & Subtitle
    draw.text((100, 180), slide["title"], fill=TEXT_WHITE, font=FONT_TITLE)
    draw.text((100, 260), slide["subtitle"], fill=TEXT_GRAY, font=FONT_SUBTITLE)
    draw.line([(100, 320), (1050, 320)], fill=CARD_BORDER, width=2)

    # Left Cards: Problem & Solution Callouts
    # Problem Callout
    draw.rounded_rectangle([100, 360, 1050, 520], radius=16, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw.rectangle([100, 360, 112, 520], fill=RED_ACCENT)
    draw.text((140, 385), "THE AIR CANADA PROBLEM", fill=RED_ACCENT, font=FONT_CARD_TITLE)
    draw.text(
        (140, 430),
        "Civil Resolution Tribunal held Air Canada legally liable when its customer chatbot\nhallucinated unauthorized refund policies. Unchecked bots cost real money.",
        fill=TEXT_WHITE,
        font=FONT_CARD_BODY,
    )

    # Solution Callout
    draw.rounded_rectangle([100, 560, 1050, 720], radius=16, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw.rectangle([100, 560, 112, 720], fill=GREEN_ACCENT)
    draw.text((140, 585), "THE SATYAHD SOLUTION", fill=GREEN_ACCENT, font=FONT_CARD_TITLE)
    draw.text(
        (140, 630),
        "A drop-in universal middleman trust layer. Evaluates raw chatbot drafts in milliseconds,\nblocks policy breaches, rewrites safe replies, and commits signed audit logs.",
        fill=TEXT_WHITE,
        font=FONT_CARD_BODY,
    )

    # Right Section: Presenter Profile Card
    draw.rounded_rectangle([1150, 100, 1820, 850], radius=24, fill=CARD_BG, outline=CYAN_ACCENT, width=3)

    # Presenter Photo (Rounded)
    photo = get_rounded_photo(PHOTO_PATH, size=(580, 520), radius=18)
    img.paste(photo, (1195, 140), mask=photo)

    # Presenter Bio Details
    pres = slide["presenter"]
    draw.text((1195, 680), pres["name"], fill=TEXT_WHITE, font=FONT_NAME)
    draw.text((1195, 730), pres["role"], fill=CYAN_ACCENT, font=FONT_ROLE)
    draw.text((1195, 775), pres["event"], fill=GOLD_ACCENT, font=FONT_BADGE)

    # Footer
    draw.line([(100, HEIGHT - 100), (WIDTH - 100, HEIGHT - 100)], fill=CARD_BORDER, width=1)
    draw.text((100, HEIGHT - 70), "Satyahd • Meta AI Hackathon 2026", fill=TEXT_MUTED, font=FONT_CARD_BODY)
    draw.text((WIDTH - 420, HEIGHT - 70), "Runtime Guardrail & Audit Layer", fill=CYAN_ACCENT, font=FONT_CARD_BODY)

    img.save(output_path, quality=95)
    print(f"  -> Generated slide frame: {output_path.name}")


def render_content_slide(slide: dict, output_path: Path):
    """Renders technical slides with a sleek Presenter PiP avatar in the top-right corner."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Top cyan border line
    draw.rectangle([0, 0, WIDTH, 8], fill=CYAN_ACCENT)

    # Badge & Title
    draw.rounded_rectangle([100, 60, 480, 105], radius=8, fill=CARD_BG, outline=CYAN_ACCENT, width=2)
    draw.text((120, 70), slide["badge"], fill=CYAN_ACCENT, font=FONT_BADGE)
    draw.text((100, 130), slide["title"], fill=TEXT_WHITE, font=FONT_TITLE)
    draw.text((100, 205), slide["subtitle"], fill=TEXT_GRAY, font=FONT_SUBTITLE)
    draw.line([(100, 260), (1450, 260)], fill=CARD_BORDER, width=2)

    # Top Right Presenter PiP Avatar
    pip_size = (180, 180)
    pip_x = WIDTH - 280
    pip_y = 50
    draw.rounded_rectangle([pip_x - 10, pip_y - 10, pip_x + pip_size[0] + 10, pip_y + pip_size[1] + 50], radius=16, fill=CARD_BG, outline=CYAN_ACCENT, width=2)
    pip_photo = get_rounded_photo(PHOTO_PATH, size=pip_size, radius=12)
    img.paste(pip_photo, (pip_x, pip_y), mask=pip_photo)
    draw.text((pip_x + 10, pip_y + pip_size[1] + 15), "Akileshwarakrishnan", fill=TEXT_WHITE, font=FONT_BADGE)

    # Main Content Area based on slide type
    stype = slide.get("type")

    if stype == "live_demo":
        # Side-by-side terminal windows
        demo = slide["demo"]
        # Left Window: Unprotected (Red)
        draw.rounded_rectangle([100, 300, 930, 850], radius=16, fill=CARD_BG, outline=RED_ACCENT, width=2)
        # Window Header Bar
        draw.rectangle([100, 300, 930, 350], fill=(20, 25, 35))
        draw.ellipse([120, 320, 135, 335], fill=(239, 68, 68))
        draw.ellipse([145, 320, 160, 335], fill=(234, 179, 8))
        draw.ellipse([170, 320, 185, 335], fill=(34, 197, 94))
        draw.text((220, 315), "UNPROTECTED CHATBOT (Without Satyahd)", fill=RED_ACCENT, font=FONT_CARD_TITLE)
        # Terminal Content
        draw.text((130, 380), demo["unprotected_text"], fill=TEXT_WHITE, font=FONT_CODE)

        # Right Window: Protected (Green)
        draw.rounded_rectangle([990, 300, 1820, 850], radius=16, fill=CARD_BG, outline=GREEN_ACCENT, width=2)
        # Window Header Bar
        draw.rectangle([990, 300, 1820, 350], fill=(20, 25, 35))
        draw.ellipse([1010, 320, 1025, 335], fill=(239, 68, 68))
        draw.ellipse([1035, 320, 1050, 335], fill=(234, 179, 8))
        draw.ellipse([1060, 320, 1075, 335], fill=(34, 197, 94))
        draw.text((1110, 315), "PROTECTED CHATBOT (With Satyahd Plugin)", fill=GREEN_ACCENT, font=FONT_CARD_TITLE)
        # Terminal Content
        draw.text((1020, 380), demo["protected_text"], fill=TEXT_WHITE, font=FONT_CODE)

    else:
        # Standard Cards Layout (Architecture, Principles, Metrics)
        cards = slide.get("steps") or slide.get("principles") or slide.get("stats") or []
        y_pos = 300
        card_h = 120
        gap = 25

        for i, (head, desc, col) in enumerate(cards):
            y = y_pos + i * (card_h + gap)
            draw.rounded_rectangle([100, y, WIDTH - 100, y + card_h], radius=14, fill=CARD_BG, outline=CARD_BORDER, width=2)
            draw.rectangle([100, y, 112, y + card_h], fill=col)
            draw.text((140, y + 20), head, fill=col, font=FONT_CARD_TITLE)
            draw.text((140, y + 65), desc, fill=TEXT_WHITE, font=FONT_CARD_BODY)

    # Footer
    draw.line([(100, HEIGHT - 80), (WIDTH - 100, HEIGHT - 80)], fill=CARD_BORDER, width=1)
    draw.text((100, HEIGHT - 55), "Satyahd • Meta AI Hackathon 2026", fill=TEXT_MUTED, font=FONT_CARD_BODY)
    draw.text((WIDTH - 420, HEIGHT - 55), "Universal Trust Middleware", fill=CYAN_ACCENT, font=FONT_CARD_BODY)

    img.save(output_path, quality=95)
    print(f"  -> Generated slide frame: {output_path.name}")


async def generate_voiceover(text: str, output_path: Path):
    """Generates natural studio voiceover using edge-tts."""
    import edge_tts
    # Natural American male voice
    voice = "en-US-ChristopherNeural"
    communicate = edge_tts.Communicate(text, voice=voice, rate="+4%")
    await communicate.save(str(output_path))
    print(f"  -> Generated voiceover: {output_path.name}")


def get_audio_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(res.stdout.strip())
    except Exception:
        return 18.0


def build_video():
    print("\n" + "=" * 70)
    print(" 🎬 Satyahd Professional Demo Video Generator (With Creator Headshot)")
    print("=" * 70)

    segments = []

    for i, slide in enumerate(SLIDES):
        print(f"\n[Slide {i+1}/{len(SLIDES)}] Rendering {slide['id']}...")
        img_path = OUTPUT_DIR / f"{slide['id']}.png"
        audio_path = OUTPUT_DIR / f"{slide['id']}.mp3"
        seg_path = OUTPUT_DIR / f"{slide['id']}.mp4"

        # 1. Render frame
        if slide["type"] == "intro":
            render_intro_slide(slide, img_path)
        else:
            render_content_slide(slide, img_path)

        # 2. Generate voiceover
        asyncio.run(generate_voiceover(slide["script"], audio_path))

        # 3. Audio duration + padding
        duration = get_audio_duration(audio_path) + 0.6
        print(f"  -> Audio Duration: {duration:.2f}s")

        # 4. Render video segment with FFmpeg
        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-i", str(img_path),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(duration),
            "-shortest",
            str(seg_path),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        segments.append(seg_path)

    # 5. Concatenate all segments into the final 1080p MP4 video
    print("\n[Final Step] Assembling all segments into full 1080p video...")
    concat_list = OUTPUT_DIR / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for s in segments:
            f.write(f"file '{s.as_posix()}'\n")

    cmd_concat = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(FINAL_VIDEO),
    ]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    print("\n" + "=" * 70)
    print(f" 🎉 SUCCESS! Professional Presentation Video Created:")
    print(f" 📁 Path: {FINAL_VIDEO}")
    file_size_mb = FINAL_VIDEO.stat().st_size / (1024 * 1024)
    print(f" 📦 Size: {file_size_mb:.2f} MB")
    total_dur = get_audio_duration(FINAL_VIDEO)
    print(f" ⏱️ Duration: {total_dur:.1f} seconds (~{int(total_dur // 60)}m {int(total_dur % 60)}s)")
    print("=" * 70)


if __name__ == "__main__":
    build_video()
