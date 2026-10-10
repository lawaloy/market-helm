#!/usr/bin/env python3
"""Render the animated README hero loop (WebP + GIF).

Reuses the layout of compose_readme_hero.py (static hero) as a function of
time. Frames are composed at 1.25x design units (2000x1325), then downsampled
to the delivery width. Requires Pillow, numpy and ffmpeg (for the GIF).

    python compose_loop.py --dashboard dashboard2x.png --alerts alerts2x.png \
        --mark mark.png --font Inter-Variable.ttf --out hero-loop
"""

import argparse
import math
import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

K = 1.25
DW, DH = 1600, 1060
W, H = int(DW * K), int(DH * K)
DURATION = 9.2
FPS = 30
OUT_W = 1000
OUT_H = round(OUT_W * H / W)

ARGS = None
LAYERS = {}


def S(v):
    return int(round(v * K))


def clamp01(x):
    return max(0.0, min(1.0, x))


def seg(t, a, b):
    return clamp01((t - a) / (b - a))


def out_expo(x):
    return 1.0 if x >= 1 else 1 - 2 ** (-10 * x)


def out_cubic(x):
    return 1 - (1 - x) ** 3


def smooth(x):
    return x * x * (3 - 2 * x)


def font(sz, w):
    f = ImageFont.truetype(ARGS.font, S(sz))
    try:
        f.set_variation_by_axes([min(32, max(14, sz)), w])
    except Exception:
        pass
    return f


def blur_layer(draw_fn, radius):
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    return layer.filter(ImageFilter.GaussianBlur(S(radius)))


def rounded(im, r):
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), S(r), fill=255)
    o = im.convert("RGBA")
    o.putalpha(m)
    return o


def crop(layer, pad=0):
    """Trim a full-canvas RGBA layer to its bbox: (image, (x, y))."""
    bb = layer.getchannel("A").point(lambda v: 255 if v > 0 else 0).getbbox()
    if bb is None:
        return Image.new("RGBA", (1, 1)), (0, 0)
    return layer.crop(bb), (bb[0], bb[1])


def over(base, item, dx=0.0, dy=0.0, op=1.0, mask=None):
    """Alpha-composite (img, pos) onto an RGB base with offset and opacity."""
    if op <= 0.002:
        return
    im, (x, y) = item
    a = im.getchannel("A")
    if mask is not None:
        a = ImageChops.multiply(a, mask)
    if op < 1:
        a = a.point(lambda v: int(v * op))
    base.paste(im.convert("RGB"), (int(round(x + dx)), int(round(y + dy))), a)


def build_background():
    grad = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        a, b = (5, 12, 22), (9, 22, 38)
        grad.putpixel((0, y), tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    base = grad.resize((W, H))
    glows = [
        ((450, -120, 1150, 320), (16, 185, 129, 70), 90),
        ((160, 380, 1180, 940), (16, 185, 129, 95), 120),
        ((900, 620, 1560, 1040), (20, 184, 166, 80), 110),
    ]
    LAYERS["glows"] = []
    for box, col, rad in glows:
        m = S(120)
        lay = Image.new("RGBA", (W + 2 * m, H + 2 * m), (0, 0, 0, 0))
        ImageDraw.Draw(lay).ellipse(tuple(S(v) + m for v in box), fill=col)
        lay = lay.filter(ImageFilter.GaussianBlur(S(rad)))
        LAYERS["glows"].append((lay, (-m, -m)))
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
    LAYERS["dots"] = (dots, (0, 0))
    LAYERS["base"] = base


def build_text():
    tmp = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(tmp)
    mark = Image.open(ARGS.mark).convert("RGBA").resize((S(40), S(40)), Image.LANCZOS)
    fb = font(22, 700)
    name = "MarketHelm"
    sp = 1.2

    def spaced_w():
        return sum(d.textlength(c, font=fb) + sp * K for c in name) - sp * K

    total = S(40) + S(12) + spaced_w()
    bx = (W - total) / 2
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lay.alpha_composite(mark, (int(bx), S(34)))
    ld = ImageDraw.Draw(lay)
    x = bx + S(52)
    for ch in name:
        ld.text((x, S(40)), ch, font=fb, fill=(226, 236, 246, 255))
        x += d.textlength(ch, font=fb) + sp * K
    LAYERS["brand"] = crop(lay)

    fh = font(76, 800)
    l1, l2 = "Your market, ", "at the helm."
    w1, w2 = d.textlength(l1, font=fh), d.textlength(l2, font=fh)
    hx, hy = (W - (w1 + w2)) / 2, S(100)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text((hx, hy), l1, font=fh, fill=(255, 255, 255, 255))
    LAYERS["head1"] = crop(lay)
    m = Image.new("L", (W, H), 0)
    ImageDraw.Draw(m).text((hx + w1, hy), l2, font=fh, fill=255)
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    x0, x1 = int(hx + w1), int(hx + w1 + w2)
    for x in range(x0, x1 + 1):
        t = (x - x0) / max(1, x1 - x0)
        c = (int(110 - 94 * t), int(231 - 46 * t), int(183 - 54 * t), 255)
        gd.line((x, hy, x, hy + S(110)), fill=c)
    g.putalpha(ImageChops.multiply(g.getchannel("A"), m))
    LAYERS["head2"] = crop(g)

    fs = font(26, 400)
    sub = "Screen the market, see five-day projections, and get alerts when it moves your way."
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(lay).text(
        ((W - d.textlength(sub, font=fs)) / 2, S(206)), sub, font=fs, fill=(150, 168, 188, 255)
    )
    LAYERS["sub"] = crop(lay)


def build_window():
    dash = Image.open(ARGS.dashboard).convert("RGB")
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
    LAYERS["box"] = box
    LAYERS["ground"] = crop(
        blur_layer(
            lambda d: d.ellipse(
                (wx + S(80), box[3] - S(40), box[2] - S(80), box[3] + S(50)),
                fill=(16, 185, 129, 110),
            ),
            50,
        )
    )
    LAYERS["shadow"] = crop(
        blur_layer(
            lambda d: d.rounded_rectangle(
                (box[0], box[1] + S(28), box[2], box[3] + S(28)), S(22), fill=(0, 0, 0, 210)
            ),
            42,
        )
    )
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lay.alpha_composite(rounded(win, 22), (wx, wy))
    od = ImageDraw.Draw(lay)
    ol = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ol)
    od.rounded_rectangle(box, S(22), outline=(255, 255, 255, 46), width=S(1))
    for i in range(S(300)):
        a = int(70 * (1 - abs(i - S(150)) / S(150)))
        od.point((wx + S(60) + i * 2, wy), fill=(255, 255, 255, max(0, a)))
    lay.alpha_composite(ol)
    LAYERS["window"] = crop(lay)


def build_alert():
    box = LAYERS["box"]
    al = Image.open(ARGS.alerts).convert("RGB")
    aw0, ah0 = al.size
    al = al.crop((int(aw0 * 0.2444), int(ah0 * 0.3174), int(aw0 * 0.9111), int(ah0 * 0.5840)))
    aw = S(640)
    ah = int(al.height * aw / al.width)
    al = al.resize((aw, ah), Image.LANCZOS)
    ax, ay = S(870), box[3] - ah + S(84)
    ab = (ax, ay, ax + aw, ay + ah)

    def glow(spread, rad):
        return crop(
            blur_layer(
                lambda d: d.rounded_rectangle(
                    (ab[0] - S(spread), ab[1] - S(spread), ab[2] + S(spread), ab[3] + S(spread)),
                    S(24),
                    outline=(52, 211, 153, 200),
                    width=S(8),
                ),
                rad,
            )
        )

    LAYERS["a_glow"] = glow(6, 14)
    LAYERS["a_pulse"] = glow(14, 30)
    LAYERS["a_shadow"] = crop(
        blur_layer(
            lambda d: d.rounded_rectangle(
                (ab[0], ab[1] + S(22), ab[2], ab[3] + S(22)), S(18), fill=(0, 0, 0, 235)
            ),
            30,
        )
    )
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lay.alpha_composite(rounded(al, 18), (ax, ay))
    ImageDraw.Draw(lay).rounded_rectangle(ab, S(18), outline=(52, 211, 153, 190), width=S(2))
    LAYERS["a_card"] = crop(lay)


def build_pills():
    fp = font(21, 600)
    items = ["Screens major indices", "Five-day projections", "Alerts by email, Slack, or Discord"]
    pad, gap, ph, ic = S(22), S(16), S(46), S(22)
    tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
    widths = [int(tmp.textlength(t, font=fp)) + pad * 2 + ic + S(10) for t in items]
    x = (W - (sum(widths) + gap * 2)) // 2
    y = S(986)
    LAYERS["pills"] = []
    for t, wd_ in zip(items, widths):
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        lay.alpha_composite(
            _pill_bg(x, y, wd_, ph),
        )
        d = ImageDraw.Draw(lay)
        cx, cy = x + pad + ic // 2, y + ph // 2
        d.ellipse(
            (cx - ic // 2, cy - ic // 2, cx + ic // 2, cy + ic // 2), fill=(52, 211, 153, 255)
        )
        d.line(
            [(cx - S(5), cy), (cx - S(1.5), cy + S(4)), (cx + S(5.5), cy - S(4))],
            fill=(6, 40, 30, 255),
            width=S(2.4),
            joint="curve",
        )
        d.text(
            (x + pad + ic + S(10), y + (ph - S(21)) // 2 - S(2)),
            t,
            font=fp,
            fill=(190, 246, 220, 255),
        )
        LAYERS["pills"].append(crop(lay))
        x += wd_ + gap


def _pill_bg(x, y, w, ph):
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle(
        (x, y, x + w, y + ph),
        ph // 2,
        fill=(16, 185, 129, 34),
        outline=(52, 211, 153, 120),
        width=S(1),
    )
    return lay


def build_all():
    build_background()
    build_text()
    build_window()
    build_alert()
    build_pills()


def sweep_mask(item, p):
    """Soft left-to-right wipe over a cropped layer; p in 0..1."""
    im = item[0]
    w, h = im.size
    edge = max(1, S(140))
    xs = np.arange(w, dtype=np.float32)
    front = -edge + p * (w + edge)
    a = np.clip((front - xs) / edge + 1.0, 0, 1)
    arr = np.tile((a * 255).astype(np.uint8), (h, 1))
    return Image.fromarray(arr, "L")


def scene(t, fade):
    if not LAYERS:
        build_all()
    # camera: slow push, easing back during the fade-out so the loop closes
    push = smooth(seg(t, 0.0, 7.7))
    ret = smooth(seg(t, 7.7, DURATION))
    cam = 1.0 + 0.03 * push * (1 - ret)
    phase = 2 * math.pi * t / DURATION  # periodic drift for glows

    im = LAYERS["base"].copy()
    for i, g in enumerate(LAYERS["glows"]):
        ang = phase + i * 2.1
        over(im, g, dx=S(18) * math.sin(ang), dy=S(12) * math.cos(ang))
    over(im, LAYERS["dots"])

    # brand + headline + subline
    p = out_expo(seg(t, 0.1, 0.7))
    over(im, LAYERS["brand"], dy=S(14) * (1 - p), op=p * fade)
    p = out_expo(seg(t, 0.2, 0.95))
    over(im, LAYERS["head1"], dy=S(22) * (1 - p), op=p * fade)
    pw = seg(t, 0.35, 1.3)
    pf = out_expo(pw)
    if pf > 0:
        over(
            im,
            LAYERS["head2"],
            dy=S(22) * (1 - pf),
            op=fade,
            mask=sweep_mask(LAYERS["head2"], out_cubic(pw)),
        )
    p = out_expo(seg(t, 0.8, 1.5))
    over(im, LAYERS["sub"], dy=S(12) * (1 - p), op=p * fade)

    # dashboard window
    pw = seg(t, 0.9, 2.2)
    p = out_expo(pw)
    rise = S(70) * (1 - p)
    over(im, LAYERS["ground"], dy=rise * 0.6, op=smooth(pw) * fade)
    over(im, LAYERS["shadow"], dy=rise, op=p * fade)
    over(im, LAYERS["window"], dy=rise, op=p * fade)

    # alert card with a single glow pulse
    pa = seg(t, 2.0, 3.0)
    p = out_expo(pa)
    dx, dy = S(90) * (1 - p), S(70) * (1 - p)
    over(im, LAYERS["a_shadow"], dx, dy, op=p * fade)
    over(im, LAYERS["a_glow"], dx, dy, op=p * fade)
    pulse = math.sin(math.pi * seg(t, 2.7, 4.0)) ** 2
    over(im, LAYERS["a_pulse"], dx, dy, op=0.85 * pulse * fade)
    over(im, LAYERS["a_card"], dx, dy, op=p * fade)

    # proof pills, one by one
    for i, pill in enumerate(LAYERS["pills"]):
        p = out_cubic(seg(t, 3.4 + 0.3 * i, 4.0 + 0.3 * i))
        over(im, pill, dy=S(14) * (1 - p), op=p * fade)

    # camera push: crop a shrinking window about the centre
    cw, ch = W / cam, H / cam
    box = ((W - cw) / 2, (H - ch) / 2 - S(6) * (cam - 1) * 10, (W + cw) / 2, 0)
    box = (box[0], box[1], box[2], box[1] + ch)
    return im.resize((OUT_W, OUT_H), Image.LANCZOS, box=box)


def render_frame(t):
    """Fade the whole composition as one flattened image so layers never ghost."""
    fade = 1 - smooth(seg(t, 7.7, DURATION))
    full = scene(t, 1.0)
    if fade >= 0.999:
        return full
    return Image.blend(scene(t, 0.0), full, fade)


def _work(args):
    i, path = args
    render_frame(i / FPS).save(path, compress_level=1)
    return i


def main():
    global ARGS
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dashboard", required=True)
    ap.add_argument("--alerts", required=True)
    ap.add_argument("--mark", required=True)
    ap.add_argument("--font", required=True, help="Path to the Inter variable font (.ttf)")
    ap.add_argument("--out", required=True, help="Output path prefix (no extension)")
    ap.add_argument("--webp-quality", type=int, default=54)
    ap.add_argument("--webp-fps", type=int, default=24)
    ap.add_argument("--frames-dir", help="Keep/reuse rendered PNG frames in this directory")
    ap.add_argument("--gif-fps", type=int, default=12)
    ap.add_argument("--gif-width", type=int, default=800)
    ap.add_argument("--gif-colors", type=int, default=64)
    ap.add_argument("--previews", default="0.3,1.2,2.6,4.6", help="Preview frame times (s)")
    ARGS = ap.parse_args()

    out = Path(ARGS.out)
    n = int(DURATION * FPS)
    tmp = Path(ARGS.frames_dir or tempfile.mkdtemp(prefix="hero-loop-"))
    tmp.mkdir(parents=True, exist_ok=True)
    jobs = [(i, tmp / f"f{i:04d}.png") for i in range(n)]
    if not (tmp / f"f{n - 1:04d}.png").exists():
        with ProcessPoolExecutor(initializer=_init, initargs=(vars(ARGS),)) as ex:
            list(ex.map(_work, jobs, chunksize=4))

    for s in ARGS.previews.split(","):
        i = min(n - 1, int(float(s) * FPS))
        shutil.copy(jobs[i][1], f"{out}-preview-{float(s):g}s.png")

    step = FPS / ARGS.webp_fps
    picks = sorted({int(k * step) for k in range(int(DURATION * ARGS.webp_fps))})
    frames = [Image.open(jobs[i][1]) for i in picks]
    frames[0].save(
        f"{out}.webp",
        save_all=True,
        append_images=frames[1:],
        duration=round(1000 / ARGS.webp_fps),
        loop=0,
        quality=ARGS.webp_quality,
        method=6,
    )
    gw = ARGS.gif_width
    vf = (
        f"fps={ARGS.gif_fps},scale={gw}:-1:flags=lanczos,split[a][b];"
        f"[a]palettegen=max_colors={ARGS.gif_colors}:stats_mode=full[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(FPS),
            "-i",
            str(tmp / "f%04d.png"),
            "-vf",
            vf,
            "-loop",
            "0",
            f"{out}.gif",
        ],
        check=True,
    )
    if not ARGS.frames_dir:
        shutil.rmtree(tmp, ignore_errors=True)


def _init(argd):
    global ARGS
    ARGS = argparse.Namespace(**argd)


if __name__ == "__main__":
    main()
