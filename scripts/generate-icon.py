"""Generate VoiceOver app icon — orange microphone on dark navy background."""

from PIL import Image, ImageDraw
import subprocess
import shutil
import os

ICON_DIR = os.path.join(os.path.dirname(__file__), '..', 'src-tauri', 'icons')

# Colors matching the app theme
BG_COLOR = (15, 23, 42)       # #0f172a - app background
MIC_COLOR = (249, 115, 22)    # #f97316 - orange accent
HIGHLIGHT = (251, 146, 60)    # #fb923c - lighter orange for highlight
RING_COLOR = (51, 65, 85)     # #334155 - subtle ring


def draw_microphone(size=1024):
    """Draw a studio condenser microphone icon."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size  # shorthand

    # Background circle (macOS will mask to rounded rect)
    pad = int(s * 0.02)
    d.rounded_rectangle([pad, pad, s - pad, s - pad], radius=int(s * 0.22), fill=BG_COLOR)

    # Subtle outer glow/ring
    d.rounded_rectangle([pad, pad, s - pad, s - pad], radius=int(s * 0.22), outline=RING_COLOR, width=int(s * 0.005))

    # --- Microphone body (capsule shape) ---
    mic_w = int(s * 0.28)
    mic_h = int(s * 0.42)
    mic_cx = s // 2
    mic_top = int(s * 0.15)
    mic_left = mic_cx - mic_w // 2
    mic_right = mic_cx + mic_w // 2
    mic_bottom = mic_top + mic_h

    # Mic body rounded rectangle
    d.rounded_rectangle(
        [mic_left, mic_top, mic_right, mic_bottom],
        radius=mic_w // 2,
        fill=MIC_COLOR
    )

    # Highlight stripe on the left side of mic body
    hl_w = int(mic_w * 0.15)
    hl_left = mic_left + int(mic_w * 0.22)
    d.rounded_rectangle(
        [hl_left, mic_top + int(mic_h * 0.1), hl_left + hl_w, mic_bottom - int(mic_h * 0.1)],
        radius=hl_w // 2,
        fill=HIGHLIGHT
    )

    # --- Grill lines on mic head ---
    grill_top = mic_top + int(mic_h * 0.08)
    grill_bottom = mic_top + int(mic_h * 0.55)
    line_spacing = int(mic_h * 0.065)
    line_width = max(2, int(s * 0.006))

    # Darker orange for grill lines
    grill_color = (194, 85, 15)  # darker orange

    y = grill_top + line_spacing
    while y < grill_bottom:
        # Calculate line width at this y position (narrower near top/bottom of capsule)
        rel_y = (y - mic_top) / mic_h
        if rel_y < 0.28:  # In the top rounded part
            frac = rel_y / 0.28
            width_frac = (frac * (2 - frac)) ** 0.5
        else:
            width_frac = 1.0
        inset = int((1 - width_frac) * mic_w * 0.5) + int(mic_w * 0.1)
        d.line(
            [(mic_left + inset, y), (mic_right - inset, y)],
            fill=grill_color, width=line_width
        )
        y += line_spacing

    # --- Stand/mount arc below mic body ---
    arc_w = int(s * 0.36)
    arc_top = mic_bottom - int(s * 0.02)
    arc_bottom = mic_bottom + int(s * 0.18)
    arc_left = mic_cx - arc_w // 2
    arc_right = mic_cx + arc_w // 2
    arc_thickness = max(3, int(s * 0.025))

    d.arc(
        [arc_left, arc_top, arc_right, arc_bottom + (arc_bottom - arc_top)],
        start=0, end=180,
        fill=MIC_COLOR, width=arc_thickness
    )

    # --- Vertical stand line ---
    stand_top = arc_bottom
    stand_bottom = int(s * 0.82)
    stand_width = max(3, int(s * 0.025))
    d.line(
        [(mic_cx, stand_top), (mic_cx, stand_bottom)],
        fill=MIC_COLOR, width=stand_width
    )

    # --- Base (horizontal line) ---
    base_w = int(s * 0.22)
    base_y = stand_bottom
    d.line(
        [(mic_cx - base_w // 2, base_y), (mic_cx + base_w // 2, base_y)],
        fill=MIC_COLOR, width=stand_width
    )

    # Rounded caps on the base
    cap_r = stand_width // 2 + 1
    d.ellipse(
        [mic_cx - base_w // 2 - cap_r, base_y - cap_r,
         mic_cx - base_w // 2 + cap_r, base_y + cap_r],
        fill=MIC_COLOR
    )
    d.ellipse(
        [mic_cx + base_w // 2 - cap_r, base_y - cap_r,
         mic_cx + base_w // 2 + cap_r, base_y + cap_r],
        fill=MIC_COLOR
    )

    return img


def main():
    os.makedirs(ICON_DIR, exist_ok=True)

    # Generate master icon at 1024x1024
    master = draw_microphone(1024)

    # Required sizes for Tauri
    sizes = {
        'icon.png': 512,
        '32x32.png': 32,
        '128x128.png': 128,
        '128x128@2x.png': 256,
        # Windows store logos
        'Square30x30Logo.png': 30,
        'Square44x44Logo.png': 44,
        'Square71x71Logo.png': 71,
        'Square89x89Logo.png': 89,
        'Square107x107Logo.png': 107,
        'Square142x142Logo.png': 142,
        'Square150x150Logo.png': 150,
        'Square284x284Logo.png': 284,
        'Square310x310Logo.png': 310,
        'StoreLogo.png': 50,
    }

    for filename, size in sizes.items():
        resized = master.resize((size, size), Image.LANCZOS)
        resized.save(os.path.join(ICON_DIR, filename), 'PNG')
        print(f"  {filename} ({size}x{size})")

    # Create ICO (Windows)
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    imgs = []
    for sz in ico_sizes:
        imgs.append(master.resize((sz, sz), Image.LANCZOS).convert('RGBA'))
    imgs[0].save(
        os.path.join(ICON_DIR, 'icon.ico'),
        format='ICO',
        sizes=[(im.width, im.height) for im in imgs],
        append_images=imgs[1:]
    )
    print("  icon.ico")

    # Create ICNS (macOS) using iconutil
    iconset_dir = os.path.join(ICON_DIR, 'icon.iconset')
    os.makedirs(iconset_dir, exist_ok=True)

    icns_sizes = {
        'icon_16x16.png': 16,
        'icon_16x16@2x.png': 32,
        'icon_32x32.png': 32,
        'icon_32x32@2x.png': 64,
        'icon_128x128.png': 128,
        'icon_128x128@2x.png': 256,
        'icon_256x256.png': 256,
        'icon_256x256@2x.png': 512,
        'icon_512x512.png': 512,
        'icon_512x512@2x.png': 1024,
    }

    for filename, size in icns_sizes.items():
        resized = master.resize((size, size), Image.LANCZOS)
        resized.save(os.path.join(iconset_dir, filename), 'PNG')

    # Run iconutil to create .icns
    result = subprocess.run(
        ['iconutil', '-c', 'icns', iconset_dir, '-o', os.path.join(ICON_DIR, 'icon.icns')],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("  icon.icns")
        shutil.rmtree(iconset_dir)
    else:
        print(f"  WARNING: iconutil failed: {result.stderr}")

    print("\nDone! All icons generated.")


if __name__ == '__main__':
    main()
