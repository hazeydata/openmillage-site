"""One-off tool: render assets/og-card.png (1200x630) for link previews. Needs Pillow; the site build does not.
Usage: python3 scripts/render_og_card.py
Palette and fonts are the site's (assets/fonts, redo.py CSS); the tagline is the Headline in content/copy.md, verbatim."""
from PIL import Image, ImageDraw, ImageFont
BG, TEXT, MUTED, CYAN = "#03070F", "#E8EEF5", "#9FB3C8", "#5FC4D6"
TAGLINE = "Your Florida property tax bill is a stack of rates. Here's who sets each one."
assert TAGLINE in open("content/copy.md", encoding="utf-8").read()
W, H, M = 1200, 630, 90
img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
d.rectangle([0, 0, 14, H], fill=CYAN)
d.text((M, 120), "OpenMillage", font=ImageFont.truetype("assets/fonts/SpaceGrotesk-600.ttf", 120), fill=TEXT)
body = ImageFont.truetype("assets/fonts/Inter-600.ttf", 52)
lines, line = [], ""
for w in TAGLINE.split():
    t = (line + " " + w).strip()
    if d.textlength(t, font=body) > W - 2 * M: lines.append(line); line = w
    else: line = t
lines.append(line)
y = 300
for l in lines: d.text((M, y), l, font=body, fill=MUTED); y += 72
d.text((M, H - 80), "openmillage.com", font=ImageFont.truetype("assets/fonts/Inter-400.ttf", 32), fill=CYAN)
img.save("assets/og-card.png", optimize=True)
