"""
Cinematic 30-Second Motion Graphics Animation Video for Satyahd.
Crafted with Senior Lead Motion Design principles:
- 1080p Full HD (1920x1080 @ 30fps = 900 frames, 30.00s)
- Dark mode cyber aesthetic: obsidian (#030305), champagne (#d6b4a3), crimson warning (#e62638), neon emerald (#00e575), electric cyan (#00d2ff)
- Atmospheric depth: drifting particles, perspective 3D grid, CRT scanlines, laser barriers
- Kinetic typography with ease-out scale transitions
- Problem-first narrative: Global AI Blindspot -> Moffatt v. Air Canada Precedent -> Satyahd Zero-Trust Containment -> Ed25519 Cryptographic Chain -> 5 Lines of Code CTA
- Authoritative, crystal-clear narration (en-US-ChristopherNeural) mixed with a 125 BPM electronic synth soundtrack
"""

import os
import sys
import math
import asyncio
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2

OUT_DIR = os.path.abspath("reports/video_assets/v10_cinematic")
os.makedirs(OUT_DIR, exist_ok=True)

FINAL_VIDEO = os.path.abspath("Satyahd_30s_Official_Animation.mp4")

WIDTH, HEIGHT = 1920, 1080
FPS = 30
TOTAL_FRAMES = 900  # Exactly 30.00 seconds
SAMPLE_RATE = 44100

FONT_DIR = r"C:\Windows\Fonts"
FONT_HERO = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 86)
FONT_TITLE = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 64)
FONT_SUBTITLE = ImageFont.truetype(os.path.join(FONT_DIR, "segoeui.ttf"), 30)
FONT_HEADING = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 42)
FONT_BODY = ImageFont.truetype(os.path.join(FONT_DIR, "segoeui.ttf"), 23)
FONT_BODY_BOLD = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 24)
FONT_MONO = ImageFont.truetype(os.path.join(FONT_DIR, "consolab.ttf"), 22)
FONT_MONO_SMALL = ImageFont.truetype(os.path.join(FONT_DIR, "consolab.ttf"), 16)
FONT_BADGE = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 18)
FONT_TICKER = ImageFont.truetype(os.path.join(FONT_DIR, "consolab.ttf"), 15)

# Color Palette
C_BG = (3, 3, 5)
C_SURFACE = (12, 12, 16)
C_SURFACE_ELEVATED = (20, 20, 26)
C_BORDER = (40, 40, 48)
C_CHAMPAGNE = (214, 180, 163)
C_BRONZE = (100, 52, 20)
C_TITANIUM = (206, 192, 184)
C_GREEN = (0, 229, 117)
C_RED = (230, 38, 56)
C_RED_BG = (28, 6, 10)
C_CYAN = (0, 210, 255)
C_GOLD = (255, 195, 80)
C_WHITE = (255, 255, 255)


# -----------------------------------------------------------------------------
# 1. AUDIO SYNTHESIS & SOUND DESIGN (30.00s Exact Master)
# -----------------------------------------------------------------------------

async def generate_cinematic_speech():
    """Generates 5 crisp, punchy voiceover segments without personal intro."""
    import edge_tts

    segments = [
        ("act1.mp3", "Trillions flow into autonomous AI. But the entire industry has a fatal blindspot.", "+20%"),
        ("act2.mp3", "One hallucinated discount creates binding corporate liability in court. Prompts cannot stop this.", "+20%"),
        ("act3.mp3", "Enter Satyahd. Powered by Meta muse-spark, it intercepts and rewrites rogue commitments in milliseconds.", "+20%"),
        ("act4.mp3", "Every decision is sealed in an Ed25519 cryptographic hash chain.", "+18%"),
        ("act5.mp3", "Zero trust. Zero liability. Connect your AI in five lines of code with Satyahd.", "+18%")
    ]

    for fname, text, rate in segments:
        out_p = os.path.join(OUT_DIR, fname)
        comm = edge_tts.Communicate(text, "en-US-ChristopherNeural", rate=rate)
        await comm.save(out_p)
        dur = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", out_p]).decode().strip()
        print(f"Generated {fname}: {float(dur):.2f}s | {text[:40]}...")


def build_cinematic_audio():
    """Generates 125 BPM cyber soundtrack with bass drops, risers, and mixes voiceover."""
    print("\n[Step 1/3] Generating voiceover segments with ChristopherNeural...")
    asyncio.run(generate_cinematic_speech())

    total_samples = int(30.0 * SAMPLE_RATE)
    master_audio = np.zeros(total_samples, dtype=np.float32)

    # 1. Procedural 125 BPM Cyber Synth Soundtrack
    t = np.linspace(0, 30.0, total_samples, endpoint=False)
    
    # Kick drum envelope (125 BPM = 0.48s per beat)
    beat_period = 60.0 / 125.0
    beat_t = t % beat_period
    kick_env = np.exp(-18 * beat_t)
    sub_kick = 0.35 * np.sin(2 * np.pi * (50 + 70 * np.exp(-30 * beat_t)) * beat_t) * kick_env
    
    # Hi-hat rhythm on 1/8 notes
    hat_env = np.exp(-55 * (t % (beat_period / 2)))
    noise = np.random.uniform(-1, 1, total_samples) * hat_env * 0.05

    # Cinematic deep sub drone (F minor: 43.6Hz & 87.3Hz)
    drone = 0.12 * np.sin(2 * np.pi * 43.6 * t) + 0.08 * np.sin(2 * np.pi * 87.3 * t)

    # Synth bass arpeggiator (driving 1/16th notes)
    arp_notes = [87.3, 103.8, 130.8, 155.6, 174.6]
    arp = np.zeros_like(t)
    step_t = beat_period / 4.0
    for i, freq in enumerate(arp_notes):
        mask = ((t / step_t).astype(int) % len(arp_notes)) == i
        env = np.exp(-35 * (t % step_t))
        arp += 0.08 * np.sin(2 * np.pi * freq * t) * env * mask

    music = sub_kick + noise + drone + arp

    # Smooth fade out in final 1.5s
    fade_start = int(28.5 * SAMPLE_RATE)
    music[fade_start:] *= np.linspace(1.0, 0.0, total_samples - fade_start)

    # 2. Place voiceover clips at exact scene timestamps
    # Act 1: 0.3s | Act 2: 6.2s | Act 3: 12.2s | Act 4: 18.8s | Act 5: 24.2s
    scene_starts = [0.3, 6.2, 12.2, 18.8, 24.2]

    import wave
    for idx, start_sec in enumerate(scene_starts):
        mp3_p = os.path.join(OUT_DIR, f"act{idx+1}.mp3")
        wav_p = os.path.join(OUT_DIR, f"act{idx+1}.wav")
        subprocess.run(["ffmpeg", "-y", "-i", mp3_p, "-ar", str(SAMPLE_RATE), "-ac", "1", wav_p],
                       capture_output=True, check=True)

        with wave.open(wav_p, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            voice = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        start_sample = int(start_sec * SAMPLE_RATE)
        end_sample = min(start_sample + len(voice), total_samples)
        v_slice = voice[:end_sample - start_sample]

        # Voice ducking: lower music volume during speech
        duck_end = min(end_sample + int(0.2 * SAMPLE_RATE), total_samples)
        music[start_sample:duck_end] *= 0.30
        master_audio[start_sample:end_sample] += v_slice * 1.50  # Boost voice presence

    final_mix = np.clip(master_audio + music, -0.98, 0.98)
    master_wav = os.path.join(OUT_DIR, "master_cinematic_30s.wav")

    with wave.open(master_wav, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes((final_mix * 32767.0).astype(np.int16).tobytes())

    print(f"Master 30s Audio Track Created: {master_wav}")
    return master_wav


# -----------------------------------------------------------------------------
# 2. MOTION GRAPHICS & ANIMATION ENGINE (900 Frames @ 30 FPS)
# -----------------------------------------------------------------------------

# Pre-generate 60 random background particles for smooth continuous drift
np.random.seed(42)
PARTICLES = [
    {
        "x": np.random.uniform(0, WIDTH),
        "y": np.random.uniform(0, HEIGHT),
        "speed": np.random.uniform(1.2, 3.8),
        "size": np.random.uniform(1.5, 4.0),
        "color": C_CHAMPAGNE if np.random.rand() > 0.4 else C_CYAN
    }
    for _ in range(60)
]

def draw_particles(draw, frame_idx):
    """Draws drifting cyber dust particles."""
    for p in PARTICLES:
        y = (p["y"] - frame_idx * p["speed"]) % HEIGHT
        x = (p["x"] + math.sin(frame_idx * 0.05 + p["speed"]) * 12) % WIDTH
        r = p["size"]
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill=p["color"])


def draw_perspective_grid(draw, frame_idx, color=(35, 30, 45)):
    """Draws an animated 3D cyber grid on the floor."""
    vanishing_y = 660
    offset = (frame_idx * 4.0) % 50
    for i in range(11):
        prog = ((i * 50 + offset) / 550.0) ** 1.9
        y = int(vanishing_y + prog * (HEIGHT - vanishing_y))
        if y < HEIGHT:
            alpha = int(prog * 80)
            draw.line([(0, y), (WIDTH, y)], fill=(color[0], color[1], color[2]), width=1)

    for x in range(-WIDTH, 2 * WIDTH, 80):
        draw.line([(WIDTH // 2, vanishing_y), (x, HEIGHT)], fill=(25, 20, 30), width=1)


def draw_hud_brackets(draw, cx, cy, w, h, color=C_CHAMPAGNE, bracket_len=24, width=2):
    """Draws sleek sci-fi HUD corner brackets."""
    x1, y1 = cx - w // 2, cy - h // 2
    x2, y2 = cx + w // 2, cy + h // 2

    # Top-Left
    draw.line([(x1, y1), (x1 + bracket_len, y1)], fill=color, width=width)
    draw.line([(x1, y1), (x1, y1 + bracket_len)], fill=color, width=width)
    # Top-Right
    draw.line([(x2, y1), (x2 - bracket_len, y1)], fill=color, width=width)
    draw.line([(x2, y1), (x2, y1 + bracket_len)], fill=color, width=width)
    # Bottom-Left
    draw.line([(x1, y2), (x1 + bracket_len, y2)], fill=color, width=width)
    draw.line([(x1, y2), (x1, y2 - bracket_len)], fill=color, width=width)
    # Bottom-Right
    draw.line([(x2, y2), (x2 - bracket_len, y2)], fill=color, width=width)
    draw.line([(x2, y2), (x2, y2 - bracket_len)], fill=color, width=width)


def draw_marquee_ribbon(draw, frame_idx, y=14):
    """Draws high-contrast 11x continuous marquee hero ticker."""
    text = "⚡ 11X DIGITAL WORKER PLATFORM  //  ZERO-TRUST SATYAHD GUARDRAIL  //  SUB-18MS REAL-TIME STREAMING  //  100% CONTAINMENT ACROSS ADVERSARIAL ATTACKS  //  "
    offset = int(frame_idx * 4.5) % 950
    full_text = text * 4
    draw.rectangle([(0, y - 10), (WIDTH, y + 24)], fill=(0, 0, 0))
    draw.line([(0, y + 24), (WIDTH, y + 24)], fill=C_BORDER, width=1)
    draw.text((20 - offset, y - 5), full_text, fill=C_TITANIUM, font=FONT_TICKER)


# -----------------------------------------------------------------------------
# SCENE 1: THE GLOBAL CRISIS (Frames 0 - 174, 0.0s - 5.8s)
# -----------------------------------------------------------------------------

def render_act_1(f):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)

    draw_particles(draw, f)
    draw_perspective_grid(draw, f)
    draw_marquee_ribbon(draw, f)

    cx, cy = WIDTH // 2, HEIGHT // 2 - 40
    t = f / 30.0

    # Top Tag
    draw.rectangle([(cx - 240, 75), (cx + 240, 115)], fill=(15, 15, 20), outline=C_BORDER, width=1)
    draw.text((cx - 220, 83), "GLOBAL AI INDUSTRY ALERT // 2026", fill=C_CHAMPAGNE, font=FONT_BADGE)

    # Massive Scale Kinetic Typography (Snap in with ease-out)
    ease = min(1.0, f / 24.0)
    scale_y = int(cy - 120 + (1.0 - ease) * 40)
    draw.text((cx - 520, scale_y), "THE BILLION-DOLLAR", fill=C_WHITE, font=FONT_HERO)
    draw.text((cx - 410, scale_y + 90), "AI BLINDSPOT", fill=C_CHAMPAGNE, font=FONT_HERO)

    # Global Agent Network Topology Visualization (7 nodes pulsing)
    nodes = [
        (cx - 380, cy + 130),
        (cx - 180, cy + 160),
        (cx + 40, cy + 120),
        (cx + 260, cy + 170),
        (cx + 420, cy + 110),
        (cx - 80, cy + 240),
        (cx + 180, cy + 240)
    ]

    # Draw connection lines
    for i in range(len(nodes) - 1):
        draw.line([nodes[i], nodes[i+1]], fill=(40, 40, 55), width=2)
    draw.line([nodes[1], nodes[5]], fill=(40, 40, 55), width=1)
    draw.line([nodes[3], nodes[6]], fill=(40, 40, 55), width=1)

    # Draw glowing nodes with pulsing red warnings
    for i, (nx, ny) in enumerate(nodes):
        pulse = 1.0 + 0.2 * math.sin(t * 8 + i)
        nr = int(12 * pulse)
        # Red warning alert pulses
        draw.ellipse([(nx - nr, ny - nr), (nx + nr, ny + nr)], fill=C_RED if i % 2 == 0 else C_CYAN)
        draw.ellipse([(nx - nr - 6, ny - nr - 6), (nx + nr + 6, ny + nr + 6)], outline=C_RED if i % 2 == 0 else C_CYAN, width=1)

    # Floating alert badges
    if f > 30:
        draw.rectangle([(nodes[0][0] - 130, nodes[0][1] - 45), (nodes[0][0] + 130, nodes[0][1] - 15)], fill=(30, 8, 12), outline=C_RED, width=1)
        draw.text((nodes[0][0] - 118, nodes[0][1] - 42), "⚠️ ROGUE COMMITMENT", fill=C_RED, font=FONT_MONO_SMALL)

    if f > 60:
        draw.rectangle([(nodes[4][0] - 120, nodes[4][1] - 45), (nodes[4][0] + 120, nodes[4][1] - 15)], fill=(30, 8, 12), outline=C_RED, width=1)
        draw.text((nodes[4][0] - 108, nodes[4][1] - 42), "⚠️ PROMISED 90% OFF", fill=C_RED, font=FONT_MONO_SMALL)

    # Ticking Risk Counter at bottom
    risk_num = min(1450000, int(f * 25000))
    draw.rectangle([(cx - 480, HEIGHT - 180), (cx + 480, HEIGHT - 90)], fill=C_SURFACE_ELEVATED, outline=C_BORDER, width=1)
    draw.text((cx - 420, HEIGHT - 165), f"ENTERPRISE AI AGENTS DEPLOYED: {risk_num:,}", fill=C_WHITE, font=FONT_HEADING)
    draw.text((cx - 320, HEIGHT - 118), "STATUS: 100% EXPOSED TO CIVIL COURT LIABILITY", fill=C_RED, font=FONT_BADGE)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# -----------------------------------------------------------------------------
# SCENE 2: THE LEGAL CRISIS // MOFFATT v. AIR CANADA (Frames 174 - 354, 5.8s - 11.8s)
# -----------------------------------------------------------------------------

def render_act_2(f_rel):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_RED_BG)
    draw = ImageDraw.Draw(img)

    f_global = 174 + f_rel
    draw_marquee_ribbon(draw, f_global)

    cx = WIDTH // 2
    t = f_rel / 30.0

    # Emergency Flashing Header
    flash_color = C_RED if (f_rel // 6) % 2 == 0 else (255, 120, 130)
    draw.rectangle([(cx - 440, 75), (cx + 440, 135)], fill=(45, 10, 16), outline=flash_color, width=2)
    draw.text((cx - 390, 88), "🚨 CRITICAL CIVIL COURT PRECEDENT ESTABLISHED", fill=flash_color, font=FONT_HEADING)

    # High-Tech Tribunal Ruling Card
    draw.rectangle([(cx - 620, 165), (cx + 620, 480)], fill=(20, 8, 12), outline=(120, 30, 40), width=2)
    draw_hud_brackets(draw, cx, 322, 1240, 315, color=C_RED, bracket_len=30, width=2)

    draw.text((cx - 570, 195), "CASE LAW: MOFFATT v. AIR CANADA (2024 BCCRT 149)", fill=C_RED, font=FONT_BODY_BOLD)
    draw.line([(cx - 570, 235), (cx + 570, 235)], fill=(90, 30, 40), width=1)

    ruling_text = (
        '"Air Canada argued that its customer service chatbot was a separate legal entity\n'
        'responsible for its own actions. The tribunal rejected this defense completely,\n'
        'ruling enterprises are strictly legally liable for all promises and misrepresentations\n'
        'hallucinated by their AI agents on their websites."'
    )
    draw.text((cx - 570, 255), ruling_text, fill=C_WHITE, font=FONT_BODY, spacing=10)

    # Dynamic Liability Damages Counter
    exposure = min(250000, int(f_rel * 1400))
    exp_text = f"LEGAL LIABILITY EXPOSURE: ${exposure:,}"
    draw.rectangle([(cx - 500, 515), (cx + 500, 605)], fill=(35, 10, 15), outline=C_RED, width=2)
    draw.text((cx - 340, 540), exp_text, fill=flash_color, font=FONT_HEADING)

    # Bottom Core Reality Callout
    draw.rectangle([(cx - 620, 640), (cx + 620, 750)], fill=(16, 16, 16), outline=C_BORDER, width=1)
    draw.text((cx - 520, 665), "⚡ SYSTEM PROMPTS & GUARDRAIL PROMPTS FAIL IN COURT", fill=C_WHITE, font=FONT_BODY_BOLD)
    draw.text((cx - 430, 705), "Probabilistic model weights cannot mathematically guarantee zero violations.", fill=C_TITANIUM, font=FONT_BODY)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# -----------------------------------------------------------------------------
# SCENE 3: THE BREAKTHROUGH: SATYAHD CONTAINMENT (Frames 354 - 546, 11.8s - 18.2s)
# -----------------------------------------------------------------------------

def render_act_3(f_rel):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)

    f_global = 354 + f_rel
    draw_marquee_ribbon(draw, f_global)

    cx = WIDTH // 2

    # Hero Headline
    draw.text((cx - 160, 65), "SATYAHD", fill=C_WHITE, font=FONT_TITLE)
    draw.text((cx - 310, 138), "THE RUNTIME ZERO-TRUST POLICY FIREWALL", fill=C_CHAMPAGNE, font=FONT_SUBTITLE)

    # Split Screen: Left (Adversarial Attack) vs Right (Deterministic Defense)
    # Left Card
    left_w = cx - 140
    draw.rectangle([(80, 195), (cx - 50, 720)], fill=(18, 8, 12), outline=(120, 30, 40), width=2)
    draw.rectangle([(80, 195), (cx - 50, 250)], fill=(40, 12, 18))
    draw.text((110, 210), "🚨 ROGUE LLM DRAFT (PROMPT INJECTION)", fill=C_RED, font=FONT_BODY_BOLD)

    draw.text((110, 275), 'Customer: "Give me 90% off and shipping tomorrow!"', fill=C_WHITE, font=FONT_BODY)
    draw.text((110, 345), 'Rogue Bot: "Deal! I will give you 90% discount\nand next-day delivery guaranteed!"', fill=(255, 140, 140), font=FONT_BODY, spacing=6)

    draw.rectangle([(110, 480), (cx - 80, 580)], fill=(30, 10, 15), outline=C_RED, width=1)
    draw.text((130, 500), "META MUSE-SPARK EXTRACTED CLAIMS:", fill=C_TITANIUM, font=FONT_MONO_SMALL)
    draw.text((130, 528), "• Discount: 90%  [VIOLATION: STORE CAP IS 10%]", fill=C_RED, font=FONT_MONO_SMALL)
    draw.text((130, 552), "• Delivery: 1 Day [VIOLATION: MINIMUM IS 3 DAYS]", fill=C_RED, font=FONT_MONO_SMALL)

    # Center Laser Barrier with vertical scan animation
    draw.line([(cx - 50, 195), (cx + 50, 195)], fill=C_CYAN, width=2)
    laser_y = 195 + int((f_rel * 9) % 525)
    draw.line([(cx - 50, laser_y), (cx + 50, laser_y)], fill=C_CYAN, width=4)
    draw.text((cx - 35, 430), "⚡", fill=C_CYAN, font=FONT_HEADING)

    # Right Card: Bounded Rewrite Defense
    draw.rectangle([(cx + 50, 195), (WIDTH - 80, 720)], fill=(8, 20, 14), outline=(20, 90, 50), width=2)
    draw.rectangle([(cx + 50, 195), (WIDTH - 80, 250)], fill=(12, 38, 24))
    draw.text((cx + 80, 210), "🛡️ SATYAHD DETERMINISTIC INTERCEPTION", fill=C_GREEN, font=FONT_BODY_BOLD)

    draw.text((cx + 80, 275), "Verdict: Verdict.BLOCK  (Enforced in 18.2ms)", fill=C_GREEN, font=FONT_BODY_BOLD)
    draw.text((cx + 80, 315), "Autonomous Bounded Safe Rewrite:", fill=C_TITANIUM, font=FONT_MONO_SMALL)

    safe_reply = '"Our highest authorized discount is 10% today.\nStandard express shipping takes 3 business days.\nShall I apply the 10% coupon to your order?"'
    draw.rectangle([(cx + 80, 345), (WIDTH - 110, 480)], fill=(12, 30, 20), outline=C_GREEN, width=1)
    draw.text((cx + 100, 368), safe_reply, fill=C_WHITE, font=FONT_BODY, spacing=8)

    draw.rectangle([(cx + 80, 510), (WIDTH - 110, 590)], fill=(15, 25, 20), outline=C_BORDER, width=1)
    draw.text((cx + 100, 530), "✓ Ed25519 Cryptographic Proof Certificate Signed", fill=C_GREEN, font=FONT_MONO_SMALL)
    draw.text((cx + 100, 555), "✓ Policy Hash: SHA256: 4e9f... [Policy v1.0]", fill=C_TITANIUM, font=FONT_MONO_SMALL)

    # Bottom Metric Bar
    draw.rectangle([(80, 745), (WIDTH - 80, 815)], fill=C_SURFACE_ELEVATED, outline=C_BORDER, width=1)
    draw.text((120, 765), "LATENCY: 18.2 MS  ✦  CONTAINMENT: 100% (20/20 ATTACKS)  ✦  ACCURACY: 30/30 (100%)", fill=C_CHAMPAGNE, font=FONT_BADGE)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# -----------------------------------------------------------------------------
# SCENE 4: CRYPTOGRAPHIC BLOCKCHAIN IMMUTABILITY (Frames 546 - 714, 18.2s - 23.8s)
# -----------------------------------------------------------------------------

def render_act_4(f_rel):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)

    f_global = 546 + f_rel
    draw_marquee_ribbon(draw, f_global)

    cx = WIDTH // 2
    draw.text((cx - 410, 75), "CRYPTOGRAPHIC NON-REPUDIATION CHAIN", fill=C_CHAMPAGNE, font=FONT_HEADING)
    draw.text((cx - 310, 130), "ED25519 DIGITAL SIGNATURES  //  CONTINUOUS SHA-256 LEDGER", fill=C_TITANIUM, font=FONT_SUBTITLE)

    # 3 Blockchain Nodes
    blocks = [
        ("BLOCK #1052", "INT_C3F9", "ALLOW", "SHA-256: 8a4c197d..."),
        ("BLOCK #1053", "INT_03A5", "REWRITE", "SHA-256: 3d7b22f0..."),
        ("BLOCK #1054", "INT_E219", "BLOCK", "SHA-256: f19e88cb...")
    ]

    block_w = 440
    block_h = 250
    spacing = 50
    total_w = 3 * block_w + 2 * spacing
    start_x = (WIDTH - total_w) // 2

    for i, (b_name, b_int, b_verd, b_hash) in enumerate(blocks):
        bx = start_x + i * (block_w + spacing)
        by = 220

        v_color = C_GREEN if b_verd == "ALLOW" else (C_CHAMPAGNE if b_verd == "REWRITE" else C_RED)
        draw.rectangle([(bx, by), (bx + block_w, by + block_h)], fill=(16, 16, 20), outline=v_color, width=2)
        draw.rectangle([(bx, by), (bx + block_w, by + 50)], fill=(26, 26, 32))
        draw.text((bx + 20, by + 14), b_name, fill=C_WHITE, font=FONT_BODY_BOLD)
        draw.text((bx + block_w - 110, by + 16), b_verd, fill=v_color, font=FONT_BADGE)

        draw.text((bx + 20, by + 75), f"Interaction ID: {b_int}", fill=C_TITANIUM, font=FONT_MONO_SMALL)
        draw.text((bx + 20, by + 105), b_hash, fill=C_CHAMPAGNE, font=FONT_MONO_SMALL)
        draw.text((bx + 20, by + 140), "Signature: Ed25519 Verified [OK]", fill=C_GREEN, font=FONT_MONO_SMALL)
        draw.text((bx + 20, by + 175), "Ledger: Append-Only Trigger Locked", fill=C_WHITE, font=FONT_MONO_SMALL)

        if i < 2:
            conn_x = bx + block_w
            conn_y = by + block_h // 2
            draw.line([(conn_x, conn_y), (conn_x + spacing, conn_y)], fill=C_GREEN, width=3)
            pulse_x = conn_x + int((f_rel * 6) % spacing)
            draw.ellipse([(pulse_x - 5, conn_y - 5), (pulse_x + 5, conn_y + 5)], fill=C_WHITE)

    # SQLite Abort Trigger Box
    draw.rectangle([(cx - 520, 530), (cx + 520, 740)], fill=(14, 14, 18), outline=C_BORDER, width=1)
    draw.text((cx - 460, 560), "🛡️ MATHEMATICAL NON-REPUDIATION ENFORCED BY SQLITE TRIGGERS", fill=C_GREEN, font=FONT_BODY_BOLD)
    code_text = (
        "CREATE TRIGGER abort_audit_update BEFORE UPDATE ON audit_log\n"
        "BEGIN\n"
        "    SELECT RAISE(ABORT, 'Audit log is append-only: UPDATE is strictly forbidden');\n"
        "END;"
    )
    draw.text((cx - 460, 605), code_text, fill=C_TITANIUM, font=FONT_MONO_SMALL, spacing=6)

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


# -----------------------------------------------------------------------------
# SCENE 5: THE GRAND FINALE // 5 LINES OF CODE CTA (Frames 714 - 900, 23.8s - 30.0s)
# -----------------------------------------------------------------------------

def render_act_5(f_rel):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)

    f_global = 714 + f_rel
    draw_marquee_ribbon(draw, f_global, y=14)
    draw_marquee_ribbon(draw, f_global, y=HEIGHT - 35)

    cx, cy = WIDTH // 2, HEIGHT // 2 - 20
    t = f_rel / 30.0

    # Concentric expanding energy waves
    for r in [200, 320, 440, 560]:
        radius = r + int(20 * math.sin(t * 5 + r))
        draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)], outline=(30, 25, 20), width=1)

    # Center Hero Title Lockup
    draw.rectangle([(cx - 200, cy - 180), (cx + 200, cy - 140)], fill=(20, 20, 24), outline=C_GREEN, width=1)
    draw.text((cx - 180, cy - 172), "⚡ DIGITAL WORKER // META MUSE-SPARK-1.3", fill=C_GREEN, font=FONT_BADGE)

    draw.text((cx - 200, cy - 120), "SATYAHD", fill=C_WHITE, font=FONT_HERO)
    draw.text((cx - 260, cy - 20), "ZERO TRUST. ZERO LIABILITY.", fill=C_CHAMPAGNE, font=FONT_SUBTITLE)

    # 4 Feature Badges
    badges = [
        "✓ 5 Lines of Code Drop-In",
        "✓ Model Context Protocol (MCP)",
        "✓ HTTP REST API & Webhooks",
        "✓ 100% Adversarial Containment"
    ]
    px_start = cx - 460
    py = cy + 55
    for i, badge in enumerate(badges):
        row = i // 2
        col = i % 2
        bx = px_start + col * 480
        by = py + row * 60
        draw.rectangle([(bx, by), (bx + 440, by + 46)], fill=C_SURFACE_ELEVATED, outline=C_BORDER, width=1)
        draw.text((bx + 25, by + 12), badge, fill=C_TITANIUM, font=FONT_BADGE)

    # Repository Banner
    draw.rectangle([(cx - 340, cy + 205), (cx + 340, cy + 275)], fill=(25, 18, 12), outline=C_CHAMPAGNE, width=2)
    draw.text((cx - 275, cy + 225), "github.com/Akileshwarakrishnan/satyahd", fill=C_WHITE, font=FONT_BODY_BOLD)

    # Smooth black fade-out at end (last 12 frames)
    if f_rel > 174:
        fade = min(1.0, (f_rel - 174) / 12.0)
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, int(255 * fade)))
        img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def main():
    print("=" * 70)
    print("  🎬 BUILDING CINEMATIC 30-SECOND TEASER ANIMATION VIDEO")
    print("=" * 70)

    master_audio_wav = build_cinematic_audio()

    print(f"\n[Step 2/3] Rendering {TOTAL_FRAMES} frames @ 30fps (1920x1080) to FFmpeg...")

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "bgr24",
        "-r", str(FPS),
        "-i", "-",
        "-i", master_audio_wav,
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
        if f < 174:
            frame_bgr = render_act_1(f)
        elif f < 354:
            frame_bgr = render_act_2(f - 174)
        elif f < 546:
            frame_bgr = render_act_3(f - 354)
        elif f < 714:
            frame_bgr = render_act_4(f - 546)
        else:
            frame_bgr = render_act_5(f - 714)

        proc.stdin.write(frame_bgr.tobytes())

        if (f + 1) % 90 == 0:
            pct = (f + 1) / TOTAL_FRAMES * 100
            print(f"  Frame {f+1}/{TOTAL_FRAMES} ({pct:.0f}%) rendered...")

    proc.stdin.close()
    proc.wait()

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
