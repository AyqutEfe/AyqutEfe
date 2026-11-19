"""Generate the animated cloud city banner for the GitHub profile.

The city floats above a sea of clouds. Three islands stand for cluster nodes,
and each project in city.json is an isometric building on one of them; its
height follows the project's commit count. Requests travel between islands,
and one building is "degraded" each day. Output: assets/city-dark.svg and
assets/city-light.svg.

Standard library only. GITHUB_TOKEN is optional: without it, commit counts
fall back to the values in city.json and the contribution line is hidden.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import random
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
CONFIG = Path(__file__).resolve().parent / "city.json"
OUT_DIR = ROOT / "assets"

W, H = 1200, 600
SANS = "'Segoe UI', Ubuntu, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace"
COS, SIN = math.cos(math.radians(30)), math.sin(math.radians(30))

THEMES = {
    "dark": {
        "sky": ["#03040d", "#0a1030", "#1b1f52", "#3a2a6b"],
        "aurora": ["#36f1cd", "#4d7cff", "#c86bfa"],
        "stars": True,
        "orb": "#f6f3d7", "orb_glow": "#9fb4ff",
        "haze": "#4d5bd6",
        "top": ["#2a3a6e", "#1d2a55"],
        "left": ["#1a2550", "#121a3a"],
        "right": ["#24336a", "#18224a"],
        "edge": "#5a73c9",
        "win_on": "#ffd27a", "win_warm": "#ff9e5e", "win_off": "#151d3d",
        "isl_top": ["#2b3f7a", "#1c2b59"],
        "isl_grass": "#2f8f83",
        "rock": ["#1b2147", "#0a0d22"],
        "crystal": "#6be4ff",
        "link": "#5fd4ff",
        "packet": ["#5fd4ff", "#ff6bd6", "#7dffb2"],
        "cloud": ["#2a2f6e", "#3b3f86", "#555aa8"],
        "cloud_op": 0.85,
        "panel": "#060a1ccc", "panel_edge": "#3b4a8a",
        "title": "#ffffff", "sub": "#9fdcff", "mono": "#7dffb2",
        "label": "#dbe4ff", "label_bg": "#0a1030cc",
        "lit": 0.6,
    },
    "light": {
        "sky": ["#3f8ee8", "#7cb9f5", "#bfe0ff", "#ffe1c7"],
        "aurora": ["#ffffff", "#ffe8b0", "#ffd0e8"],
        "stars": False,
        "orb": "#fff7d1", "orb_glow": "#ffd27a",
        "haze": "#ffffff",
        "top": ["#c9d6f2", "#aebfe6"],
        "left": ["#6f84b8", "#5a6ea3"],
        "right": ["#8ea2d1", "#7a8fc2"],
        "edge": "#ffffff",
        "win_on": "#fff3c4", "win_warm": "#ffe2a8", "win_off": "#4f6296",
        "isl_top": ["#9be3b0", "#6cc597"],
        "isl_grass": "#4fb38a",
        "rock": ["#8a7a9e", "#5b4f72"],
        "crystal": "#ffffff",
        "link": "#ffffff",
        "packet": ["#ffffff", "#ffd166", "#ff8fc7"],
        "cloud": ["#ffffff", "#f3f6ff", "#e6edff"],
        "cloud_op": 0.95,
        "panel": "#ffffffc0", "panel_edge": "#ffffff",
        "title": "#0b1533", "sub": "#0b4f8a", "mono": "#0b5d3b",
        "label": "#0b1533", "label_bg": "#ffffffcc",
        "lit": 0.25,
    },
}

# Islands (cluster nodes): screen anchor of the island's back corner, bob delay.
ISLANDS = [(260, 300, 0.0), (600, 262, 1.4), (940, 300, 2.6)]
TILE = 150          # island side in iso units
LOTS = [(10, 58), (90, 52)]   # building positions on an island (iso units)
BW = 46             # building footprint (iso units)


def api(url: str, token: str | None, data: bytes | None = None):
    req = urllib.request.Request(url, data=data)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-city-generator")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.headers, json.loads(resp.read() or b"null")


def commit_count(user: str, repo: str, token: str | None) -> int | None:
    url = f"https://api.github.com/repos/{user}/{repo}/commits?per_page=1"
    try:
        headers, body = api(url, token)
    except (urllib.error.URLError, TimeoutError):
        return None
    match = re.search(r'[?&]page=(\d+)>; rel="last"', headers.get("Link", ""))
    if match:
        return int(match.group(1))
    return len(body) if isinstance(body, list) else None


def contributions(user: str, token: str | None) -> int | None:
    if not token:
        return None
    query = '{ user(login: "%s") { contributionsCollection { contributionCalendar { totalContributions } } } }' % user
    try:
        _, body = api("https://api.github.com/graphql", token, json.dumps({"query": query}).encode())
        return body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    except (urllib.error.URLError, TimeoutError, KeyError, TypeError):
        return None


def load_buildings(cfg: dict, token: str | None) -> list[dict]:
    result = []
    for b in cfg["buildings"]:
        count = None
        if b.get("repo"):
            count = commit_count(cfg["user"], b["repo"], token)
        result.append({"name": b["name"], "commits": count or b.get("commits", 10)})
    return result


def pts(points) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


class Iso:
    """Isometric projection around an island's back corner."""

    def __init__(self, ox: float, oy: float):
        self.ox, self.oy = ox, oy

    def __call__(self, x: float, y: float, z: float = 0) -> tuple[float, float]:
        return self.ox + (x - y) * COS, self.oy + (x + y) * SIN - z


def css(t: dict) -> str:
    return f"""
text {{ white-space: pre }}
.tw {{ animation: tw 3.4s ease-in-out infinite }}
@keyframes tw {{ 0%,100% {{ opacity: .2 }} 50% {{ opacity: 1 }} }}
.aur {{ animation: aur 14s ease-in-out infinite alternate; transform-origin: 600px 120px }}
@keyframes aur {{ from {{ opacity: .35; transform: translateX(-40px) skewX(-6deg) }} to {{ opacity: .8; transform: translateX(40px) skewX(6deg) }} }}
.shoot {{ animation: shoot 11s linear infinite; opacity: 0 }}
@keyframes shoot {{ 0% {{ transform: translate(0,0); opacity: 0 }} 2% {{ opacity: 1 }} 8% {{ transform: translate(-320px,160px); opacity: 0 }} 100% {{ opacity: 0 }} }}
.bob {{ animation: bob 6s ease-in-out infinite }}
@keyframes bob {{ 0%,100% {{ transform: translateY(0) }} 50% {{ transform: translateY(-9px) }} }}
.fl {{ animation: fl 6s steps(1) infinite }}
@keyframes fl {{ 0%,100% {{ fill: {t['win_on']} }} 35% {{ fill: {t['win_off']} }} 60% {{ fill: {t['win_warm']} }} }}
.link {{ fill: none; stroke: {t['link']}; stroke-width: 1.6; stroke-dasharray: 2 8; stroke-linecap: round; opacity: .7; animation: flow 1.4s linear infinite }}
@keyframes flow {{ to {{ stroke-dashoffset: -20 }} }}
.beam {{ animation: beam 2.6s ease-in-out infinite }}
@keyframes beam {{ 0%,100% {{ opacity: .15 }} 50% {{ opacity: .55 }} }}
.ok {{ animation: tw 2.2s ease-in-out infinite }}
.alert {{ animation: alert 1.1s ease-in-out infinite }}
@keyframes alert {{ 0%,100% {{ opacity: .2 }} 50% {{ opacity: 1 }} }}
.smoke {{ animation: smoke 3.6s ease-out infinite; opacity: 0; transform-box: fill-box; transform-origin: center }}
@keyframes smoke {{ 0% {{ transform: translate(0,0) scale(.6); opacity: 0 }} 15% {{ opacity: .55 }} 100% {{ transform: translate(14px,-70px) scale(2.2); opacity: 0 }} }}
.drift {{ animation: drift linear infinite }}
@keyframes drift {{ from {{ transform: translateX(0) }} to {{ transform: translateX(-{W}px) }} }}
.drift2 {{ animation: drift2 linear infinite }}
@keyframes drift2 {{ from {{ transform: translateX(-{W}px) }} to {{ transform: translateX(0) }} }}
.in {{ opacity: 0; animation: in 1.1s ease-out forwards }}
@keyframes in {{ from {{ opacity: 0; transform: translateY(10px) }} to {{ opacity: 1; transform: none }} }}
.cursor {{ animation: blink 1s steps(1) infinite }}
@keyframes blink {{ 50% {{ opacity: 0 }} }}
"""


def grad(gid: str, colors: list[str], vertical: bool = True) -> str:
    x2, y2 = ("0", "1") if vertical else ("1", "0")
    stops = "".join(f'<stop offset="{i / (len(colors) - 1):.2f}" stop-color="{c}"/>' for i, c in enumerate(colors))
    return f'<linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}">{stops}</linearGradient>'


def cloud_band(t: dict, rnd: random.Random, y: int, color: str, count: int, scale: float) -> str:
    """A horizontally repeating strip of puffy clouds (two copies for a seamless loop)."""
    puffs = []
    for _ in range(count):
        cx = rnd.uniform(0, W)
        r = rnd.uniform(28, 60) * scale
        puffs.append((cx, y + rnd.uniform(-10, 14), r))
    body = "".join(f'<ellipse cx="{cx:.0f}" cy="{cy:.0f}" rx="{r * 1.6:.0f}" ry="{r:.0f}"/>' for cx, cy, r in puffs)
    base = f'<rect x="0" y="{y + 10}" width="{W}" height="{H - y}"/>'
    return (f'<g fill="{color}">{body}{base}'
            f'<g transform="translate({W} 0)">{body}{base}</g></g>')


def building(o: list[str], t: dict, iso: Iso, rnd: random.Random, x: float, y: float, h: float,
             name: str, degraded: bool, idx: int, labels: list[str]) -> None:
    add = o.append
    w = d = BW
    top = [iso(x, y, h), iso(x + w, y, h), iso(x + w, y + d, h), iso(x, y + d, h)]
    left = [iso(x, y + d, 0), iso(x + w, y + d, 0), iso(x + w, y + d, h), iso(x, y + d, h)]
    right = [iso(x + w, y, 0), iso(x + w, y + d, 0), iso(x + w, y + d, h), iso(x + w, y, h)]

    # Soft light spill on the island under the building
    gx, gy = iso(x + w / 2, y + d / 2, 0)
    add(f'<ellipse cx="{gx:.0f}" cy="{gy + 4:.0f}" rx="{w * 1.25:.0f}" ry="{w * 0.55:.0f}" '
        f'fill="{"#ff3b5c" if degraded else t["win_on"]}" opacity="{0.28 if degraded else 0.12}" filter="url(#soft)"/>')

    add(f'<polygon points="{pts(left)}" fill="url(#gl)"/>')
    add(f'<polygon points="{pts(right)}" fill="url(#gr)"/>')
    add(f'<polygon points="{pts(top)}" fill="url(#gt)" stroke="{t["edge"]}" stroke-opacity=".5" stroke-width=".8"/>')
    add(f'<polyline points="{pts([iso(x, y + d, h), iso(x + w, y + d, h), iso(x + w, y, h)])}" '
        f'fill="none" stroke="{t["edge"]}" stroke-opacity=".8" stroke-width="1"/>')
    add(f'<line x1="{iso(x + w, y + d, 0)[0]:.1f}" y1="{iso(x + w, y + d, 0)[1]:.1f}" '
        f'x2="{iso(x + w, y + d, h)[0]:.1f}" y2="{iso(x + w, y + d, h)[1]:.1f}" stroke="{t["edge"]}" stroke-opacity=".45"/>')

    # Windows on both visible faces
    floors = int((h - 14) // 13)
    for face in ("left", "right"):
        for f in range(floors):
            z0 = 10 + f * 13
            for c in range(3):
                u0 = 7 + c * 13
                if face == "left":
                    quad = [iso(x + u0, y + d, z0), iso(x + u0 + 8, y + d, z0),
                            iso(x + u0 + 8, y + d, z0 + 7), iso(x + u0, y + d, z0 + 7)]
                else:
                    quad = [iso(x + w, y + u0, z0), iso(x + w, y + u0 + 8, z0),
                            iso(x + w, y + u0 + 8, z0 + 7), iso(x + w, y + u0, z0 + 7)]
                roll = rnd.random()
                flick = rnd.random() < 0.14
                delay = rnd.uniform(0, 6)
                if degraded and rnd.random() < 0.5:
                    add(f'<polygon class="alert" points="{pts(quad)}" fill="#ff4d6d" style="animation-delay:{delay % 1.1:.2f}s"/>')
                elif flick:
                    add(f'<polygon class="fl" points="{pts(quad)}" fill="{t["win_on"]}" style="animation-delay:{delay:.2f}s"/>')
                else:
                    fill = t["win_on"] if roll < t["lit"] * 0.8 else t["win_warm"] if roll < t["lit"] else t["win_off"]
                    add(f'<polygon points="{pts(quad)}" fill="{fill}"/>')

    # Roof: antenna and status light
    ax, ay = iso(x + w / 2, y + d / 2, h)
    add(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{ax:.1f}" y2="{ay - 22:.1f}" stroke="{t["edge"]}" stroke-width="1.6"/>')
    if degraded:
        add(f'<circle class="alert" cx="{ax:.1f}" cy="{ay - 24:.1f}" r="5" fill="#ff3b5c" filter="url(#glow)"/>')
        for k in range(4):
            add(f'<circle class="smoke" cx="{ax - 6:.1f}" cy="{ay - 2:.1f}" r="6" fill="#8b8fa8" '
                f'style="animation-delay:{k * 0.9:.1f}s"/>')
    else:
        add(f'<polygon class="beam" points="{ax:.1f},{ay - 24:.1f} {ax - 14:.1f},{ay - 120:.1f} {ax + 14:.1f},{ay - 120:.1f}" '
            f'fill="url(#beam)" style="animation-delay:{idx * 0.4:.1f}s"/>')
        add(f'<circle class="ok" cx="{ax:.1f}" cy="{ay - 24:.1f}" r="3" fill="#7dffb2" filter="url(#glow)" '
            f'style="animation-delay:{idx * 0.3:.1f}s"/>')

    # Name tag floating beside the building base (drawn later, above the buildings)
    lx, ly = iso(x + w, y + d, 0)
    label = escape(name)
    tw = 7.2 * len(name) + 14
    labels.append(f'<g transform="translate({lx - tw / 2:.0f} {ly + 6:.0f})">'
        f'<rect width="{tw:.0f}" height="18" rx="9" fill="{t["label_bg"]}" stroke="{"#ff3b5c" if degraded else t["edge"]}" stroke-opacity=".7"/>'
        f'<text x="{tw / 2:.0f}" y="13" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{t["label"]}">{label}</text></g>')


def island(o: list[str], t: dict, iso: Iso, rnd: random.Random, degraded_here: bool) -> None:
    add = o.append
    L = TILE
    a, b, c, d = iso(0, 0), iso(L, 0), iso(L, L), iso(0, L)
    tip = iso(L * 0.55, L * 0.55, -150)
    # Glow under the island
    add(f'<ellipse cx="{c[0]:.0f}" cy="{(a[1] + c[1]) / 2 + 40:.0f}" rx="{L * 1.0:.0f}" ry="{L * 0.35:.0f}" '
        f'fill="{"#ff3b5c" if degraded_here else t["crystal"]}" opacity=".18" filter="url(#soft)"/>')
    # Rocky underside: two faces meeting at a tip
    add(f'<polygon points="{pts([d, c, tip])}" fill="url(#rockL)"/>')
    add(f'<polygon points="{pts([c, b, tip])}" fill="url(#rockR)"/>')
    for _ in range(5):  # crystals in the rock
        u, v = rnd.uniform(0.25, 0.75), rnd.uniform(0.15, 0.6)
        side = (d, c) if rnd.random() < 0.5 else (c, b)
        px = side[0][0] + (side[1][0] - side[0][0]) * u
        py = side[0][1] + (side[1][1] - side[0][1]) * u
        px += (tip[0] - px) * v
        py += (tip[1] - py) * v
        add(f'<polygon class="tw" points="{px:.0f},{py - 6:.0f} {px + 3:.0f},{py:.0f} {px:.0f},{py + 6:.0f} {px - 3:.0f},{py:.0f}" '
            f'fill="{t["crystal"]}" style="animation-delay:{rnd.uniform(0, 3):.1f}s"/>')
    # Top surface with an edge and a lane grid
    add(f'<polygon points="{pts([a, b, c, d])}" fill="url(#isl)" stroke="{t["edge"]}" stroke-opacity=".6"/>')
    add(f'<polyline points="{pts([d, c, b])}" fill="none" stroke="{t["isl_grass"]}" stroke-width="3"/>')
    for k in (L / 3, 2 * L / 3):
        p1, p2 = iso(k, 4), iso(k, L - 4)
        q1, q2 = iso(4, k), iso(L - 4, k)
        add(f'<line x1="{p1[0]:.1f}" y1="{p1[1]:.1f}" x2="{p2[0]:.1f}" y2="{p2[1]:.1f}" stroke="{t["edge"]}" stroke-opacity=".18"/>')
        add(f'<line x1="{q1[0]:.1f}" y1="{q1[1]:.1f}" x2="{q2[0]:.1f}" y2="{q2[1]:.1f}" stroke="{t["edge"]}" stroke-opacity=".18"/>')


def render(theme: str, cfg: dict, buildings: list[dict], total: int | None, today: dt.date) -> str:
    t = THEMES[theme]
    rnd = random.Random(7)
    o: list[str] = []
    add = o.append
    n = len(buildings)
    incident = today.toordinal() % n
    max_log = max(math.log(b["commits"] + 1) for b in buildings)

    add(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" aria-label="{escape(cfg["title"])}: a floating cloud city where each building is a project">')
    add("<defs>")
    add(grad("sky", t["sky"]))
    add(grad("gt", t["top"], False))
    add(grad("gl", t["left"]))
    add(grad("gr", t["right"]))
    add(grad("isl", t["isl_top"], False))
    add(grad("rockL", t["rock"]))
    add(grad("rockR", [t["rock"][0], t["rock"][1]], False))
    add(f'<linearGradient id="beam" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{t["link"]}" stop-opacity=".7"/>'
        f'<stop offset="1" stop-color="{t["link"]}" stop-opacity="0"/></linearGradient>')
    add(f'<linearGradient id="aur" x1="0" y1="0" x2="1" y2="0">'
        + "".join(f'<stop offset="{i / 2:.1f}" stop-color="{col}"/>' for i, col in enumerate(t["aurora"]))
        + "</linearGradient>")
    add(f'<radialGradient id="orb"><stop offset="0" stop-color="{t["orb_glow"]}" stop-opacity=".6"/>'
        f'<stop offset="1" stop-color="{t["orb_glow"]}" stop-opacity="0"/></radialGradient>')
    add('<filter id="glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="2.5" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    add('<filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="14"/></filter>')
    add('<filter id="blur" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="22"/></filter>')
    add(f"<style>{css(t)}</style>")
    add("</defs>")

    # Sky, aurora, stars, moon
    add(f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')
    add('<g class="aur" filter="url(#blur)">'
        f'<path d="M-50 150 C 200 40, 420 200, 650 90 S 1050 30, 1260 120 L 1260 190 C 1000 110, 820 250, 600 170 S 180 120, -50 230 Z" fill="url(#aur)" opacity=".55"/>'
        "</g>")
    for _ in range(110):
        x, y = rnd.uniform(0, W), rnd.uniform(0, 330)
        r = rnd.choice([0.5, 0.7, 0.9, 1.2, 1.6])
        delay = rnd.uniform(0, 3.4)
        if t["stars"]:
            add(f'<circle class="tw" cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="#ffffff" style="animation-delay:{delay:.2f}s"/>')
    if t["stars"]:
        add('<g class="shoot"><line x1="1000" y1="40" x2="1060" y2="10" stroke="#ffffff" stroke-width="1.5" stroke-linecap="round" opacity=".9"/></g>')
    add('<circle cx="1080" cy="86" r="90" fill="url(#orb)"/>')
    add(f'<circle cx="1080" cy="86" r="30" fill="{t["orb"]}"/>')
    if t["stars"]:
        add(f'<circle cx="1070" cy="80" r="5" fill="{t["sky"][2]}" opacity=".15"/><circle cx="1092" cy="96" r="3.5" fill="{t["sky"][2]}" opacity=".15"/>')

    # Far cloud layer
    add(f'<g class="drift2" style="animation-duration:160s" opacity="{t["cloud_op"] * 0.55}">{cloud_band(t, rnd, 455, t["cloud"][0], 14, 0.9)}</g>')

    # Islands and their buildings, back to front
    lots = [(ISLANDS[i // 2], LOTS[i % 2]) for i in range(n)]
    roof_points = []
    island_tops = []
    for ii, (ox, oy, delay) in enumerate(ISLANDS):
        iso = Iso(ox, oy)
        add(f'<g class="bob" style="animation-delay:-{delay:.1f}s">')
        members = [k for k in range(n) if k // 2 == ii]
        island(o, t, iso, rnd, incident in members)
        island_tops.append(iso(TILE / 2, TILE / 2))
        labels: list[str] = []
        for k in sorted(members, key=lambda k: sum(LOTS[k % 2])):
            lx, ly = LOTS[k % 2]
            h = 70 + 100 * math.log(buildings[k]["commits"] + 1) / max_log
            building(o, t, iso, rnd, lx, ly, h, buildings[k]["name"], k == incident, k, labels)
            roof_points.append(iso(lx + BW / 2, ly + BW / 2, h))
        o.extend(labels)
        add("</g>")

    # Links between islands with travelling packets
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(island_tops, island_tops[1:])):
        mx, my = (x1 + x2) / 2, min(y1, y2) - 90
        pid = f"lk{i}"
        add(f'<path id="{pid}" class="link" d="M{x1:.0f} {y1:.0f} Q{mx:.0f} {my:.0f} {x2:.0f} {y2:.0f}"/>')
        for k in range(3):
            col = t["packet"][(i + k) % 3]
            dur = 3.2 + k * 0.9
            reverse = 'keyPoints="1;0" keyTimes="0;1" calcMode="linear"' if k == 1 else ""
            add(f'<circle r="3.5" fill="{col}" filter="url(#glow)"><animateMotion dur="{dur:.1f}s" '
                f'begin="-{k * 1.1:.1f}s" repeatCount="indefinite" {reverse}><mpath xlink:href="#{pid}"/></animateMotion></circle>')

    # Near cloud layer drifting the other way
    add(f'<g class="drift" style="animation-duration:110s" opacity="{t["cloud_op"]}">{cloud_band(t, rnd, 525, t["cloud"][1], 16, 1.0)}</g>')
    add(f'<g class="drift2" style="animation-duration:80s" opacity="{t["cloud_op"]}">{cloud_band(t, rnd, 572, t["cloud"][2], 16, 0.8)}</g>')

    # Title panel
    ready = n - 1
    panel_h = 136 if total is not None else 116
    add(f'<g class="in"><rect x="24" y="22" width="560" height="{panel_h}" rx="12" fill="{t["panel"]}" '
        f'stroke="{t["panel_edge"]}" stroke-opacity=".6"/>')
    for k, col in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        add(f'<circle cx="{528 + k * 14}" cy="40" r="4" fill="{col}"/>')
    add(f'<text x="44" y="68" font-family="{SANS}" font-size="34" font-weight="700" fill="{t["title"]}">{escape(cfg["title"])}</text>')
    add(f'<text x="46" y="94" font-family="{SANS}" font-size="16" fill="{t["sub"]}">{escape(cfg["subtitle"])}</text></g>')
    status = f"$ kubectl get city  →  {n} services · {ready} Ready · 1 Degraded ({buildings[incident]['name']})"
    add(f'<g class="in" style="animation-delay:.5s"><text x="46" y="120" font-family="{MONO}" font-size="12.5" '
        f'fill="{t["mono"]}">{escape(status)}</text>')
    if total is not None:
        add(f'<text x="46" y="140" font-family="{MONO}" font-size="12.5" fill="{t["mono"]}" opacity=".8">'
            f'$ git log --since=1y | wc -l  →  {total} contributions</text>')
    add("</g>")

    add("</svg>")
    return "\n".join(o)


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    token = os.environ.get("GITHUB_TOKEN")
    buildings = load_buildings(cfg, token)[:6]  # three islands, two lots each
    total = contributions(cfg["user"], token)
    today = dt.datetime.now(dt.timezone.utc).date()
    OUT_DIR.mkdir(exist_ok=True)
    for theme in THEMES:
        path = OUT_DIR / f"city-{theme}.svg"
        path.write_text(render(theme, cfg, buildings, total, today), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")
    print("buildings:", ", ".join(f"{b['name']}={b['commits']}" for b in buildings), "| contributions:", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
