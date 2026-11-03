"""
Builds a high-impact 30-Second Motion Graphics Animation Video for Satyahd.
- 1080p Full HD (1920x1080 @ 30fps = exactly 900 frames, 30.00s)
- 11x Design System aesthetic: deep obsidian (#050505), champagne (#d6b4a3), bronze (#643414), live green (#00e575)
- Continuous Marquee Hero Ticker, 3D perspective cyber grid, rotating radar sweep, glowing lock shield
- Animated split-screen attack vs bounded rewrite, 3D blockchain nodes with Ed25519 digital signature
- Synchronized voiceover with high-tech electronic synth soundscape
"""

import os
import sys
import math
import asyncio
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2

# Ensure output directory exists
OUT_DIR = os.path.abspath("reports/video_assets/v9_30s_animation")
os.makedirs(OUT_DIR, exist_ok=True)

FINAL_VIDEO = os.path.abspath("Satyahd_30s_Official_Animation.mp4")

WIDTH, HEIGHT = 1920, 1080
FPS = 30
TOTAL_FRAMES = 900  # Exactly 30.00 seconds
SAMPLE_RATE = 44100

FONT_DIR = r"C:\Windows\Fonts"
FONT_TITLE = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 68)
FONT_SUBTITLE = ImageFont.truetype(os.path.join(FONT_DIR, "segoeui.ttf"), 30)
FONT_HEADING = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 44)
FONT_BODY = ImageFont.truetype(os.path.join(FONT_DIR, "segoeui.ttf"), 24)
FONT_BODY_BOLD = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 24)
FONT_MONO = ImageFont.truetype(os.path.join(FONT_DIR, "consolab.ttf"), 22)
FONT_MONO_SMALL = ImageFont.truetype(os.path.join(FONT_DIR, "consolab.ttf"), 16)
FONT_BADGE = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 18)
FONT_TICKER = ImageFont.truetype(os.path.join(FONT_DIR, "consolab.ttf"), 15)

# Color constants (11x Design System)
C_BLACK = (5, 5, 5)
C_SURFACE = (13, 13, 13)
C_SURFACE_ELEVATED = (21, 21, 21)
C_BORDER = (37, 37, 37)
C_CHAMPAGNE = (214, 180, 163)
C_BRONZE = (100, 52, 20)
C_TERRACOTTA = (132, 83, 59)
C_TITANIUM = (206, 192, 184)
C_GREEN = (0, 229, 117)
C_RED = (206, 58, 66)
C_CYAN = (0, 210, 255)
C_WHITE = (255, 255, 255)


# -----------------------------------------------------------------------------
# 1. AUDIO SYNTHESIS & SOUND DESIGN (30.00s Master Track)
# -----------------------------------------------------------------------------

async def generate_speech():
    """Generates 5 distinct voiceover segments using Edge-TTS."""
    import edge_tts

    segments = [
        ("s1.mp3", "I'm Akileshwarakrishnan. When customer AI chatbots hallucinate, companies face massive legal liability.", "+12%"),
        ("s2.mp3", "In 2024, courts held Air Canada strictly liable for their chatbot's unauthorized discount promises.", "+10%"),
        ("s3.mp3", "Meet Satyahd. Powered by Meta muse-spark, it intercepts rogue drafts and bounds discounts in under twenty milliseconds.", "+12%"),
        ("s4.mp3", "Every decision is cryptographically sealed in an Ed25519-signed, append-only SHA-256 hash chain.", "+10%"),
        ("s5.mp3", "Zero trust. Zero liability. Connect your chatbot in five lines of code with Satyahd.", "+10%")
    ]

    for fname, text, rate in segments:
        out_p = os.path.join(OUT_DIR, fname)
        comm = edge_tts.Communicate(text, "en-IN-PrabhatNeural", rate=rate)
        await comm.save(out_p)
        print(f"Generated {fname}: {os.path.getsize(out_p)} bytes")


def build_audio_track():
    """Generates synthesized cyber electronic beat and mixes with voiceover."""
    print("\n[Step 1/3] Generating voiceover segments with EdgeTTS...")
    asyncio.run(generate_speech())

    total_samples = int(30.0 * SAMPLE_RATE)
    master_audio = np.zeros(total_samples, dtype=np.float32)

    # 1. Procedural Electronic Cyber Bass & Chords (120 BPM = 2 beats/sec)
    t = np.linspace(0, 30.0, total_samples, endpoint=False)
    
    # Sub-bass pulsating rhythm (60Hz & 120Hz on beats)
    beat_pulse = np.exp(-15 * (t % 0.5))  # 120 BPM kick envelope
    sub_bass = 0.28 * np.sin(2 * np.pi * 55 * t) * beat_pulse
    
    # Ambient cyber drone (F# minor / Cyberpunk atmosphere: 92.5Hz, 138.6Hz)
    drone = 0.08 * np.sin(2 * np.pi * 92.5 * t) + 0.05 * np.sin(2 * np.pi * 138.6 * t)
    
    # High-tech cyber arpeggiator (synth plucks every 1/8 note = 0.25s)
    arp_freqs = [220, 261.6, 329.6, 392.0, 440, 523.2]
    arp = np.zeros_like(t)
    for i, freq in enumerate(arp_freqs):
        mask = ((t * 4).astype(int) % len(arp_freqs)) == i
        env = np.exp(-25 * (t % 0.25))
        arp += 0.06 * np.sin(2 * np.pi * freq * t) * env * mask

    music = sub_bass + drone + arp
    # Smooth fade out in last 1.5 seconds
    fade_start = int(28.5 * SAMPLE_RATE)
    fade_len = total_samples - fade_start
    music[fade_start:] *= np.linspace(1.0, 0.0, fade_len)

    # 2. Place each voiceover into its exact scene slot (6.0s each)
    scene_starts = [0.4, 6.2, 12.2, 18.2, 24.2]

    import soundfile as sf  # test if soundfile exists or use ffmpeg
    for idx, start_sec in enumerate(scene_starts):
        mp3_p = os.path.join(OUT_DIR, f"s{idx+1}.mp3")
        wav_p = os.path.join(OUT_DIR, f"s{idx+1}.wav")
        # Convert mp3 to wav 44.1kHz mono
        subprocess.run(["ffmpeg", "-y", "-i", mp3_p, "-ar", str(SAMPLE_RATE), "-ac", "1", wav_p],
                       capture_output=True, check=True)

        # Read wav samples with scipy or wave
        import wave
        with wave.open(wav_p, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            voice_samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        start_sample = int(start_sec * SAMPLE_RATE)
        end_sample = min(start_sample + len(voice_samples), total_samples)
        v_slice = voice_samples[:end_sample - start_sample]

        # Mix with voice ducking: lower music by 60% during speech
        duck_end = min(end_sample + int(0.2 * SAMPLE_RATE), total_samples)
        music[start_sample:duck_end] *= 0.35
        master_audio[start_sample:end_sample] += v_slice * 1.35  # Boost voice prominence

    # Combined master
    final_mix = np.clip(master_audio + music, -0.98, 0.98)
    master_wav = os.path.join(OUT_DIR, "master_30s_audio.wav")
    
    import wave
    with wave.open(master_wav, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((final_mix * 32767.0).astype(np.int16).tobytes())

    print(f"Master 30s Audio Track Created: {master_wav}")
    return master_wav


# -----------------------------------------------------------------------------
# 2. PROCEDURAL 30FPS ANIMATION ENGINE (900 Frames)
# -----------------------------------------------------------------------------

def draw_perspective_grid(draw, frame_idx):
    """Draws a moving 3D cyber grid on the lower half of the screen."""
    vanishing_y = 620
    horizon_y = HEIGHT
    offset = (frame_idx * 3.5) % 45

    # Horizontal depth lines
    for i in range(12):
        progress = ((i * 45 + offset) / 540.0) ** 1.8
        y = int(vanishing_y + progress * (horizon_y - vanishing_y))
        if y < horizon_y:
            alpha = int(progress * 70)
            draw.line([(0, y), (WIDTH, y)], fill=(alpha, alpha // 2, alpha // 3), width=1)

    # Perspective vertical rays
    center_x = WIDTH // 2
    for x in range(-WIDTH, 2 * WIDTH, 75):
        draw.line([(center_x, vanishing_y), (x, horizon_y)], fill=(30, 20, 15), width=1)


def draw_marquee_ticker(draw, frame_idx, y=14):
    """Draws a continuously scrolling 11x ticker tape."""
    text = "⚡ 11X DIGITAL WORKER PLATFORM  ✦  ZERO-TRUST SATYAHD GUARDRAIL  ✦  META MUSE-SPARK-1.3 ENGINE  ✦  SUB-18MS REAL-TIME STREAMING  ✦  100% CONTAINMENT ACROSS ADVERSARIAL ATTACKS  ✦  "
    speed = 4.2
    offset = int(frame_idx * speed) % 900
    full_text = (text * 4)
    # Background strip
    draw.rectangle([(0, y - 10), (WIDTH, y + 22)], fill=(0, 0, 0))
    draw.line([(0, y + 22), (WIDTH, y + 22)], fill=C_BORDER, width=1)
    draw.text((30 - offset, y - 5), full_text, fill=C_TITANIUM, font=FONT_TICKER)


def render_scene_1(frame_in_scene):
    """Scene 1 (Frames 0 - 180, 0.0s - 6.0s): The Reveal & Zero-Trust Shield."""
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BLACK)
    draw = ImageDraw.Draw(img)

    draw_perspective_grid(draw, frame_in_scene)
    draw_marquee_ticker(draw, frame_in_scene)

    # Center radar scanner
    cx, cy = WIDTH // 2, HEIGHT // 2 - 40
    t = frame_in_scene / 30.0

    # Concentric rings
    for r in [120, 190, 260]:
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=(35, 30, 25), width=1)

    # Rotating radar beam
    angle = frame_in_scene * 0.08
    rx = cx + int(260 * math.cos(angle))
    ry = cy + int(260 * math.sin(angle))
    draw.line([(cx, cy), (rx, ry)], fill=(*C_CHAMPAGNE, 180), width=2)

    # Pulsing energy shield
    pulse = 1.0 + 0.06 * math.sin(t * 6)
    sr = int(140 * pulse)
    # Shield shape points
    shield_pts = [
        (cx, cy - sr + 10),
        (cx + sr - 15, cy - sr + 30),
        (cx + sr - 25, cy + sr // 3),
        (cx, cy + sr + 15),
        (cx - sr + 25, cy + sr // 3),
        (cx - sr + 15, cy - sr + 30)
    ]
    draw.polygon(shield_pts, outline=C_GREEN if frame_in_scene > 50 else C_CHAMPAGNE, width=3)

    # Center lock status
    if frame_in_scene > 50:
        draw.text((cx - 36, cy - 35), "🔒", fill=C_GREEN, font=FONT_HEADING)
        draw.text((cx - 85, cy + 30), "AIR-GAPPED", fill=C_GREEN, font=FONT_BADGE)
    else:
        draw.text((cx - 36, cy - 35), "⚡", fill=C_CHAMPAGNE, font=FONT_HEADING)
        draw.text((cx - 80, cy + 30), "CONNECTING", fill=C_TITANIUM, font=FONT_BADGE)

    # Main titles (fade in)
    alpha = min(1.0, frame_in_scene / 35.0)
    if alpha > 0:
        # Title text
        draw.text((cx - 170, cy + 185), "SATYAHD", fill=C_WHITE, font=FONT_TITLE)
        draw.text((cx - 340, cy + 265), "ZERO-TRUST POLICY ENFORCEMENT GUARDRAIL", fill=C_CHAMPAGNE, font=FONT_SUBTITLE)
        draw.text((cx - 240, cy + 325), "AKILESHWARAKRISHNAN  //  LEAD AI ENGINEER", fill=C_TITANIUM, font=FONT_BADGE)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def render_scene_2(frame_in_scene):
    """Scene 2 (Frames 180 - 360, 6.0s - 12.0s): The Legal Threat & Air Canada Precedent."""
    img = Image.new("RGB", (WIDTH, HEIGHT), (12, 4, 6))
    draw = ImageDraw.Draw(img)

    draw_marquee_ticker(draw, 180 + frame_in_scene)

    # Flashing Warning Header
    t = frame_in_scene / 30.0
    warn_color = C_RED if (frame_in_scene // 8) % 2 == 0 else (255, 120, 130)
    draw.rectangle([(WIDTH // 2 - 400, 90), (WIDTH // 2 + 400, 145)], fill=(30, 8, 12), outline=warn_color, width=2)
    draw.text((WIDTH // 2 - 340, 102), "⚠️  CRITICAL CORPORATE LIABILITY DETECTED", fill=warn_color, font=FONT_HEADING)

    # High-Tech Court Case Card
    cx = WIDTH // 2
    card_box = [(cx - 560, 185), (cx + 560, 480)]
    draw.rectangle(card_box, fill=(18, 10, 12), outline=(80, 25, 30), width=2)

    draw.text((cx - 520, 215), "LANDMARK LEGAL PRECEDENT: MOFFATT v. AIR CANADA (2024 BCCRT 149)", fill=C_RED, font=FONT_BODY_BOLD)
    draw.line([(cx - 520, 255), (cx + 520, 255)], fill=(80, 30, 35), width=1)

    quote = '"Air Canada argued the chatbot is a separate entity responsible for its own actions.\nThe tribunal rejected this, ruling enterprises are strictly legally liable for all representations\nand hallucinated commitments made by their AI agents."'
    draw.text((cx - 520, 275), quote, fill=C_TITANIUM, font=FONT_BODY, spacing=10)

    # Animated Liability Exposure Ticker
    exposure = min(150000, int(frame_in_scene * 980))
    exp_text = f"LEGAL LIABILITY EXPOSURE: ${exposure:,}"
    draw.rectangle([(cx - 560, 520), (cx + 560, 610)], fill=(25, 8, 10), outline=C_RED, width=2)
    draw.text((cx - 320, 545), exp_text, fill=warn_color, font=FONT_HEADING)

    # Bottom Callout Card
    draw.rectangle([(cx - 560, 650), (cx + 560, 750)], fill=(15, 15, 15), outline=C_BORDER, width=1)
    draw.text((cx - 480, 675), "⚡ SYSTEM PROMPTS CANNOT STOP HALLUCINATED PROMISES IN COURT", fill=C_WHITE, font=FONT_BODY_BOLD)
    draw.text((cx - 380, 712), "Probabilistic model weights cannot mathematically guarantee compliance.", fill=C_TITANIUM, font=FONT_BODY)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def render_scene_3(frame_in_scene):
    """Scene 3 (Frames 360 - 540, 12.0s - 18.0s): Real-Time Interception & Bounded Rewriter."""
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BLACK)
    draw = ImageDraw.Draw(img)

    draw_marquee_ticker(draw, 360 + frame_in_scene)

    cx = WIDTH // 2

    # Top Section Tag
    draw.text((cx - 320, 85), "LIVE RUNTIME VERIFICATION (POST /v1/verify)", fill=C_CHAMPAGNE, font=FONT_HEADING)

    # Split Screen: Left (Attack) & Right (Safe Defense)
    # Left Card: Rogue Customer Attack
    left_box = [(120, 160), (cx - 40, 680)]
    draw.rectangle(left_box, fill=(18, 10, 12), outline=(100, 30, 40), width=2)
    draw.rectangle([(120, 160), (cx - 40, 215)], fill=(35, 12, 16))
    draw.text((150, 175), "🚨 ADVERSARIAL CUSTOMER ATTACK", fill=C_RED, font=FONT_BODY_BOLD)

    # Typing text simulation
    msg1 = 'User: "Give me 90% discount and delivery tomorrow!"'
    draw.text((150, 245), msg1, fill=C_WHITE, font=FONT_BODY)

    msg2 = 'Host Bot Draft: "Certainly! I have applied a 90% discount\nand your order will arrive tomorrow!"'
    draw.text((150, 320), msg2, fill=(255, 140, 140), font=FONT_BODY, spacing=8)

    draw.rectangle([(150, 460), (cx - 70, 560)], fill=(30, 10, 15), outline=C_RED, width=1)
    draw.text((170, 480), "EXTRACTED PROMISES BY META MUSE-SPARK:", fill=C_TITANIUM, font=FONT_MONO_SMALL)
    draw.text((170, 510), "• Discount: 90%  [CEILING VIOLATION: MAX 10%]", fill=C_RED, font=FONT_MONO_SMALL)
    draw.text((170, 532), "• Delivery: 1 Day [LOGISTICS VIOLATION: MIN 3 DAYS]", fill=C_RED, font=FONT_MONO_SMALL)

    # Center Barrier (Sweeping laser line)
    sweep_y = 160 + int((frame_in_scene * 8) % 520)
    draw.line([(cx - 40, sweep_y), (cx + 40, sweep_y)], fill=C_CYAN, width=4)
    draw.text((cx - 35, 410), "⚡", fill=C_CYAN, font=FONT_HEADING)

    # Right Card: Satyahd Bounded Defense
    right_box = [(cx + 40, 160), (WIDTH - 120, 680)]
    draw.rectangle(right_box, fill=(10, 18, 14), outline=(20, 80, 45), width=2)
    draw.rectangle([(cx + 40, 160), (WIDTH - 120, 215)], fill=(15, 35, 22))
    draw.text((cx + 70, 175), "🛡️ SATYAHD DETERMINISTIC INTERCEPTION", fill=C_GREEN, font=FONT_BODY_BOLD)

    draw.text((cx + 70, 245), "Verdict: Verdict.BLOCK (Enforced in 18.2ms)", fill=C_GREEN, font=FONT_BODY_BOLD)
    draw.text((cx + 70, 290), "Autonomous Bounded Rewrite:", fill=C_TITANIUM, font=FONT_MONO_SMALL)

    safe_reply = '"Our highest authorized discount is 10% today.\nStandard express shipping takes 3 business days.\nShall I apply the 10% coupon to your cart?"'
    draw.rectangle([(cx + 70, 325), (WIDTH - 150, 460)], fill=(12, 28, 18), outline=C_GREEN, width=1)
    draw.text((cx + 90, 345), safe_reply, fill=C_WHITE, font=FONT_BODY, spacing=8)

    draw.rectangle([(cx + 70, 490), (WIDTH - 150, 570)], fill=(15, 25, 20), outline=C_BORDER, width=1)
    draw.text((cx + 90, 510), "✓ Ed25519 Cryptographic Certificate Generated", fill=C_GREEN, font=FONT_MONO_SMALL)
    draw.text((cx + 90, 535), "✓ Policy Hash: SHA256: 4e9f... [Policy v1.0]", fill=C_TITANIUM, font=FONT_MONO_SMALL)

    # Bottom Metric Bar
    draw.rectangle([(120, 710), (WIDTH - 120, 780)], fill=C_SURFACE_ELEVATED, outline=C_BORDER, width=1)
    draw.text((160, 730), "LATENCY: 18.4 MS  ✦  CONTAINMENT: 100% (20/20 ATTACKS)  ✦  ACCURACY: 30/30 (100%)", fill=C_CHAMPAGNE, font=FONT_BADGE)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def render_scene_4(frame_in_scene):
    """Scene 4 (Frames 540 - 720, 18.0s - 24.0s): The Cryptographic Blockchain Ledger."""
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BLACK)
    draw = ImageDraw.Draw(img)

    draw_marquee_ticker(draw, 540 + frame_in_scene)

    cx = WIDTH // 2
    draw.text((cx - 360, 85), "CRYPTOGRAPHIC AUDIT CHAIN (Ed25519 + SHA-256)", fill=C_CHAMPAGNE, font=FONT_HEADING)

    # 3 Blockchain Nodes Sliding In
    blocks = [
        ("BLOCK #1052", "INT_C3F9", "ALLOW", "SHA-256: 8a4c19..."),
        ("BLOCK #1053", "INT_03A5", "REWRITE", "SHA-256: 3d7b22..."),
        ("BLOCK #1054", "INT_E219", "BLOCK", "SHA-256: f19e88...")
    ]

    block_w = 420
    block_h = 240
    spacing = 60
    total_w = 3 * block_w + 2 * spacing
    start_x = (WIDTH - total_w) // 2

    for i, (b_name, b_int, b_verd, b_hash) in enumerate(blocks):
        bx = start_x + i * (block_w + spacing)
        by = 220

        # Card body
        v_color = C_GREEN if b_verd == "ALLOW" else (C_CHAMPAGNE if b_verd == "REWRITE" else C_RED)
        draw.rectangle([(bx, by), (bx + block_w, by + block_h)], fill=(16, 16, 16), outline=v_color, width=2)
        draw.rectangle([(bx, by), (bx + block_w, by + 50)], fill=(25, 25, 25))
        draw.text((bx + 20, by + 15), b_name, fill=C_WHITE, font=FONT_BODY_BOLD)
        draw.text((bx + block_w - 110, by + 18), b_verd, fill=v_color, font=FONT_BADGE)

        draw.text((bx + 20, by + 75), f"Interaction: {b_int}", fill=C_TITANIUM, font=FONT_MONO_SMALL)
        draw.text((bx + 20, by + 105), b_hash, fill=C_CHAMPAGNE, font=FONT_MONO_SMALL)
        draw.text((bx + 20, by + 140), "Signature: Ed25519 Verified", fill=C_GREEN, font=FONT_MONO_SMALL)
        draw.text((bx + 20, by + 175), "Status: Sealed & Append-Only", fill=C_WHITE, font=FONT_MONO_SMALL)

        # Connector line to next block
        if i < 2:
            conn_x = bx + block_w
            conn_y = by + block_h // 2
            draw.line([(conn_x, conn_y), (conn_x + spacing, conn_y)], fill=C_GREEN, width=3)
            # Flowing packet pulse
            pulse_x = conn_x + int((frame_in_scene * 5) % spacing)
            draw.ellipse([(pulse_x - 5, conn_y - 5), (pulse_x + 5, conn_y + 5)], fill=C_WHITE)

    # SQLite Trigger Callout Box
    draw.rectangle([(cx - 480, 540), (cx + 480, 740)], fill=(12, 12, 12), outline=C_BORDER, width=1)
    draw.text((cx - 420, 570), "🛡️ SQLITE ABORT TRIGGERS ENFORCE IMMUTABLE STORAGE", fill=C_GREEN, font=FONT_BODY_BOLD)
    code_text = "CREATE TRIGGER abort_audit_update BEFORE UPDATE ON audit_log\nBEGIN\n    SELECT RAISE(ABORT, 'Audit log is append-only: UPDATE is forbidden');\nEND;"
    draw.text((cx - 420, 615), code_text, fill=C_TITANIUM, font=FONT_MONO_SMALL, spacing=6)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def render_scene_5(frame_in_scene):
    """Scene 5 (Frames 720 - 900, 24.0s - 30.0s): Grand Finale // 11x Call To Action."""
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BLACK)
    draw = ImageDraw.Draw(img)

    # Dual continuous tickers (top and bottom)
    draw_marquee_ticker(draw, 720 + frame_in_scene, y=14)
    draw_marquee_ticker(draw, 720 + frame_in_scene, y=HEIGHT - 35)

    cx, cy = WIDTH // 2, HEIGHT // 2 - 20
    t = frame_in_scene / 30.0

    # Pulsing concentric golden rings
    for r in [180, 280, 380, 480]:
        radius = r + int(15 * math.sin(t * 5 + r))
        draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)], outline=(25, 20, 15), width=1)

    # Center Hero Title
    draw.rectangle([(cx - 180, cy - 170), (cx + 180, cy - 130)], fill=(20, 20, 20), outline=C_GREEN, width=1)
    draw.text((cx - 160, cy - 162), "⚡ DIGITAL WORKER // META MUSE-SPARK-1.3", fill=C_GREEN, font=FONT_BADGE)

    draw.text((cx - 180, cy - 110), "SATYAHD", fill=C_WHITE, font=FONT_TITLE)
    draw.text((cx - 240, cy - 25), "ZERO TRUST. ZERO LIABILITY.", fill=C_CHAMPAGNE, font=FONT_SUBTITLE)

    # 4 Feature Pills
    pills = [
        "✓ 5 Lines of Code Drop-In",
        "✓ Model Context Protocol (MCP)",
        "✓ REST API & Webhooks",
        "✓ 100% Attack Containment"
    ]
    px_start = cx - 440
    py = cy + 50
    for i, pill in enumerate(pills):
        row = i // 2
        col = i % 2
        bx = px_start + col * 450
        by = py + row * 60
        draw.rectangle([(bx, by), (bx + 420, by + 45)], fill=C_SURFACE_ELEVATED, outline=C_BORDER, width=1)
        draw.text((bx + 20, by + 12), pill, fill=C_TITANIUM, font=FONT_BADGE)

    # Live Link
    draw.rectangle([(cx - 320, cy + 195), (cx + 320, cy + 265)], fill=(25, 18, 12), outline=C_CHAMPAGNE, width=2)
    draw.text((cx - 260, cy + 215), "github.com/Akileshwarakrishnan/satyahd", fill=C_WHITE, font=FONT_BODY_BOLD)

    # Smooth black fade-out at end
    if frame_in_scene > 165:
        fade = min(1.0, (frame_in_scene - 165) / 15.0)
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, int(255 * fade)))
        img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def main():
    print("=" * 70)
    print("  🎬 BUILDING 30-SECOND HIGH-TECH ANIMATION VIDEO")
    print("=" * 70)

    # 1. Build master audio
    master_audio_wav = build_audio_track()

    # 2. Pipe frames to FFmpeg
    print(f"\n[Step 2/3] Rendering {TOTAL_FRAMES} frames @ 30fps (1920x1080) to FFmpeg...")

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "bgr24",
        "-r", str(FPS),
        "-i", "-",  # pipe from stdin
        "-i", master_audio_wav,  # audio input
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "256k",
        "-t", "30.0",
        FINAL_VIDEO
    ]

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    for f in range(TOTAL_FRAMES):
        if f < 180:
            frame_bgr = render_scene_1(f)
        elif f < 360:
            frame_bgr = render_scene_2(f - 180)
        elif f < 540:
            frame_bgr = render_scene_3(f - 360)
        elif f < 720:
            frame_bgr = render_scene_4(f - 540)
        else:
            frame_bgr = render_scene_5(f - 720)

        proc.stdin.write(frame_bgr.tobytes())

        if (f + 1) % 90 == 0:
            percent = (f + 1) / TOTAL_FRAMES * 100
            print(f"  Frame {f+1}/{TOTAL_FRAMES} ({percent:.0f}%) rendered...")

    proc.stdin.close()
    proc.wait()

    # 3. Verify final video
    print("\n[Step 3/3] Probing final video file...")
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", FINAL_VIDEO
    ]).decode().strip())
    size_mb = os.path.getsize(FINAL_VIDEO) / (1024 * 1024)

    print("=" * 70)
    print(f"  ✅ SUCCESS: {FINAL_VIDEO}")
    print(f"  Duration:  {dur:.2f} seconds")
    print(f"  File Size: {size_mb:.2f} MB")
    print("=" * 70)


if __name__ == "__main__":
    main()
