#!/usr/bin/env python3
"""
Generate adaptive Dark & Light Total Contributions Counter SVGs
(`assets/contributions-count.svg` and `assets/contributions-count-light.svg`),
modeled after React Bits <CountUp mode="roll" easing="spring" duration={2.4} />.

Fetches lifetime GitHub contributions (GraphQL across all years when GITHUB_TOKEN
is available, or public GitHub contribution calendars otherwise) and renders a
4rem (64px) centered odometer counter below a 'Total Contributions' label with
per-column staggered spring roll + directional vertical motion blur.
"""
import argparse
import base64
import datetime as dt
import html
import json
import math
import os
import re
import urllib.request
from pathlib import Path

API = "https://api.github.com/graphql"
UA = "contributions-count/1.0"
FONT_DIR = Path(__file__).resolve().parent / "fonts"
POPPINS_500 = FONT_DIR / "poppins-latin-500-normal.woff2"


def _gql(query, variables, token):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        API,
        data=body,
        headers={"Authorization": f"bearer {token}", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_total_contributions(user, token=None):
    """Return exact lifetime contribution total for `user` across every calendar year."""
    if token:
        try:
            me = _gql(
                "query($l:String!){ user(login:$l){ createdAt } }",
                {"l": user},
                token,
            )["user"]
            created_yr = dt.datetime.fromisoformat(me["createdAt"].replace("Z", "+00:00")).year
            now = dt.datetime.now(dt.timezone.utc)
            q = """
            query($login:String!,$from:DateTime!,$to:DateTime!){
              user(login:$login){
                contributionsCollection(from:$from,to:$to){
                  contributionCalendar{ totalContributions }
                }
              }
            }"""
            total = 0
            for yr in range(created_yr, now.year + 1):
                start = dt.datetime(yr, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
                end = min(now, dt.datetime(yr, 12, 31, 23, 59, 59, tzinfo=dt.timezone.utc))
                res = _gql(q, {"login": user, "from": start.isoformat(), "to": end.isoformat()}, token)
                total += int(res["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"])
            return total
        except Exception as exc:
            import sys
            print(f"GraphQL contribution fetch failed ({exc}); falling back to public calendar.", file=sys.stderr)

    # Unauthenticated fallback: public REST created_at + yearly contribution fragments
    req = urllib.request.Request(f"https://api.github.com/users/{user}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        created_yr = int(json.load(r)["created_at"][:4])
    cur_yr = dt.datetime.now(dt.timezone.utc).year
    total = 0
    for yr in range(created_yr, cur_yr + 1):
        url = f"https://github.com/users/{user}/contributions?from={yr}-01-01&to={yr}-12-31"
        h_req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(h_req, timeout=15) as r:
            body = r.read().decode("utf-8", "ignore")
        m = re.search(r"([\d,]+)\s+contributions?\s+in\s+", body, re.I)
        if m:
            total += int(m.group(1).replace(",", ""))
    return total


def _make_spring(overshoot):
    """Exact damped spring easing curve from React Bits <CountUp />."""
    log = math.log(min(0.5, max(0.001, overshoot)))
    zeta = -log / math.sqrt(math.pi * math.pi + log * log)
    damped = math.pi / 0.52
    natural = damped / math.sqrt(1.0 - zeta * zeta)

    def _raw(t):
        return 1.0 - math.exp(-zeta * natural * t) * (
            math.cos(damped * t) + ((zeta * natural) / damped) * math.sin(damped * t)
        )

    residual = 1.0 - _raw(1.0)
    return lambda t: 1.0 if t >= 1.0 else (_raw(t) + residual * t * t * t)


def _roll_columns(total_count):
    """Reproduce React Bits buildRoll(0, total_count) per-column delta + comma layout."""
    s = f"{max(0, int(total_count)):,}"
    digits = [int(ch) for ch in s if ch.isdigit()]
    n = len(digits)
    slots = []
    digit_idx = 0
    for ch in s:
        if not ch.isdigit():
            slots.append({"type": "sep", "char": ch})
            continue
        place = n - 1 - digit_idx
        rank = place
        d_target = digits[digit_idx]
        turns = min(total_count // (10 ** (place + 1)), max(0, 3 - rank))
        delta = (d_target % 10) + 10 * turns
        slots.append({"type": "col", "index": digit_idx, "target": d_target, "delta": delta})
        digit_idx += 1
    return slots


def build_count_svg(total_count, dark_mode=True, width=493, height=112, duration=2.4):
    """Build pure SVG React Bits <CountUp mode='roll' easing='spring' /> Total Contributions counter."""
    poppins_b64 = base64.b64encode(POPPINS_500.read_bytes()).decode()
    slots = _roll_columns(total_count)
    n_cols = sum(1 for sl in slots if sl["type"] == "col")

    cx = width / 2.0
    label_y = 20.0
    font_size = 64.0  # 4rem = 64px, fontWeight = 500
    cell_h = 74.0
    win_top = 29.0
    win_h = 76.0
    base_y = win_top + 59.0  # baseline aligning 64px digit optical center neatly inside 29..105

    col_w = 42.0
    sep_w = 18.0
    total_w = sum(col_w if sl["type"] == "col" else sep_w for sl in slots)
    width = max(width, math.ceil(total_w + 64))
    cx = width / 2.0

    # Periodic showcase cycle: 2.4s spring roll + 6.4s calm crisp settled hold + 0.3s fade-reset = 9.1s
    stagger = min(0.07, (duration * 0.4) / max(1, n_cols - 1)) if n_cols > 1 else 0.0
    span = max(0.01, duration - stagger * max(0, n_cols - 1))
    cycle_s = 9.1
    hold_end = cycle_s - 0.35

    if dark_mode:
        label_col = "#8b949e"
        num_top, num_bot = "#ffffff", "#d2fedb"
    else:
        label_col = "#57606a"
        num_top, num_bot = "#1f2328", "#116329"

    # Build vertical feather fade mask over digit window so digits glide smoothly in & out
    fade_stops = "".join(
        f'<stop offset="{pos}%" stop-color="#ffffff" stop-opacity="{op:.3f}" />'
        for pos, op in ((0, 0.0), (14, 1.0), (86, 1.0), (100, 0.0))
    )

    filters_xml = []
    slots_xml = []
    cur_x = cx - total_w / 2.0

    for sl in slots:
        if sl["type"] == "sep":
            sep_cx = cur_x + sep_w / 2.0
            cur_x += sep_w
            slots_xml.append(
                f'<text class="cu-num" x="{sep_cx:.1f}" y="{base_y:.1f}" text-anchor="middle" fill="url(#cu-fill)">'
                f'{html.escape(sl["char"])}</text>'
            )
            continue

        col_idx = sl["index"]
        col_cx = cur_x + col_w / 2.0
        cur_x += col_w
        delta = max(0, sl["delta"])

        # Digit strip runs vertically downward: row k at offset -k? Wait: moving upward cleanly rolls 0->1->...->target!
        # Placing row k at y = base_y + k * cell_h and translating strip UP by -pos * cell_h scrolls 0 -> delta upward.
        max_row = max(delta + 2, 2)
        strip_chars = []
        for k in range(max_row + 1):
            d = k % 10
            strip_chars.append(
                f'<text class="cu-num" x="{col_cx:.1f}" y="{base_y + k * cell_h:.1f}" '
                f'text-anchor="middle" fill="url(#cu-fill)">{d}</text>'
            )

        # Sample exact React Bits spring curve during [delay_i, delay_i + span] inside cycle_s
        overshoot = min(0.12, max(0.01, 0.35 / max(1, delta)))
        spring = _make_spring(overshoot)
        t0 = col_idx * stagger
        steps = 28
        key_times = []
        trans_vals = []
        blur_vals = []
        op_vals = []

        if t0 > 0.001:
            key_times.append("0.0000")
            trans_vals.append("0 0.0")
            blur_vals.append("0 0.0")
            op_vals.append("1.0")

        for s_i in range(steps + 1):
            u = s_i / steps
            t_sec = t0 + u * span
            kt = t_sec / cycle_s
            pos = delta * spring(u)
            dy = -pos * cell_h

            # Instantaneous velocity -> directional vertical blur matching React Bits countup formula
            u0 = max(0.0, u - 0.005)
            u1 = min(1.0, u + 0.005)
            spd = (delta * abs(spring(u1) - spring(u0))) / ((u1 - u0) * span) if (0.0 < u < 1.0 and u1 > u0) else 0.0
            sigma_y = min(cell_h * 0.055, (spd * cell_h) / 480.0) if 0.0 < u < 1.0 else 0.0

            key_times.append(f"{kt:.4f}")
            trans_vals.append(f"0 {dy:.2f}")
            blur_vals.append(f"0 {sigma_y:.2f}")
            op_vals.append("1.0")

        final_dy = -delta * cell_h
        key_times.extend([f"{hold_end / cycle_s:.4f}", f"{(hold_end + 0.16) / cycle_s:.4f}", f"{(hold_end + 0.18) / cycle_s:.4f}", "1.0000"])
        trans_vals.extend([f"0 {final_dy:.2f}", f"0 {final_dy:.2f}", "0 0.0", "0 0.0"])
        blur_vals.extend(["0 0.0", "0 0.0", "0 0.0", "0 0.0"])
        op_vals.extend(["1.0", "0.0", "0.0", "1.0"])

        kt_str = ";".join(key_times)
        # Start cycle 1.5s before end of previous settled hold so t=0 displays settled count immediately, then rolls!
        begin_s = -(cycle_s - 1.5)

        filters_xml.append(
            f'<filter id="mb-{col_idx}" filterUnits="userSpaceOnUse" x="{col_cx - 28:.1f}" y="{win_top - 4:.1f}" '
            f'width="56" height="{win_h + 8:.1f}">'
            f'<feGaussianBlur stdDeviation="0 0">'
            f'<animate attributeName="stdDeviation" values="{";".join(blur_vals)}" keyTimes="{kt_str}" '
            f'dur="{cycle_s:.2f}s" begin="{begin_s:.2f}s" repeatCount="indefinite" />'
            f'</feGaussianBlur></filter>'
        )

        # Static reduced-motion fallback renders exact final digit cleanly when animations disabled
        slots_xml.append(
            f'<g filter="url(#mb-{col_idx})">'
            f'<g class="cu-strip">'
            f'<animateTransform attributeName="transform" type="translate" '
            f'values="{";".join(trans_vals)}" keyTimes="{kt_str}" '
            f'dur="{cycle_s:.2f}s" begin="{begin_s:.2f}s" repeatCount="indefinite" />'
            f'<animate attributeName="opacity" values="{";".join(op_vals)}" keyTimes="{kt_str}" '
            f'dur="{cycle_s:.2f}s" begin="{begin_s:.2f}s" repeatCount="indefinite" />'
            f'{"".join(strip_chars)}'
            f'</g></g>'
        )

    css = f"""
@font-face{{font-family:'FPop500';font-style:normal;font-weight:500;src:url(data:font/woff2;base64,{poppins_b64}) format('woff2');}}
.cu-lbl{{font-family:'FPop500',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13.5px;font-weight:500;letter-spacing:0.4px;fill:{label_col}}}
.cu-num{{font-family:'FPop500',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:{font_size:.0f}px;font-weight:500;font-variant-numeric:tabular-nums}}
"""

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="Total Contributions: {total_count:,}">'
        f'<title>Total Contributions: {total_count:,}</title>'
        f'<desc>Lifetime GitHub contributions count for Muhammad Uzair (@uzairshahidgithub): {total_count:,}</desc>'
        f'<defs>'
        f'<style>{css}</style>'
        f'<linearGradient id="cu-fill" x1="0%" y1="0%" x2="0%" y2="100%">'
        f'<stop offset="0%" stop-color="{num_top}" />'
        f'<stop offset="100%" stop-color="{num_bot}" />'
        f'</linearGradient>'
        f'<linearGradient id="cu-win-grad" x1="0%" y1="0%" x2="0%" y2="100%">{fade_stops}</linearGradient>'
        f'<mask id="cu-win-mask" maskUnits="userSpaceOnUse" x="0" y="{win_top:.1f}" width="{width}" height="{win_h:.1f}">'
        f'<rect x="0" y="{win_top:.1f}" width="{width}" height="{win_h:.1f}" fill="url(#cu-win-grad)" />'
        f'</mask>'
        f'<clipPath id="cu-win-clip"><rect x="0" y="{win_top:.1f}" width="{width}" height="{win_h:.1f}" /></clipPath>'
        f'{"".join(filters_xml)}'
        f'</defs>'
        f'<text class="cu-lbl" x="{cx:.1f}" y="{label_y:.1f}" text-anchor="middle">Total Contributions</text>'
        f'<g clip-path="url(#cu-win-clip)" mask="url(#cu-win-mask)">'
        f'{"".join(slots_xml)}'
        f'</g>'
        f'</svg>\n'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_ACTOR", "uzairshahidgithub"))
    ap.add_argument("--out-dir", default="assets")
    ap.add_argument("--count", type=int, default=None, help="Explicit count override (skips network fetch)")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    total = args.count if args.count is not None else fetch_total_contributions(args.user, token=token)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for dark, suffix in ((True, ""), (False, "-light")):
        svg = build_count_svg(total, dark_mode=dark)
        p = out_dir / f"contributions-count{suffix}.svg"
        p.write_text(svg, encoding="utf-8")
        print(f"wrote {p}: total={total:,}, {len(svg) // 1024} KB")


if __name__ == "__main__":
    main()
