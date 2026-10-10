#!/usr/bin/env python3
"""Compose the README hero image (docs/assets/readme/markethelm-hero.png).

Inputs are the README screenshots produced by e2e/scripts/capture-readme.mjs.
For crisp text, capture at 2x into a temp folder first:

    README_CAPTURE_SCALE=2 README_CAPTURE_OUT=/tmp/readme-2x node e2e/scripts/capture-readme.mjs
    python scripts/compose_readme_hero.py --dashboard /tmp/readme-2x/markethelm-dashboard.png \
        --alerts /tmp/readme-2x/markethelm-alerts.png --font /path/to/Inter-Variable.ttf

Requires Pillow and the Inter variable font.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets" / "readme"
ap = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
)
ap.add_argument("--dashboard", default=str(ASSETS / "markethelm-dashboard.png"))
ap.add_argument("--alerts", default=str(ASSETS / "markethelm-alerts.png"))
ap.add_argument("--mark", default=str(ASSETS / "markethelm-mark.png"))
ap.add_argument("--font", required=True, help="Path to the Inter variable font (.ttf)")
ap.add_argument("--out", default=str(ASSETS / "markethelm-hero.png"))
args = ap.parse_args()
K = 2
W, H = 1600 * K, 1060 * K


def S(v):
    return int(round(v * K))


FONT = args.font


def font(sz, w):
    f = ImageFont.truetype(FONT, S(sz))
    try:
        f.set_variation_by_axes([min(32, max(14, sz)), w])
    except Exception:
        pass
    return f


def text_w(d, t, f, sp=0):
    return d.textlength(t, font=f) + sp * K * (len(t) - 1)


def draw_spaced(d, xy, t, f, fill, sp=0):
    x, y = xy
    for ch in t:
        d.text((x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) + sp * K


def rounded(im, r):
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), S(r), fill=255)
    o = im.convert("RGBA")
    o.putalpha(m)
    return o


def blur_layer(draw_fn, radius):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    return layer.filter(ImageFilter.GaussianBlur(S(radius)))


# ---- background
bg = Image.new("RGB", (W, H), (6, 14, 25))
grad = Image.new("RGB", (1, H))
for y in range(H):
    t = y / (H - 1)
    a = (5, 12, 22)
    b = (9, 22, 38)
    grad.putpixel((0, y), tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
bg = grad.resize((W, H)).convert("RGBA")
# glows: top spotlight, cluster glow
bg.alpha_composite(
    blur_layer(lambda d: d.ellipse((S(450), S(-120), S(1150), S(320)), fill=(16, 185, 129, 70)), 90)
)
bg.alpha_composite(
    blur_layer(lambda d: d.ellipse((S(160), S(380), S(1180), S(940)), fill=(16, 185, 129, 95)), 120)
)
bg.alpha_composite(
    blur_layer(
        lambda d: d.ellipse((S(900), S(620), S(1560), S(1040)), fill=(20, 184, 166, 80)), 110
    )
)
# dot grid with radial fade
dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
dd = ImageDraw.Draw(dots)
sp = S(36)
for gy in range(sp // 2, H, sp):
    for gx in range(sp // 2, W, sp):
        dd.ellipse((gx - S(1), gy - S(1), gx + S(1), gy + S(1)), fill=(148, 200, 180, 34))
mask = Image.new("L", (W, H), 0)
ImageDraw.Draw(mask).ellipse((S(-100), S(60), S(1700), S(1100)), fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(S(180)))
dots.putalpha(ImageChops.multiply(dots.getchannel("A"), mask))
bg.alpha_composite(dots)

d = ImageDraw.Draw(bg)
# ---- brand row
mark = Image.open(args.mark).convert("RGBA").resize((S(40), S(40)), Image.LANCZOS)
fb = font(22, 700)
name = "MarketHelm"
nw = text_w(d, name, fb, 1.2)
total = S(40) + S(12) + nw
bx = (W - total) / 2
bg.alpha_composite(mark, (int(bx), S(34)))
draw_spaced(d, (bx + S(52), S(40)), name, fb, (226, 236, 246, 255), 1.2)

# ---- headline with gradient accent
fh = font(76, 800)
l1 = "Your market, "
l2 = "at the helm."
w1 = d.textlength(l1, font=fh)
w2 = d.textlength(l2, font=fh)
hx = (W - (w1 + w2)) / 2
hy = S(100)
d.text((hx, hy), l1, font=fh, fill=(255, 255, 255, 255))
m = Image.new("L", (W, H), 0)
ImageDraw.Draw(m).text((hx + w1, hy), l2, font=fh, fill=255)
g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(g)
x0 = int(hx + w1)
x1 = int(hx + w1 + w2)
for x in range(x0, x1 + 1):
    t = (x - x0) / max(1, x1 - x0)
    c = (int(110 + (16 - 110) * t), int(231 + (185 - 231) * t), int(183 + (129 - 183) * t), 255)
    gd.line((x, hy, x, hy + S(110)), fill=c)
g.putalpha(ImageChops.multiply(g.getchannel("A"), m))
bg.alpha_composite(g)
d = ImageDraw.Draw(bg)
fs = font(26, 400)
sub = "Screen the market, see five-day projections, and get alerts when it moves your way."
d.text(((W - d.textlength(sub, font=fs)) / 2, S(206)), sub, font=fs, fill=(150, 168, 188, 255))

# ---- dashboard window
dash = Image.open(args.dashboard).convert("RGB")
dw = S(1020)
dh = int(dash.height * dw / dash.width)
dash = dash.resize((dw, dh), Image.LANCZOS)
bar = S(38)
win = Image.new("RGB", (dw, dh + bar), (11, 22, 36))
wd = ImageDraw.Draw(win)
for i, c in enumerate([(255, 95, 87), (254, 188, 46), (40, 200, 64)]):
    wd.ellipse((S(18 + i * 22), S(13), S(30 + i * 22), S(25)), fill=c)
win.paste(dash, (0, bar))
wx, wy = S(90), S(272)
box = (wx, wy, wx + dw, wy + dh + bar)
# ground glow + shadow
bg.alpha_composite(
    blur_layer(
        lambda d: d.ellipse(
            (wx + S(80), box[3] - S(40), box[2] - S(80), box[3] + S(50)), fill=(16, 185, 129, 110)
        ),
        50,
    )
)
bg.alpha_composite(
    blur_layer(
        lambda d: d.rounded_rectangle(
            (box[0], box[1] + S(28), box[2], box[3] + S(28)), S(22), fill=(0, 0, 0, 210)
        ),
        42,
    )
)
bg.alpha_composite(rounded(win, 22), (wx, wy))
ol = Image.new("RGBA", (W, H), (0, 0, 0, 0))
od = ImageDraw.Draw(ol)
od.rounded_rectangle(box, S(22), outline=(255, 255, 255, 46), width=S(1))
# top highlight
for i in range(S(300)):
    a = int(70 * (1 - abs(i - S(150)) / S(150)))
    od.point((wx + S(60) + i * 2, wy), fill=(255, 255, 255, max(0, a)))
bg.alpha_composite(ol)

# ---- alert card
al = Image.open(args.alerts).convert("RGB")
aw0, ah0 = al.size
al = al.crop((int(aw0 * 0.2444), int(ah0 * 0.3174), int(aw0 * 0.9111), int(ah0 * 0.5840)))
aw = S(640)
ah = int(al.height * aw / al.width)
al = al.resize((aw, ah), Image.LANCZOS)
ax = S(870)
ay = box[3] - ah + S(84)
abox = (ax, ay, ax + aw, ay + ah)
bg.alpha_composite(
    blur_layer(
        lambda d: d.rounded_rectangle(
            (abox[0] - S(6), abox[1] - S(6), abox[2] + S(6), abox[3] + S(6)),
            S(24),
            outline=(52, 211, 153, 200),
            width=S(8),
        ),
        14,
    )
)
bg.alpha_composite(
    blur_layer(
        lambda d: d.rounded_rectangle(
            (abox[0], abox[1] + S(22), abox[2], abox[3] + S(22)), S(18), fill=(0, 0, 0, 235)
        ),
        30,
    )
)
bg.alpha_composite(rounded(al, 18), (ax, ay))
ImageDraw.Draw(bg).rounded_rectangle(abox, S(18), outline=(52, 211, 153, 190), width=S(2))

# ---- proof pills
fp = font(21, 600)
items = ["Screens major indices", "Five-day projections", "Alerts by email, Slack, or Discord"]
pad = S(22)
gap = S(16)
ph = S(46)
ic = S(22)
tmp = ImageDraw.Draw(bg)
widths = [int(tmp.textlength(t, font=fp)) + pad * 2 + ic + S(10) for t in items]
tot = sum(widths) + gap * (len(items) - 1)
x = (W - tot) // 2
y = S(986)
pl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
pd = ImageDraw.Draw(pl)
xs = []
for t, wd_ in zip(items, widths):
    pd.rounded_rectangle(
        (x, y, x + wd_, y + ph),
        ph // 2,
        fill=(16, 185, 129, 34),
        outline=(52, 211, 153, 120),
        width=S(1),
    )
    xs.append(x)
    x += wd_ + gap
bg.alpha_composite(pl)
d = ImageDraw.Draw(bg)
for t, x, wd_ in zip(items, xs, widths):
    cx = x + pad + ic // 2
    cy = y + ph // 2
    d.ellipse((cx - ic // 2, cy - ic // 2, cx + ic // 2, cy + ic // 2), fill=(52, 211, 153, 255))
    d.line(
        [(cx - S(5), cy), (cx - S(1.5), cy + S(4)), (cx + S(5.5), cy - S(4))],
        fill=(6, 40, 30, 255),
        width=S(2.4),
        joint="curve",
    )
    d.text(
        (x + pad + ic + S(10), y + (ph - S(21)) // 2 - S(2)), t, font=fp, fill=(190, 246, 220, 255)
    )

out = bg.convert("RGB").resize((2000, int(2000 * H / W)), Image.LANCZOS)
out.save(args.out, optimize=True)
print(args.out, out.size)
