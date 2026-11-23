#!/usr/bin/env python3
"""
Generate adaptive Dark & Light Followers Shoutout Text-Path SVGs
(`assets/followers-path.svg` and `assets/followers-path-light.svg`).

Fetches live GitHub followers for --user, embeds crisp circular WebP avatars,
and animates clean `[avatar] @username` items smoothly along a curved SVG wave
path with a smootherstep edge fade mask.
"""
import argparse
import base64
import concurrent.futures
import html
import io
import json
import math
import os
import urllib.request
from pathlib import Path

from PIL import Image

UA = "followers-path/1.0"
FONT_DIR = Path(__file__).resolve().parent / "fonts"
POPPINS_500 = FONT_DIR / "poppins-latin-500-normal.woff2"
POPPINS_600 = FONT_DIR / "poppins-latin-600-normal.woff2"

# Measured Poppins 500 @ 11.5px average character widths for crisp pill sizing
_W500 = {
    "0": 7.37, "1": 4.03, "2": 6.64, "3": 6.83, "4": 7.44,
    "5": 7.35, "6": 7.38, "7": 6.44, "8": 7.34, "9": 7.30,
    "A": 8.02, "B": 7.25, "C": 8.89, "D": 8.15, "E": 6.03,
    "F": 5.92, "G": 8.89, "H": 8.11, "I": 3.04, "J": 6.49,
    "K": 7.28, "L": 5.11, "M": 10.14, "N": 8.29, "O": 9.02,
    "P": 6.84, "Q": 9.05, "R": 7.27, "S": 6.95, "T": 6.49,
    "U": 7.94, "V": 7.98, "W": 11.49, "X": 7.59, "Y": 6.96,
    "Z": 6.42, "a": 7.80, "b": 7.80, "c": 6.90, "d": 7.80,
    "e": 7.10, "f": 3.82, "g": 7.80, "h": 7.46, "i": 3.04,
    "j": 3.04, "k": 6.37, "l": 3.04, "m": 11.95, "n": 7.46,
    "o": 7.34, "p": 7.80, "q": 7.80, "r": 4.42, "s": 6.14,
    "t": 4.28, "u": 7.46, "v": 6.62, "w": 9.49, "x": 5.74,
    "y": 6.69, "z": 5.42, "-": 6.73, "_": 9.18, "@": 11.20,
}


def _user_alive(login, token=None):
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(f"https://api.github.com/users/{login}", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def fetch_followers(user, token=None, max_followers=120):
    followers = []
    page = 1
    headers = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    while len(followers) < max_followers:
        url = f"https://api.github.com/users/{user}/followers?per_page=100&page={page}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            batch = json.load(r)
        if not batch:
            break
        followers.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return followers[:max_followers]


def fetch_avatar_webp(avatar_url, login=None, token=None, size=48):
    sep = "&" if "?" in avatar_url else "?"
    url = f"{avatar_url}{sep}s={size * 2}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        im = im.resize((size, size), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="WEBP", quality=84, method=6)
        return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode(), True
    except Exception:
        # Exclude deleted/suspended accounts (404 on user API) instead of rendering stale ghost profiles
        if login and not _user_alive(login, token=token):
            return None, False
        return None, True


def measure_text(s):
    return sum(_W500.get(ch, 7.2) for ch in s)


def smootherstep(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def fade_stops(fade_width=0.11):
    span = max(0.0, min(0.5, fade_width)) * 100.0
    stops = []
    for i in range(13):
        a = smootherstep(i / 12.0)
        stops.append(f'<stop offset="{(span * i / 12.0):.3f}%" stop-color="#ffffff" stop-opacity="{a:.4f}" />')
    for i in range(12, -1, -1):
        a = smootherstep(i / 12.0)
        stops.append(f'<stop offset="{(100.0 - span * i / 12.0):.3f}%" stop-color="#ffffff" stop-opacity="{a:.4f}" />')
    return "".join(stops)


def build_svg(user, items, dark_mode=True, width=640, height=82, speed=68.0):
    """Build curved Text-Path followers shoutout SVG with collision-free staggered animateMotion."""
    poppins_b64 = base64.b64encode(POPPINS_500.read_bytes()).decode()

    # Graceful compact S-curve centered on 640px for crisp desktop + mobile App legibility
    wave_path = "M -280 43 C -60 17, 160 17, 320 41 C 480 65, 700 65, 920 39"
    path_len = 1224.0
    cross_dur = path_len / max(10.0, speed)

    # Measure widths and auto-tile seamlessly if follower count is small so the curve stays continuous
    base_followers = []
    avatar_r = 12.0
    gap_text = 7.0
    gap_after = 26.0
    for f in items:
        handle = f"@{f['login']}"
        tw = measure_text(handle) * (13.0 / 11.5)
        item_w = avatar_r * 2 + gap_text + tw
        base_followers.append({"login": f["login"], "handle": handle, "avatar": f["avatar"], "w": item_w})

    if not base_followers:
        text_col = "#8b949e" if dark_mode else "#57606a"
        css = f"@font-face{{font-family:'FPop';font-weight:500;src:url(data:font/woff2;base64,{poppins_b64}) format('woff2');}}"
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'role="img" aria-label="Followers shoutout for {html.escape(user)}">'
            f'<title>{html.escape(user)} followers community</title><defs><style>{css}</style></defs>'
            f'<text x="{width/2:.1f}" y="{height/2+4:.1f}" text-anchor="middle" '
            f'font-family="FPop,-apple-system,sans-serif" font-size="13" fill="{text_col}">Open Source Community &amp; Contributors</text></svg>\n'
        )

    base_dts = [
        (base_followers[i]["w"] * 0.5 + gap_after + base_followers[(i + 1) % len(base_followers)]["w"] * 0.5) / speed
        for i in range(len(base_followers))
    ]
    cycle_sum = max(0.5, sum(base_dts))
    repeat_k = max(1, math.ceil((cross_dur + 1.5) / cycle_sum)) if cycle_sum < (cross_dur + 1.5) else 1
    followers = base_followers * repeat_k
    dts = base_dts * repeat_k

    total_dur = max(cross_dur + 1.5, sum(dts))
    frac = min(0.995, cross_dur / total_dur)

    if dark_mode:
        av_ring = "#3fb950"
        av_ring_op = "0.46"
        text_col = "#e6edf3"
        init_bg = "#238636"
    else:
        av_ring = "#1a7f37"
        av_ring_op = "0.38"
        text_col = "#1f2328"
        init_bg = "#1a7f37"

    defs_clips = ['<clipPath id="avc"><circle cx="0" cy="0" r="12" /></clipPath>']
    nodes = []
    cursor_t = 0.0
    for idx, p in enumerate(followers):
        iw = p["w"]
        # Center item horizontally on motion anchor (0,0) so rotation pivots smoothly at item center
        x0 = -iw / 2.0
        av_cx = x0 + avatar_r
        txt_x = av_cx + avatar_r + gap_text

        if p["avatar"]:
            av_el = (
                f'<g transform="translate({av_cx:.1f},0)">'
                f'<image href="{p["avatar"]}" x="-12" y="-12" width="24" height="24" '
                f'clip-path="url(#avc)" preserveAspectRatio="xMidYMid slice" />'
                f'<circle cx="0" cy="0" r="12" fill="none" stroke="{av_ring}" stroke-opacity="{av_ring_op}" stroke-width="1" />'
                f'</g>'
            )
        else:
            av_el = (
                f'<g transform="translate({av_cx:.1f},0)">'
                f'<circle cx="0" cy="0" r="12" fill="{init_bg}" fill-opacity="0.22" stroke="{av_ring}" stroke-width="1" />'
                f'<text x="0" y="4.0" text-anchor="middle" font-size="10.5" font-weight="500" fill="{text_col}">'
                f'{html.escape(p["login"][:1].upper())}</text>'
                f'</g>'
            )

        begin_s = -cursor_t
        cursor_t += dts[idx]

        # Pure rounded icon + @username text with zero bubble background or crossing track stroke
        nodes.append(
            f'<g>'
            f'<title>{html.escape(p["handle"])}</title>'
            f'{av_el}'
            f'<text class="f-name" x="{txt_x:.1f}" y="4.2" text-anchor="start">{html.escape(p["handle"])}</text>'
            f'<animateMotion dur="{total_dur:.2f}s" begin="{begin_s:.2f}s" repeatCount="indefinite" '
            f'rotate="auto" calcMode="linear" keyPoints="0;1;1" keyTimes="0;{frac:.5f};1" path="{wave_path}" />'
            f'</g>'
        )

    css = f"""
@font-face{{font-family:'FPop';font-style:normal;font-weight:500;src:url(data:font/woff2;base64,{poppins_b64}) format('woff2');}}
.f-name{{font-family:'FPop',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;font-weight:500;fill:{text_col}}}
"""

    handles_desc = ", ".join(f["handle"] for f in base_followers)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="Followers shoutout for {html.escape(user)} ({len(base_followers)} followers)">'
        f'<title>{html.escape(user)} followers shoutout ({len(base_followers)})</title>'
        f'<desc>GitHub followers of Muhammad Uzair (@{html.escape(user)}): {html.escape(handles_desc)}</desc>'
        f'<defs>'
        f'<style>{css}</style>'
        f'<linearGradient id="fp-fade" x1="0%" y1="0%" x2="100%" y2="0%">{fade_stops(0.11)}</linearGradient>'
        f'<mask id="fp-mask"><rect x="0" y="0" width="{width}" height="{height}" fill="url(#fp-fade)" /></mask>'
        f'{"".join(defs_clips)}'
        f'</defs>'
        f'<g mask="url(#fp-mask)">'
        f'<g>{"".join(nodes)}</g>'
        f'</g>'
        f'</svg>\n'
    )


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _blend_gamma22(c1, c2, amount):
    """Blend two RGB tuples using React Bits gamma-2.2 interpolation."""
    out = []
    for a, b in zip(c1, c2):
        va = (a / 255.0) ** 2.2
        vb = (b / 255.0) ** 2.2
        out.append(round(((va * (1.0 - amount) + vb * amount) ** (1.0 / 2.2)) * 255))
    return f"rgb({out[0]},{out[1]},{out[2]})"


def build_heading_svg(
    dark_mode=True,
    width=640,
    height=28,
    text="Special Thanks for My Followers",
    speed=2.0,
    angle=120.0,
    shine_width=40.0,
    softness=0.8,
):
    """Build React Bits <ShinyText /> SVG banner ('Special Thanks for My Followers')."""
    poppins600_b64 = base64.b64encode(POPPINS_600.read_bytes()).decode()

    # Exact React Bits dark palette (#b5b5b5 -> #ffffff); light mode preserves emerald contrast on #ffffff
    base_hex = "#b5b5b5" if dark_mode else "#57606a"
    shine_hex = "#ffffff" if dark_mode else "#1a7f37"
    base_rgb = _hex_to_rgb(base_hex)
    shine_rgb = _hex_to_rgb(shine_hex)

    # Exact measured box width for "Special Thanks for My Followers" @ 21px Poppins 600
    cx = width / 2.0
    cy = height / 2.0
    text_w = 296.0
    text_h = 23.0

    rad = math.radians(angle)
    dx = math.sin(rad)
    dy = -math.cos(rad)
    grad_span = abs(text_w * dx) + abs(text_h * dy)
    band_span = (shine_width / 100.0) * grad_span
    half_band = band_span / 2.0

    # Symmetric React Bits smoothstep falloff stops across [0%, 100%] of the shine band
    half_pct = shine_width / 2.0
    core_pct = half_pct * (1.0 - softness)
    fade_pct = half_pct - core_pct
    raw_stops = []
    falloff = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    for side in (-1.0, 1.0):
        for f in falloff:
            u = 0.5 + side * (core_pct + fade_pct * (1.0 - f)) / shine_width
            amt = f * f * (3.0 - 2.0 * f)
            raw_stops.append((max(0.0, min(1.0, u)), amt))
    raw_stops.sort(key=lambda s: s[0])
    stops_xml = "".join(
        f'<stop offset="{u * 100:.2f}%" stop-color="{_blend_gamma22(base_rgb, shine_rgb, amt)}" />'
        for u, amt in raw_stops
    )

    # Sweep direction="left": entry = 100 + extent, exit = -extent along gradient axis
    extent_frac = (shine_width / 2.0 + 2.0) / 100.0
    tx_entry = ((0.5 + extent_frac) * grad_span) / dx
    tx_exit = -tx_entry
    x1_0 = cx - half_band * dx
    x2_0 = cx + half_band * dx
    y1 = cy - half_band * dy
    y2 = cy + half_band * dy

    grad_id = "sh-dark" if dark_mode else "sh-light"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{html.escape(text)}">'
        f'<title>{html.escape(text)}</title>'
        f'<defs>'
        f'<style>'
        f'@font-face{{font-family:"FPop600";font-style:normal;font-weight:600;src:url(data:font/woff2;base64,{poppins600_b64}) format("woff2");}}'
        f'.sh-txt{{font-family:"FPop600",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;font-size:21px;font-weight:600;letter-spacing:-0.01em}}'
        f'</style>'
        f'<linearGradient id="{grad_id}" gradientUnits="userSpaceOnUse" spreadMethod="pad" '
        f'x1="{x1_0 + tx_entry:.2f}" y1="{y1:.2f}" x2="{x2_0 + tx_entry:.2f}" y2="{y2:.2f}">'
        f'{stops_xml}'
        f'<animate attributeName="x1" values="{x1_0 + tx_entry:.2f};{x1_0 + tx_exit:.2f}" '
        f'dur="{speed:.2f}s" repeatCount="indefinite" calcMode="spline" keyTimes="0;1" keySplines="0.37 0 0.63 1" />'
        f'<animate attributeName="x2" values="{x2_0 + tx_entry:.2f};{x2_0 + tx_exit:.2f}" '
        f'dur="{speed:.2f}s" repeatCount="indefinite" calcMode="spline" keyTimes="0;1" keySplines="0.37 0 0.63 1" />'
        f'</linearGradient>'
        f'</defs>'
        f'<text class="sh-txt" x="{cx:.1f}" y="20.5" text-anchor="middle" fill="url(#{grad_id})">'
        f'{html.escape(text)}'
        f'</text>'
        f'</svg>\n'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_ACTOR", "uzairshahidgithub"))
    ap.add_argument("--out-dir", default="assets")
    ap.add_argument("--max-followers", type=int, default=120)
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    raw = fetch_followers(args.user, token=token, max_followers=args.max_followers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(lambda f: fetch_avatar_webp(f["avatar_url"], login=f["login"], token=token), raw))

    items = [
        {"login": f["login"], "avatar": av}
        for f, (av, alive) in zip(raw, results)
        if alive
    ]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for dark, suffix in ((True, ""), (False, "-light")):
        h_svg = build_heading_svg(dark_mode=dark)
        hp = out_dir / f"followers-heading{suffix}.svg"
        hp.write_text(h_svg, encoding="utf-8")
        print(f"wrote {hp}: {len(h_svg) // 1024} KB")

        svg = build_svg(args.user, items, dark_mode=dark)
        p = out_dir / f"followers-path{suffix}.svg"
        p.write_text(svg, encoding="utf-8")
        print(f"wrote {p}: {len(items)} followers, {len(svg) // 1024} KB")


if __name__ == "__main__":
    main()
