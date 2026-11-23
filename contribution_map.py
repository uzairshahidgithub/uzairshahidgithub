#!/usr/bin/env python3
"""
Linked map generator: a spider-web style SVG that shows how many contributions
you made to each organization, using the organization's logo and name.

Standard library only. Output is a self-contained SVG (avatars are embedded as
base64, because GitHub does not load external images inside an SVG).

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

API = "https://api.github.com/graphql"
UA = "contribution-map/1.0"

BG = "#0d1117"
PANEL = "#161b22"
GREEN = "#00ff9c"
DEEP = "#0a3d2e"
TEXT = "#c9d1d9"


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
        "... on Organization{ name } } } contributions{ totalCount }"
    )


def collect(login, token):
    """Return {org_login: {"name", "avatar", "count"}} across all years."""
    created = gql(
        "query($l:String!){ user(login:$l){ createdAt avatarUrl(size:200) } }",
        {"l": login},
        token,
    )["user"]
    start = dt.datetime.fromisoformat(created["createdAt"].replace("Z", "+00:00"))
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

    orgs = {}
    cursor = start
    while cursor < now:
        end = min(cursor + dt.timedelta(days=365), now)
        coll = gql(
            query,
            {"login": login, "from": cursor.isoformat(), "to": end.isoformat()},
            token,
        )["user"]["contributionsCollection"]
        for bucket in coll.values():
            for item in bucket:
                owner = item["repository"]["owner"]
                if owner["__typename"] != "Organization":
                    continue
                key = owner["login"]
                entry = orgs.setdefault(
                    key,
                    {"name": owner.get("name") or key, "avatar_url": owner["avatarUrl"], "count": 0},
                )
                entry["count"] += item["contributions"]["totalCount"]
        cursor = end
    return created["avatarUrl"], orgs


def fetch_data_uri(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            ctype = resp.headers.get("Content-Type", "image/png").split(";")[0]
            return f"data:{ctype};base64,{base64.b64encode(resp.read()).decode()}"
    except Exception as exc:  # network or 404: fall back to initials
        print(f"avatar fetch failed for {url}: {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def esc(s):
    return html.escape(str(s), quote=True)


def short(s, n=18):
    return s if len(s) <= n else s[: n - 1] + "…"


def node_image(idx, x, y, r, data_uri, label):
    clip = f"clip{idx}"
    if data_uri:
        inner = (
            f'<image href="{data_uri}" x="{x - r:.1f}" y="{y - r:.1f}" '
            f'width="{2 * r:.1f}" height="{2 * r:.1f}" clip-path="url(#{clip})" '
            f'preserveAspectRatio="xMidYMid slice"/>'
        )
    else:
        inner = (
            f'<text x="{x:.1f}" y="{y + r * 0.35:.1f}" text-anchor="middle" '
            f'font-size="{r * 0.95:.0f}" font-weight="700" fill="{GREEN}">{esc(label[:1].upper())}</text>'
        )
    return (
        f'<clipPath id="{clip}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}"/></clipPath>',
        inner,
    )


def render(user, user_avatar, orgs):
    W, H = 900, 660
    cx, cy = 450, 325
    rx, ry = 335, 200

    ordered = sorted(orgs.values(), key=lambda o: o["count"], reverse=True)
    n = len(ordered)
    peak = max((o["count"] for o in ordered), default=1)

    defs, back, links, nodes = [], [], [], []

    defs.append(
        '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    )
    defs.append(
        f'<radialGradient id="bg" cx="50%" cy="48%" r="65%">'
        f'<stop offset="0" stop-color="{DEEP}" stop-opacity="0.55"/>'
        f'<stop offset="1" stop-color="{BG}" stop-opacity="0"/></radialGradient>'
    )

    # Spider web: concentric ellipses + spokes
    for k in (0.25, 0.5, 0.75, 1.0):
        back.append(
            f'<ellipse cx="{cx}" cy="{cy}" rx="{(rx + 40) * k:.1f}" ry="{(ry + 35) * k:.1f}" '
            f'fill="none" stroke="{GREEN}" stroke-opacity="0.10" stroke-width="1"/>'
        )

    # Center node
    cr = 54
    defs.append(f'<clipPath id="clipc"><circle cx="{cx}" cy="{cy}" r="{cr}"/></clipPath>')

    for i, org in enumerate(ordered):
        ang = -math.pi / 2 + 2 * math.pi * i / max(n, 1)
        x = cx + rx * math.cos(ang)
        y = cy + ry * math.sin(ang)
        ratio = org["count"] / peak if peak else 0
        r = 26 + 16 * math.sqrt(ratio)

        # spoke (faint) and link (bright, animated)
        back.append(
            f'<line x1="{cx}" y1="{cy}" x2="{cx + (rx + 40) * math.cos(ang):.1f}" '
            f'y2="{cy + (ry + 35) * math.sin(ang):.1f}" stroke="{GREEN}" stroke-opacity="0.07"/>'
        )
        width = 1.2 + 2.6 * ratio
        ux, uy = math.cos(ang), math.sin(ang)
        # unit vector in screen space so lines end exactly on the rings
        dx, dy = x - cx, y - cy
        dist = math.hypot(dx, dy)
        ux, uy = dx / dist, dy / dist
        sx, sy = cx + ux * (cr + 8), cy + uy * (cr + 8)
        ex, ey = x - ux * (r + 7), y - uy * (r + 7)
        links.append(
            f'<line x1="{sx:.1f}" y1="{sy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" stroke="{GREEN}" '
            f'stroke-opacity="{0.35 + 0.45 * ratio:.2f}" stroke-width="{width:.1f}" '
            f'stroke-dasharray="6 8" stroke-linecap="round">'
            f'<animate attributeName="stroke-dashoffset" from="28" to="0" dur="{2.4 - ratio:.1f}s" '
            f'repeatCount="indefinite"/></line>'
        )

        clip_def, img = node_image(i, x, y, r, org.get("avatar"), org["name"])
        defs.append(clip_def)
        above = math.sin(ang) < -0.5
        name_y = y - r - 26 if above else y + r + 22
        count_y = y - r - 10 if above else y + r + 39
        nodes.append(
            f'<g><title>{esc(org["name"])}: {org["count"]:,} contributions</title>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r + 5:.1f}" fill="{PANEL}" stroke="{GREEN}" '
            f'stroke-opacity="0.9" stroke-width="2" filter="url(#glow)"/>'
            f'{img}'
            f'<text x="{x:.1f}" y="{name_y:.1f}" text-anchor="middle" font-size="13" '
            f'font-weight="600" fill="{TEXT}">{esc(short(org["name"]))}</text>'
            f'<text x="{x:.1f}" y="{count_y:.1f}" text-anchor="middle" font-size="12" '
            f'fill="{GREEN}">{org["count"]:,}</text></g>'
        )

    # center
    if user_avatar:
        center_img = (
            f'<image href="{user_avatar}" x="{cx - cr}" y="{cy - cr}" width="{2 * cr}" height="{2 * cr}" '
            f'clip-path="url(#clipc)" preserveAspectRatio="xMidYMid slice"/>'
        )
    else:
        center_img = (
            f'<text x="{cx}" y="{cy + 18}" text-anchor="middle" font-size="52" font-weight="700" '
            f'fill="{GREEN}">{esc(user[:1].upper())}</text>'
        )
    pulse = (
        f'<circle cx="{cx}" cy="{cy}" r="{cr}" fill="none" stroke="{GREEN}" stroke-width="2">'
        f'<animate attributeName="r" from="{cr + 4}" to="{cr + 34}" dur="3s" repeatCount="indefinite"/>'
        f'<animate attributeName="stroke-opacity" from="0.6" to="0" dur="3s" repeatCount="indefinite"/></circle>'
    )
    center = (
        f'{pulse}'
        f'<circle cx="{cx}" cy="{cy}" r="{cr + 6}" fill="{PANEL}" stroke="{GREEN}" stroke-width="3" filter="url(#glow)"/>'
        f'{center_img}'
        f'<rect x="{cx - 95}" y="{cy + cr + 12}" width="190" height="24" rx="12" fill="{BG}" stroke="{GREEN}" stroke-opacity="0.6"/>'
        f'<text x="{cx}" y="{cy + cr + 29}" text-anchor="middle" font-size="13" font-weight="600" '
        f'fill="{GREEN}">@{esc(short(user, 24))}</text>'
    )

    total = sum(o["count"] for o in ordered)
    header = (
        f'<text x="28" y="40" font-size="16" font-weight="700" fill="{TEXT}">Contribution map</text>'
        f'<text x="28" y="60" font-size="12" fill="{TEXT}" fill-opacity="0.65">'
        f'{total:,} contributions across {n} organization{"s" if n != 1 else ""}</text>'
    )
    empty = ""
    if n == 0:
        empty = (
            f'<text x="{cx}" y="{cy + 140}" text-anchor="middle" font-size="14" fill="{TEXT}" '
            f'fill-opacity="0.7">No organization contributions found yet</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" \
font-family="'Segoe UI', Helvetica, Arial, sans-serif" role="img" aria-label="Contribution map for {esc(user)}">
<defs>{''.join(defs)}</defs>
<rect width="{W}" height="{H}" rx="14" fill="{BG}"/>
<rect width="{W}" height="{H}" rx="14" fill="url(#bg)"/>
<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="14" fill="none" stroke="{GREEN}" stroke-opacity="0.25"/>
{header}
{''.join(back)}
{''.join(links)}
{''.join(nodes)}
{center}
{empty}
</svg>
"""


# --------------------------------------------------------------------------- #
def demo_orgs():
    sample = [
        ("openscan-labs", 412), ("redline-security", 268), ("agentforge", 190),
        ("sandbox-works", 143), ("sigma-rules", 97), ("zero-trust-kit", 64),
        ("fuzz-collective", 41), ("cloud-hardening", 23),
    ]
    return {k: {"name": k, "avatar": None, "count": c} for k, c in sample}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default=os.environ.get("GITHUB_ACTOR", ""))
    ap.add_argument("--out", default="assets/contribution-map.svg")
    ap.add_argument("--top", type=int, default=10, help="max organizations shown")
    ap.add_argument("--exclude", default="", help="comma-separated org logins to hide")
    ap.add_argument("--demo", action="store_true", help="offline preview with fake data")
    args = ap.parse_args()

    if args.demo:
        user = args.user or "uzairshahidgithub"
        user_avatar, orgs = None, demo_orgs()
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token or not args.user:
            sys.exit("Need --user and GITHUB_TOKEN (or use --demo).")
        user = args.user
        avatar_url, raw = collect(user, token)
        user_avatar = fetch_data_uri(avatar_url)
        hide = {s.strip().lower() for s in args.exclude.split(",") if s.strip()}
        orgs = {}
        for login, o in raw.items():
            if login.lower() in hide:
                continue
            orgs[login] = {"name": o["name"], "avatar": fetch_data_uri(o["avatar_url"]), "count": o["count"]}

    top = dict(sorted(orgs.items(), key=lambda kv: kv[1]["count"], reverse=True)[: args.top])
    svg = render(user, user_avatar, top)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"wrote {args.out} ({len(top)} organizations)")


if __name__ == "__main__":
    main()
