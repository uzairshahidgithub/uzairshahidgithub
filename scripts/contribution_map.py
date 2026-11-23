#!/usr/bin/env python3
"""
Linked contribution map: a concise, liquid-glass SVG showing the organizations
and people you contribute to.

  * center            : your avatar
  * rounded squares   : organizations you contribute to (logo + pill)
  * circles           : other people whose projects you contribute to
  * wires             : translucent liquid-glass filaments with a calm sheen

Standard library only. The SVG is self-contained: avatars and the Poppins font
are embedded as base64, because GitHub does not load external resources inside
an SVG shown in a README.

Usage:
  GITHUB_TOKEN=... python contribution_map.py --user uzairshahidgithub
  python contribution_map.py --demo            # offline preview with fake data
"""
import argparse
import base64
import datetime as dt
import html
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

API = "https://api.github.com/graphql"
UA = "contribution-map/3.0"
FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT_FILES = {
    400: "poppins-latin-400-normal.woff2",
    500: "poppins-latin-500-normal.woff2",
    600: "poppins-latin-600-normal.woff2",
}

# Measured glyph widths for bundled Poppins 500 @ 10px and 600 @ 9.5px
_W500 = {
    "0": 6.41, "1": 3.50, "2": 5.77, "3": 5.94, "4": 6.47,
    "5": 6.39, "6": 6.42, "7": 5.60, "8": 6.38, "9": 6.35,
    "A": 6.97, "B": 6.30, "C": 7.73, "D": 7.09, "E": 5.24,
    "F": 5.15, "G": 7.73, "H": 7.05, "I": 2.64, "J": 5.64,
    "K": 6.33, "L": 4.44, "M": 8.82, "N": 7.21, "O": 7.84,
    "P": 5.95, "Q": 7.87, "R": 6.32, "S": 6.04, "T": 5.64,
    "U": 6.90, "V": 6.94, "W": 9.99, "X": 6.60, "Y": 6.05,
    "Z": 5.58, "a": 6.78, "b": 6.78, "c": 6.00, "d": 6.78,
    "e": 6.17, "f": 3.32, "g": 6.78, "h": 6.49, "i": 2.64,
    "j": 2.64, "k": 5.54, "l": 2.64, "m": 10.39, "n": 6.49,
    "o": 6.38, "p": 6.78, "q": 6.78, "r": 3.84, "s": 5.34,
    "t": 3.72, "u": 6.49, "v": 5.76, "w": 8.25, "x": 4.99,
    "y": 5.82, "z": 4.71, " ": 2.60, ".": 2.41, ",": 2.25,
    "-": 5.85, "_": 7.98, "&": 7.61, "+": 7.14, "/": 5.14,
    "(": 4.92, ")": 4.92, "…": 6.38,
}
_W600 = {
    "0": 6.14, "1": 3.44, "2": 5.45, "3": 5.69, "4": 6.28,
    "5": 6.12, "6": 6.08, "7": 5.21, "8": 6.11, "9": 5.95,
    ",": 2.41,
}


# --------------------------------------------------------------------------- #
# GitHub data
# --------------------------------------------------------------------------- #
def gql(query, variables, token):
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


def _sel():
    return (
        "repository{ owner{ __typename login avatarUrl(size:120) "
        "... on Organization{ name } ... on User{ name } } } contributions{ totalCount }"
    )


def collect(login, token):
    """Return (my_avatar_url, {owner_login: {name, avatar_url, count, kind}})."""
    me = gql(
        "query($l:String!){ user(login:$l){ createdAt avatarUrl(size:200) } }",
        {"l": login},
        token,
    )["user"]
    start = dt.datetime.fromisoformat(me["createdAt"].replace("Z", "+00:00"))
    now = dt.datetime.now(dt.timezone.utc)

    query = f"""
    query($login:String!,$from:DateTime!,$to:DateTime!){{
      user(login:$login){{
        contributionsCollection(from:$from,to:$to){{
          commitContributionsByRepository(maxRepositories:100){{ {_sel()} }}
          pullRequestContributionsByRepository(maxRepositories:100){{ {_sel()} }}
          issueContributionsByRepository(maxRepositories:100){{ {_sel()} }}
          pullRequestReviewContributionsByRepository(maxRepositories:100){{ {_sel()} }}
        }}
      }}
    }}"""

    owners = {}
    cursor = start
    while cursor < now:
        end = min(cursor + dt.timedelta(days=365), now)
        coll = gql(
            query,
            {"login": login, "from": cursor.isoformat(), "to": end.isoformat()},
            token,
        )["user"]["contributionsCollection"]
        for bucket in coll.values():
            for item in bucket or []:
                repo = (item or {}).get("repository") or {}
                owner = repo.get("owner")
                if not owner or not owner.get("login"):
                    continue
                key = owner["login"]
                if key.lower() == login.lower():
                    continue
                entry = owners.setdefault(
                    key,
                    {
                        "name": owner.get("name") or key,
                        "avatar_url": owner.get("avatarUrl") or "",
                        "kind": "org" if owner.get("__typename") == "Organization" else "user",
                        "count": 0,
                    },
                )
                entry["count"] += (item.get("contributions") or {}).get("totalCount", 0)
        cursor = end
    return me["avatarUrl"], owners


def fetch_data_uri(url):
    if not url:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            ctype = resp.headers.get("Content-Type", "image/png").split(";")[0]
            return f"data:{ctype};base64,{base64.b64encode(resp.read()).decode()}"
    except Exception as exc:
        print(f"avatar fetch failed for {url}: {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Typography & Pill Layout
# --------------------------------------------------------------------------- #
def esc(s):
    return html.escape(str(s), quote=True)


def short(s, n=26):
    return s if len(s) <= n else s[: n - 1] + "…"


def measure_text(s, table, default_w=6.2):
    return sum(table.get(ch, default_w) for ch in s)


def pill_metrics(name, count):
    """Compute centered capsule dimensions for white name + white-bubble black count."""
    label = short(name)
    count_str = f"{count:,}"
    name_w = measure_text(label, _W500, 6.2)
    count_w = measure_text(count_str, _W600, 5.8)

    pad_l = 9.0
    gap = 6.0
    pad_r = 3.0  # concentric with 11px pill radius and 8px badge radius
    badge_h = 16.0
    badge_w = max(18.0, count_w + 10.0)
    pill_h = 22.0
    pill_w = pad_l + name_w + gap + badge_w + pad_r
    return {
        "label": label,
        "count_str": count_str,
        "name_w": name_w,
        "pill_w": pill_w,
        "pill_h": pill_h,
        "badge_w": badge_w,
        "badge_h": badge_h,
        "pad_l": pad_l,
        "gap": gap,
    }


def font_css():
    out = []
    for weight, fname in FONT_FILES.items():
        path = FONT_DIR / fname
        if not path.exists():
            print(f"font missing: {path} (falling back to system fonts)", file=sys.stderr)
            continue
        b64 = base64.b64encode(path.read_bytes()).decode()
        out.append(
            "@font-face{font-family:'Poppins';font-style:normal;font-weight:%d;"
            "src:url(data:font/woff2;base64,%s) format('woff2');}" % (weight, b64)
        )
    return "".join(out)


CSS = """
text{font-family:'Poppins','Segoe UI',Helvetica,Arial,sans-serif}
.nm{font-size:10px;font-weight:500;fill:#ffffff;letter-spacing:.1px}
.ct{font-size:9.5px;font-weight:600;fill:#000000;letter-spacing:.1px}
.pill-bg{fill:#101521;fill-opacity:.88;stroke:url(#glass-rim);stroke-width:1}
.ct-bubble{fill:#ffffff}
.plate-bg{fill:#111622;fill-opacity:.84;stroke:url(#glass-rim);stroke-width:1.35}
.center-bg{fill:#111622;fill-opacity:.90;stroke:url(#glass-rim);stroke-width:1.6}
.wire-edge{fill:none;stroke-linecap:round;stroke:#7890b2;stroke-opacity:.36}
.wire-body{fill:none;stroke-linecap:round}
.wire-spec{fill:none;stroke-linecap:round}
.wire-flow{fill:none;stroke:#ffffff;stroke-width:1.8;stroke-linecap:round;
           stroke-dasharray:8 192;stroke-dashoffset:8;stroke-opacity:.82;
           animation:flow linear infinite both}
.pulse{fill:none;stroke:rgba(180,202,235,.36);stroke-width:1.15;stroke-opacity:0;
       transform-box:fill-box;transform-origin:50% 50%;animation:pulse 5.2s ease-out infinite both}
.init{font-weight:600;fill:#ffffff}
@keyframes flow{from{stroke-dashoffset:8}to{stroke-dashoffset:-192}}
@keyframes pulse{0%{stroke-opacity:.36;transform:scale(1)}100%{stroke-opacity:0;transform:scale(1.62)}}
@media (prefers-color-scheme:light){
  .wire-edge{stroke:#64748b;stroke-opacity:.34}
  .pulse{stroke:rgba(71,85,105,.32)}
  .plate-bg{fill:#182030;fill-opacity:.88;stroke:rgba(255,255,255,.52)}
  .center-bg{fill:#182030;fill-opacity:.92;stroke:rgba(255,255,255,.58)}
  .pill-bg{fill:#141b29;fill-opacity:.92;stroke:rgba(255,255,255,.28)}
}
@media (prefers-reduced-motion:reduce){
  .wire-flow,.pulse{animation:none!important}
}
"""


def plate(shape, x, y, r, clip_id, data_uri, label):
    """Frosted liquid-glass plate with specular rim and clipped avatar."""
    pad = 3.5
    if shape == "org":
        outer = (
            f'<rect class="plate-bg" x="{x - r - pad:.1f}" y="{y - r - pad:.1f}" '
            f'width="{2 * (r + pad):.1f}" height="{2 * (r + pad):.1f}" '
            f'rx="{(r + pad) * 0.42:.1f}" filter="url(#glass-shadow)"/>'
        )
        clip = (
            f'<clipPath id="{clip_id}"><rect x="{x - r:.1f}" y="{y - r:.1f}" '
            f'width="{2 * r:.1f}" height="{2 * r:.1f}" rx="{r * 0.36:.1f}"/></clipPath>'
        )
    else:
        outer = (
            f'<circle class="plate-bg" cx="{x:.1f}" cy="{y:.1f}" r="{r + pad:.1f}" '
            f'filter="url(#glass-shadow)"/>'
        )
        clip = f'<clipPath id="{clip_id}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"/></clipPath>'

    if data_uri:
        inner = (
            f'<image href="{data_uri}" x="{x - r:.1f}" y="{y - r:.1f}" '
            f'width="{2 * r:.1f}" height="{2 * r:.1f}" clip-path="url(#{clip_id})" '
            f'preserveAspectRatio="xMidYMid slice"/>'
        )
    else:
        inner = (
            f'<text class="init" x="{x:.1f}" y="{y + r * 0.34:.1f}" text-anchor="middle" '
            f'font-size="{r * 0.95:.0f}">{esc(label[:1].upper())}</text>'
        )
    return clip, outer + inner


def node_radius(kind, ratio):
    return (19 + 7 * math.sqrt(ratio)) if kind == "org" else (16 + 5.5 * math.sqrt(ratio))


def wire_points(cx, cy, cr, x, y, r):
    """Smooth Bezier wire curving cleanly clear of the node's below-avatar pill."""
    dx, dy = x - cx, y - cy
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist
    sx, sy = cx + ux * (cr + 5), cy + uy * (cr + 5)
    # Enter upper-side nodes slightly higher on the plate rim so the wire arches above wide pills
    if dy < -10 and abs(dx) > 10:
        ex = x - ux * (r + 5)
        ey = y - uy * (r + 5) - min(10.0, 0.36 * r)
    else:
        ex, ey = x - ux * (r + 5), y - uy * (r + 5)
    mx, my = (sx + ex) / 2, (sy + ey) / 2
    nx, ny = -uy, ux
    if dy < -10 and ny > 0:
        nx, ny = -nx, -ny
    curve = (0.20 if dy < -10 else 0.11) * dist
    return (sx, sy, mx + nx * curve, my + ny * curve, ex, ey)


def node_pill_box(node):
    """Axis-aligned bounding box (x0, y0, x1, y1) of the below-profile pill."""
    pm = node["pm"]
    pw, ph = pm["pill_w"], pm["pill_h"]
    px = node["x"] - pw / 2
    py = node["y"] + node["r"] + 3.5 + 7.0
    return (px, py, px + pw, py + ph)


def rect_dist(pt_x, pt_y, box):
    x0, y0, x1, y1 = box
    dx = max(x0 - pt_x, 0.0, pt_x - x1)
    dy = max(y0 - pt_y, 0.0, pt_y - y1)
    return math.hypot(dx, dy)


def clearance(cx, cy, cr, cand, all_nodes):
    """Minimum gap from candidate wire to other plates and all below-profile pills."""
    sx, sy, qx, qy, ex, ey = wire_points(cx, cy, cr, cand["x"], cand["y"], cand["r"])
    best = 1e9
    own_box = node_pill_box(cand)
    for k in range(1, 28):
        t = k / 28
        bx = (1 - t) ** 2 * sx + 2 * (1 - t) * t * qx + t * t * ex
        by = (1 - t) ** 2 * sy + 2 * (1 - t) * t * qy + t * t * ey
        best = min(best, rect_dist(bx, by, own_box) - 3.0)
        for o in all_nodes:
            if o is cand:
                continue
            best = min(best, math.hypot(bx - o["x"], by - o["y"]) - (o["r"] + 9))
            best = min(best, rect_dist(bx, by, node_pill_box(o)) - 4.0)
    return best


def layout_clear(nodes, cx, cy, cr):
    """Return True if all pills clear the center avatar, each other, and all node plates."""
    for i, a in enumerate(nodes):
        abox = node_pill_box(a)
        if rect_dist(cx, cy, abox) < (cr + 16.0):
            return False
        for j, b in enumerate(nodes):
            if i == j:
                continue
            if rect_dist(b["x"], b["y"], abox) < (b["r"] + 12.0):
                return False
            if j > i:
                bbox = node_pill_box(b)
                ox = min(abox[2], bbox[2]) - max(abox[0], bbox[0]) + 10.0
                oy = min(abox[3], bbox[3]) - max(abox[1], bbox[1]) + 6.0
                if ox > 0 and oy > 0:
                    return False
    return True


def pair_overlap_penalty(nodes, cx, cy, cr):
    """Penalize pill-to-center, pill-to-plate, and pill-to-pill overlaps."""
    penalty = 0.0
    for i, a in enumerate(nodes):
        abox = node_pill_box(a)
        cd = rect_dist(cx, cy, abox)
        if cd < (cr + 16.0):
            penalty += (cr + 16.0) - cd
        for j in range(i + 1, len(nodes)):
            b = nodes[j]
            bbox = node_pill_box(b)
            ox = min(abox[2], bbox[2]) - max(abox[0], bbox[0]) + 10.0
            oy = min(abox[3], bbox[3]) - max(abox[1], bbox[1]) + 6.0
            if ox > 0 and oy > 0:
                penalty += min(ox, oy)
    return penalty


def plan(orgs, people, radius=None):
    """Compute concise circular orbital radii for the contribution map."""
    items = [("org", o) for o in orgs] + [("user", p) for p in people]
    total = len(items)
    if total == 0:
        return []

    if total <= 6 or not (orgs and people):
        if radius is not None:
            r_main = float(radius)
        else:
            r_main = {1: 108.0, 2: 122.0, 3: 138.0, 4: 146.0, 5: 162.0, 6: 178.0}.get(
                total, min(240.0, 150.0 + 11.0 * total)
            )
        return [(items, r_main)]

    if radius is not None:
        r_org = max(130.0, float(radius) * 0.64)
        r_user = max(r_org + 108.0, float(radius))
    else:
        r_org = min(210.0, 140.0 + 10.0 * len(orgs))
        r_user = min(320.0, max(r_org + 110.0, 230.0 + 8.0 * len(people)))
    return [([("org", o) for o in orgs], r_org), ([("user", p) for p in people], r_user)]


def _start_angle(n):
    """Avoid placing nodes straight up (-pi/2) when n is small so wires stay clear of below-pills."""
    if n == 1:
        return math.pi / 2
    if n == 2:
        return 0.0
    if n == 3:
        return -5 * math.pi / 6
    if n == 4:
        return -3 * math.pi / 4
    return -math.pi / 2 + math.pi / n


def _build_ring(grp, ring_r, offset, cx, cy, peak):
    n = len(grp)
    out = []
    for i, (kind, item) in enumerate(grp):
        ang = offset + 2 * math.pi * i / n
        ratio = item["count"] / peak
        r = node_radius(kind, ratio)
        out.append(
            {
                "item": item,
                "kind": kind,
                "ring_r": ring_r,
                "ang": ang,
                "x": cx + ring_r * math.cos(ang),
                "y": cy + ring_r * math.sin(ang),
                "r": r,
                "ratio": ratio,
                "pm": pill_metrics(item["name"], item["count"]),
            }
        )
    return out


def place(groups, cx, cy, cr, fixed_radius=False):
    """Place nodes on concise circular radii, expanding gently if pills need more clearance."""
    all_items = [item for grp, _ in groups for _, item in grp]
    peak = max((i["count"] for i in all_items), default=1) or 1

    # Single-ring concise mode: if the widest pill sits better on the bottom slot for n=3,
    # rotate items so the widest pill sits at +90 deg unless doing so breaks order, OR expand R.
    if len(groups) == 1 and not fixed_radius:
        grp, base_r = groups[0]
        n = len(grp)
        # Try base radius and grow slightly only if any pill touches center or sibling pill
        for step_r in range(0, 120, 8):
            ring_r = base_r + step_r
            best_nodes = None
            best_score = -1e9
            samples = 1 if n <= 4 else 144
            base = _start_angle(n)
            for k in range(samples):
                off = base + (2 * math.pi / n) * k / samples
                cand = _build_ring(grp, ring_r, off, cx, cy, peak)
                if not layout_clear(cand, cx, cy, cr):
                    continue
                wire_gap = min(clearance(cx, cy, cr, c, cand) for c in cand)
                if wire_gap > best_score:
                    best_score = wire_gap
                    best_nodes = cand
            if best_nodes is not None and best_score >= 6.0:
                return best_nodes

    placed = []
    for gi, (grp, base_r) in enumerate(groups):
        n = len(grp)
        base = _start_angle(n)
        step = 2 * math.pi / n
        chosen = None

        max_grow = 0 if fixed_radius else 128
        for grow in range(0, max_grow + 1, 10):
            ring_r = base_r + grow
            best_cand, best_score = None, -1e9
            samples = 1 if (gi == 0 and n <= 4 and fixed_radius) else 144
            for k in range(samples):
                off = base + step * k / samples
                cand = _build_ring(grp, ring_r, off, cx, cy, peak)
                combined = placed + cand
                wire_gap = min(clearance(cx, cy, cr, c, combined) for c in cand)
                pen = pair_overlap_penalty(combined, cx, cy, cr)
                score = wire_gap - 5.0 * pen
                if score > best_score:
                    best_score = score
                    best_cand = cand
            if best_cand is not None and (
                fixed_radius or (layout_clear(placed + best_cand, cx, cy, cr) and best_score >= 6.0)
            ):
                chosen = best_cand
                break
            chosen = best_cand
        placed.extend(chosen or [])
    return placed


def compute_bounds(placed, cx, cy, cr):
    """Tight bounding box around center plate, all node plates, and all below-profile pills."""
    pad = 22.0
    xs = [cx - (cr + 8), cx + (cr + 8)]
    ys = [cy - (cr + 8), cy + (cr + 8)]
    for node in placed:
        r = node["r"] + 5
        xs.extend([node["x"] - r, node["x"] + r])
        ys.extend([node["y"] - r, node["y"] + r])
        px0, py0, px1, py1 = node_pill_box(node)
        xs.extend([px0, px1])
        ys.extend([py0, py1])
    min_x, max_x = min(xs) - pad, max(xs) + pad
    min_y, max_y = min(ys) - pad, max(ys) + pad
    return min_x, min_y, max_x - min_x, max_y - min_y


def render(user, user_avatar, orgs, people, radius=None):
    groups = plan(orgs, people, radius=radius)
    cx, cy = 400.0, 400.0
    cr = 32.0
    placed = place(groups, cx, cy, cr, fixed_radius=(radius is not None))

    min_x, min_y, raw_w, raw_h = compute_bounds(placed, cx, cy, cr)
    W = math.ceil(raw_w)
    H = math.ceil(raw_h)
    shift_x = -min_x + (W - raw_w) / 2
    shift_y = -min_y + (H - raw_h) / 2
    cx += shift_x
    cy += shift_y
    for node in placed:
        node["x"] += shift_x
        node["y"] += shift_y

    wires, flows, nodes, defs = [], [], [], []

    defs.append(f'<style>{font_css()}{CSS}</style>')
    defs.append(
        '<linearGradient id="glass-rim" x1="0%" y1="0%" x2="100%" y2="100%">'
        '<stop offset="0%" stop-color="#ffffff" stop-opacity="0.56"/>'
        '<stop offset="50%" stop-color="#dbeafe" stop-opacity="0.20"/>'
        '<stop offset="100%" stop-color="#ffffff" stop-opacity="0.36"/>'
        '</linearGradient>'
    )
    defs.append(
        '<filter id="glass-shadow" x="-25%" y="-25%" width="150%" height="150%">'
        '<feDropShadow dx="0" dy="3" stdDeviation="3.5" flood-color="#000000" flood-opacity="0.28"/>'
        '</filter>'
    )
    defs.append(
        '<filter id="sheen-blur" x="-15%" y="-15%" width="130%" height="130%">'
        '<feGaussianBlur in="SourceGraphic" stdDeviation="0.8"/>'
        '</filter>'
    )

    for idx, node in enumerate(placed):
        item, kind = node["item"], node["kind"]
        x, y, r, ratio = node["x"], node["y"], node["r"], node["ratio"]
        pm = node["pm"]

        sx, sy, qx, qy, ex, ey = wire_points(cx, cy, cr, x, y, r)
        d = f"M{sx:.1f} {sy:.1f}Q{qx:.1f} {qy:.1f} {ex:.1f} {ey:.1f}"

        # Per-wire userSpace gradients prevent collapse on horizontal/vertical segments
        w_grad_id = f"wg{idx}"
        s_grad_id = f"sg{idx}"
        op_hi = 0.42 + 0.16 * ratio
        op_lo = 0.22 + 0.12 * ratio
        defs.append(
            f'<linearGradient id="{w_grad_id}" gradientUnits="userSpaceOnUse" '
            f'x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}">'
            f'<stop offset="0%" stop-color="#dbeafe" stop-opacity="{op_hi:.2f}"/>'
            f'<stop offset="55%" stop-color="#e2e8f0" stop-opacity="{op_hi + 0.08:.2f}"/>'
            f'<stop offset="100%" stop-color="#94a3b8" stop-opacity="{op_lo:.2f}"/>'
            f'</linearGradient>'
        )
        defs.append(
            f'<linearGradient id="{s_grad_id}" gradientUnits="userSpaceOnUse" '
            f'x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}">'
            f'<stop offset="0%" stop-color="#ffffff" stop-opacity="0.78"/>'
            f'<stop offset="60%" stop-color="#ffffff" stop-opacity="0.46"/>'
            f'<stop offset="100%" stop-color="#ffffff" stop-opacity="0.22"/>'
            f'</linearGradient>'
        )

        body_w = 3.0 + 0.9 * ratio
        edge_w = body_w + 1.8
        dur = 4.6 + (idx * 0.41) % 2.0
        delay = -((idx * 1.13) % dur)

        wires.append(
            f'<path class="wire-edge" d="{d}" stroke-width="{edge_w:.2f}"/>'
            f'<path class="wire-body" d="{d}" stroke="url(#{w_grad_id})" stroke-width="{body_w:.2f}"/>'
            f'<path class="wire-spec" d="{d}" stroke="url(#{s_grad_id})" stroke-width="1.05"/>'
        )
        flows.append(
            f'<path class="wire-flow" pathLength="100" d="{d}" '
            f'style="animation-duration:{dur:.2f}s;animation-delay:{delay:.2f}s"/>'
        )

        clip, body = plate(kind, x, y, r, f"c{idx}", item.get("avatar"), item["name"])
        defs.append(clip)

        # Bubble always below orgs + people's profile:
        # dark frosted pill (white text) + nested white bubble (black count)
        pw, ph = pm["pill_w"], pm["pill_h"]
        bw, bh = pm["badge_w"], pm["badge_h"]
        px = x - pw / 2
        py = y + r + 3.5 + 7.0
        name_x = px + pm["pad_l"]
        text_y = py + ph / 2 + 3.4
        badge_x = px + pm["pad_l"] + pm["name_w"] + pm["gap"]
        badge_y = py + (ph - bh) / 2
        count_cx = badge_x + bw / 2
        count_cy = py + ph / 2 + 3.3

        kind_label = "Organization" if kind == "org" else "Person"
        nodes.append(
            f'<g class="node">'
            f'<title>{esc(item["name"])} ({kind_label}): {item["count"]:,} contributions</title>'
            f'{body}'
            f'<rect class="pill-bg" x="{px:.1f}" y="{py:.1f}" width="{pw:.1f}" height="{ph:.1f}" '
            f'rx="{ph / 2:.1f}" filter="url(#glass-shadow)"/>'
            f'<text class="nm" x="{name_x:.1f}" y="{text_y:.1f}" text-anchor="start">{esc(pm["label"])}</text>'
            f'<rect class="ct-bubble" x="{badge_x:.1f}" y="{badge_y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'rx="{bh / 2:.1f}"/>'
            f'<text class="ct" x="{count_cx:.1f}" y="{count_cy:.1f}" text-anchor="middle">{esc(pm["count_str"])}</text>'
            f'</g>'
        )

    # Center avatar plate (clean glass medallion, no background rings)
    defs.append(f'<clipPath id="cc"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="{cr:.1f}"/></clipPath>')
    if user_avatar:
        c_img = (
            f'<image href="{user_avatar}" x="{cx - cr:.1f}" y="{cy - cr:.1f}" '
            f'width="{2 * cr:.1f}" height="{2 * cr:.1f}" clip-path="url(#cc)" '
            f'preserveAspectRatio="xMidYMid slice"/>'
        )
    else:
        c_img = (
            f'<text class="init" x="{cx:.1f}" y="{cy + 13:.1f}" text-anchor="middle" font-size="34">'
            f'{esc(user[:1].upper())}</text>'
        )
    center = (
        f'<circle class="pulse" cx="{cx:.1f}" cy="{cy:.1f}" r="{cr + 5:.1f}"/>'
        f'<g class="center">'
        f'<circle class="center-bg" cx="{cx:.1f}" cy="{cy:.1f}" r="{cr + 4:.1f}" filter="url(#glass-shadow)"/>'
        f'{c_img}</g>'
    )

    total = sum(n["item"]["count"] for n in placed)
    orgs_list = ", ".join(esc(n["item"]["name"]) for n in placed if n["kind"] == "org")
    people_list = ", ".join(esc(n["item"]["name"]) for n in placed if n["kind"] == "user")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'role="img" aria-label="Contribution map for {esc(user)}">'
        f'<title>{esc(user)}: {total:,} contributions across {len(placed)} organizations and people</title>'
        f'<desc>GitHub open source contributions by {esc(user)} to organizations ({orgs_list}) and collaborators ({people_list}).</desc>'
        f'<defs>{"".join(defs)}</defs>'
        f'<g>{"".join(wires)}</g>'
        f'<g filter="url(#sheen-blur)">{"".join(flows)}</g>'
        f'<g>{"".join(nodes)}</g>'
        f'{center}'
        f'</svg>\n'
    )


# --------------------------------------------------------------------------- #
def _demo_avatar(label, hue):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="hsl({hue},38%,36%)"/>'
        f'<stop offset="1" stop-color="hsl({(hue + 40) % 360},48%,22%)"/>'
        '</linearGradient></defs><rect width="100" height="100" fill="url(#g)"/>'
        f'<text x="50" y="66" font-size="48" font-family="Arial" font-weight="700" text-anchor="middle" '
        f'fill="rgba(255,255,255,.88)">{label[:1].upper()}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def demo_data():
    orgs = [
        ("Codemo Open Source Labs", 412),
        ("redline-security", 268),
        ("agentforge", 190),
        ("sandbox-works", 143),
        ("sigma-rules", 97),
        ("zero-trust-kit", 64),
    ]
    people = [
        ("Ali Raza", 58),
        ("mchen", 41),
        ("sarah-k", 33),
        ("n0va", 27),
        ("Tariq Aziz", 19),
        ("lena-dev", 12),
        ("pwn-ninja", 8),
        ("dr-fuzz", 5),
    ]
    mk = lambda lst, k, base: [
        {"name": n, "count": c, "kind": k, "avatar": _demo_avatar(n, (base + i * 47) % 360)}
        for i, (n, c) in enumerate(lst)
    ]
    return mk(orgs, "org", 180), mk(people, "user", 20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_ACTOR", ""))
    ap.add_argument("--out", default="assets/contribution-map.svg")
    ap.add_argument("--top-orgs", type=int, default=8, help="max organizations shown")
    ap.add_argument("--top-people", type=int, default=10, help="max people shown")
    ap.add_argument("--radius", type=float, default=None, help="map radius in px (auto-sized concisely if omitted)")
    ap.add_argument("--no-people", action="store_true", help="organizations only")
    ap.add_argument("--exclude", default="", help="comma-separated logins to hide")
    ap.add_argument("--demo", action="store_true", help="offline preview with fake data")
    args = ap.parse_args()

    if args.demo:
        user = args.user or "uzairshahidgithub"
        user_avatar = _demo_avatar(user, 210)
        orgs, people = demo_data()
        if args.no_people:
            people = []
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token or not args.user:
            sys.exit("Need --user and GITHUB_TOKEN (or use --demo).")
        user = args.user
        avatar_url, raw = collect(user, token)
        user_avatar = fetch_data_uri(avatar_url)
        hide = {s.strip().lower() for s in args.exclude.split(",") if s.strip()}
        by_kind = {"org": [], "user": []}
        for login, o in raw.items():
            if login.lower() in hide:
                continue
            by_kind[o["kind"]].append(
                {
                    "name": o["name"],
                    "count": o["count"],
                    "kind": o["kind"],
                    "avatar_url": o["avatar_url"],
                }
            )
        orgs = sorted(by_kind["org"], key=lambda o: o["count"], reverse=True)[: args.top_orgs]
        people = (
            []
            if args.no_people
            else sorted(by_kind["user"], key=lambda o: o["count"], reverse=True)[: args.top_people]
        )
        for item in orgs + people:
            item["avatar"] = fetch_data_uri(item.pop("avatar_url"))

    orgs.sort(key=lambda o: o["count"], reverse=True)
    people.sort(key=lambda o: o["count"], reverse=True)
    svg = render(user, user_avatar, orgs, people, radius=args.radius)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {args.out}: {len(orgs)} organizations, {len(people)} people, {len(svg) // 1024} KB")


if __name__ == "__main__":
    main()
