"""Generate the 'aykut-top' terminal dashboard and the clickable link line.

The dashboard looks like a full-screen terminal monitor (btop / k9s style) and
is drawn from live data: the last year of contributions as a heatmap with a
scanning beam, commits per project, monthly activity and streaks.

Outputs (dark and light):
  assets/top-{theme}.svg   the dashboard
  assets/link.svg          a terminal line that the README wraps in a link

Standard library only. Needs GITHUB_TOKEN for the contribution calendar;
without it the heatmap is drawn empty.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import CONFIG, OUT_DIR, ROOT, api, load_buildings  # noqa: E402

W = 860
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
LINKEDIN = "linkedin.com/in/aykut-efe-caglayan"

THEMES = {
    "dark": {
        "bg": "#0d1117", "bar": "#161b22", "border": "#30363d", "box": "#3b4a7a",
        "title": "#8b949e", "text": "#c9d1d9", "dim": "#6e7681", "key": "#79c0ff",
        "accent": "#5fd4ff", "accent2": "#d2a8ff", "ok": "#3fb950", "warn": "#d29922",
        "prompt": "#7ee0b5", "hot": "#ff7b72",
        "heat": ["#161b22", "#0b3a53", "#0f6a8f", "#1fa3d1", "#5fd4ff"],
        "beam": "#5fd4ff", "bar_bg": "#161b22", "hint_bg": "#1f6feb", "hint_fg": "#ffffff",
    },
    "light": {
        "bg": "#ffffff", "bar": "#f6f8fa", "border": "#d0d7de", "box": "#9aaccc",
        "title": "#57606a", "text": "#24292f", "dim": "#6e7781", "key": "#0969da",
        "accent": "#0969da", "accent2": "#8250df", "ok": "#1a7f37", "warn": "#9a6700",
        "prompt": "#1a7f37", "hot": "#cf222e",
        "heat": ["#ebeef3", "#b6e3ff", "#54aeff", "#0969da", "#0a3069"],
        "beam": "#0969da", "bar_bg": "#eef1f5", "hint_bg": "#0969da", "hint_fg": "#ffffff",
    },
}


def calendar(user: str, token: str | None) -> tuple[list[dict], str | None]:
    if not token:
        return [], None
    query = ('{ user(login: "%s") { createdAt contributionsCollection { contributionCalendar '
             '{ weeks { contributionDays { date contributionCount } } } } } }' % user)
    try:
        _, body = api("https://api.github.com/graphql", token, json.dumps({"query": query}).encode())
        u = body["data"]["user"]
        weeks = u["contributionsCollection"]["contributionCalendar"]["weeks"]
        return [d for w in weeks for d in w["contributionDays"]], u["createdAt"]
    except Exception:  # noqa: BLE001 - any API failure falls back to an empty heatmap
        return [], None


def streaks(days: list[dict]) -> tuple[int, int]:
    longest = run = 0
    for d in days:
        run = run + 1 if d["contributionCount"] else 0
        longest = max(longest, run)
    current = 0
    for d in reversed(days):
        if d["contributionCount"]:
            current += 1
        elif current or d is not days[-1]:  # today may still be empty
            break
    return current, longest


def age(created: str | None, today: dt.date) -> str:
    if not created:
        return "?"
    c = dt.date.fromisoformat(created[:10])
    months = (today.year - c.year) * 12 + today.month - c.month
    return f"{months // 12}y {months % 12}m"


def level(count: int, peak: int) -> int:
    if count == 0:
        return 0
    return min(4, 1 + int(3.2 * (count / max(peak, 1)) ** 0.5))


def box(o: list[str], c: dict, x: float, y: float, w: float, h: float, title: str) -> None:
    o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="none" stroke="{c["box"]}"/>')
    tw = len(title) * 7.8 + 12
    o.append(f'<rect x="{x + 12}" y="{y - 8}" width="{tw:.0f}" height="16" fill="{c["bg"]}"/>')
    o.append(f'<text x="{x + 18}" y="{y + 4}" fill="{c["accent"]}">{escape(title)}</text>')


def render_top(theme: str, days: list[dict], created: str | None, projects: list[dict], today: dt.date) -> str:
    c = THEMES[theme]
    H = 470
    o: list[str] = []
    add = o.append
    total = sum(d["contributionCount"] for d in days)
    peak = max((d["contributionCount"] for d in days), default=0)
    current, longest = streaks(days)
    busiest = max(days, key=lambda d: d["contributionCount"]) if days else None

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="aykut-top: {total} contributions in the last year, commits per project and streaks">')
    add(f"""<style>
text {{ font-family: {MONO}; font-size: 13px; white-space: pre }}
.cell {{ opacity: 0; animation: pop .35s ease-out forwards }}
@keyframes pop {{ from {{ opacity: 0 }} to {{ opacity: 1 }} }}
.beam {{ animation: scan 7s linear infinite }}
@keyframes scan {{ from {{ transform: translateX(0) }} to {{ transform: translateX(742px) }} }}
.grow {{ transform-box: fill-box; transform-origin: left center; transform: scaleX(0); animation: grow 1.2s cubic-bezier(.2,.8,.2,1) forwards }}
@keyframes grow {{ to {{ transform: scaleX(1) }} }}
.blink {{ animation: blink 1s steps(1) infinite }}
@keyframes blink {{ 50% {{ opacity: 0 }} }}
.live {{ animation: live 1.6s ease-in-out infinite }}
@keyframes live {{ 0%,100% {{ opacity: .3 }} 50% {{ opacity: 1 }} }}
</style>""")
    add(f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="{c["bg"]}" stroke="{c["border"]}"/>')
    add(f'<path d="M.5 36V10.5a10 10 0 0 1 10-10h{W - 21}a10 10 0 0 1 10 10V36z" fill="{c["bar"]}"/>')
    add(f'<line x1="0" y1="36" x2="{W}" y2="36" stroke="{c["border"]}"/>')
    for k, col in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        add(f'<circle cx="{22 + k * 20}" cy="18" r="6" fill="{col}"/>')
    add(f'<text x="{W / 2}" y="23" text-anchor="middle" fill="{c["title"]}" style="font-size:12px">aykut@cloud: ~ — aykut-top</text>')

    # Header line
    add(f'<text x="24" y="62"><tspan fill="{c["accent2"]}">aykut-top</tspan>'
        f'<tspan fill="{c["dim"]}">  ·  </tspan><tspan fill="{c["text"]}">{today.isoformat()}</tspan>'
        f'<tspan fill="{c["dim"]}">  ·  account age </tspan><tspan fill="{c["text"]}">{age(created, today)}</tspan>'
        f'<tspan fill="{c["dim"]}">  ·  refresh </tspan><tspan fill="{c["text"]}">24h</tspan></text>')
    add(f'<circle class="live" cx="{W - 70}" cy="58" r="4" fill="{c["ok"]}"/>'
        f'<text x="{W - 60}" y="62" fill="{c["ok"]}">LIVE</text>')

    # Heatmap box
    bx, by, bw, bh = 20, 84, W - 40, 150
    box(o, c, bx, by, bw, bh, f" contributions · last 52 weeks · {total} total ")
    gx, gy, cell, gap = 46, 108, 11, 3
    weeks = [days[i:i + 7] for i in range(0, len(days), 7)][-53:]
    for wi, week in enumerate(weeks):
        for d in week:
            wd = (dt.date.fromisoformat(d["date"]).weekday() + 1) % 7  # Sunday first, like GitHub
            lv = level(d["contributionCount"], peak)
            add(f'<rect class="cell" x="{gx + wi * (cell + gap)}" y="{gy + wd * (cell + gap)}" width="{cell}" height="{cell}" '
                f'rx="2" fill="{c["heat"][lv]}" style="animation-delay:{0.3 + wi * 0.025:.3f}s"/>')
    if not weeks:
        add(f'<text x="{gx}" y="{gy + 50}" fill="{c["dim"]}">no data (GITHUB_TOKEN missing)</text>')
    for label, row in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        add(f'<text x="24" y="{gy + row * (cell + gap) + 9}" fill="{c["dim"]}" style="font-size:9px">{label}</text>')
    # Month labels
    last_month = None
    for wi, week in enumerate(weeks):
        m = dt.date.fromisoformat(week[0]["date"]).strftime("%b")
        if m != last_month and wi < len(weeks) - 2:
            add(f'<text x="{gx + wi * (cell + gap)}" y="{gy + 7 * (cell + gap) + 12}" fill="{c["dim"]}" style="font-size:9px">{m}</text>')
            last_month = m
    # Scanning beam
    add(f'<defs><linearGradient id="bm" x1="0" x2="1"><stop offset="0" stop-color="{c["beam"]}" stop-opacity="0"/>'
        f'<stop offset=".8" stop-color="{c["beam"]}" stop-opacity=".35"/><stop offset="1" stop-color="{c["beam"]}" stop-opacity=".9"/></linearGradient></defs>')
    add(f'<rect class="beam" x="{gx - 40}" y="{gy - 4}" width="40" height="{7 * (cell + gap) + 4}" fill="url(#bm)"/>')

    # Commits per project
    px, py, pw, ph = 20, 256, 500, 170
    box(o, c, px, py, pw, ph, " kubectl top projects --sort=commits ")
    ranked = sorted(projects, key=lambda p: -p["commits"])[:6]
    top_commits = max((p["commits"] for p in ranked), default=1)
    for i, p in enumerate(ranked):
        y = py + 30 + i * 22
        width = 230 * p["commits"] / top_commits
        add(f'<text x="{px + 16}" y="{y + 9}" fill="{c["text"]}">{escape(p["name"][:17]):<17}</text>')
        add(f'<rect x="{px + 170}" y="{y}" width="230" height="11" rx="2" fill="{c["bar_bg"]}"/>')
        add(f'<rect class="grow" x="{px + 170}" y="{y}" width="{width:.0f}" height="11" rx="2" fill="{c["accent"] if i else c["accent2"]}" '
            f'style="animation-delay:{1.2 + i * 0.12:.2f}s"/>')
        add(f'<text x="{px + 410}" y="{y + 9}" fill="{c["dim"]}">{p["commits"]:>4} commits</text>')

    # Stats and monthly sparkline
    sx, sy, sw, sh = 536, 256, W - 556, 170
    box(o, c, sx, sy, sw, sh, " stats ")
    rows = [
        ("contributions", str(total), c["accent"]),
        ("current streak", f"{current} days", c["ok"] if current else c["dim"]),
        ("longest streak", f"{longest} days", c["warn"]),
        ("busiest day", f"{busiest['date']} ({busiest['contributionCount']})" if busiest else "-", c["hot"]),
    ]
    for i, (k, v, col) in enumerate(rows):
        y = sy + 34 + i * 22
        add(f'<text x="{sx + 16}" y="{y}" fill="{c["key"]}">{k}</text>'
            f'<text x="{sx + sw - 16}" y="{y}" text-anchor="end" fill="{col}">{escape(v)}</text>')
    months: dict[str, int] = {}
    for d in days:
        months[d["date"][:7]] = months.get(d["date"][:7], 0) + d["contributionCount"]
    series = list(months.values())[-12:]
    top_m = max(series, default=1) or 1
    add(f'<text x="{sx + 16}" y="{sy + 132}" fill="{c["dim"]}" style="font-size:11px">activity / month</text>')
    for i, v in enumerate(series):
        h = 4 + 26 * v / top_m
        add(f'<rect class="grow" x="{sx + 16 + i * 22}" y="{sy + 160 - h:.0f}" width="16" height="{h:.0f}" rx="2" '
            f'fill="{c["accent2"]}" opacity="{0.45 + 0.55 * v / top_m:.2f}" style="animation-delay:{1.6 + i * 0.05:.2f}s;transform-origin:center bottom"/>')

    # k9s-style key hints
    hy = H - 26
    x = 24
    for key, label in (("l", "linkedin"), ("c", "cloudcity"), ("r", "reappkit"), ("?", "help"), ("q", "quit")):
        add(f'<rect x="{x}" y="{hy - 12}" width="22" height="17" rx="3" fill="{c["hint_bg"]}"/>'
            f'<text x="{x + 11}" y="{hy + 1}" text-anchor="middle" fill="{c["hint_fg"]}">{key}</text>'
            f'<text x="{x + 30}" y="{hy + 1}" fill="{c["dim"]}">{label}</text>')
        x += 30 + len(label) * 7.8 + 22
    add(f'<rect class="blink" x="{W - 40}" y="{hy - 12}" width="8" height="15" fill="{c["text"]}"/>')
    add("</svg>")
    return "\n".join(o)


def render_link(theme: str) -> str:
    c = THEMES[theme]
    H = 52
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="Open my LinkedIn profile">
<style>text {{ font-family: {MONO}; font-size: 14px; white-space: pre }}
.blink {{ animation: blink 1s steps(1) infinite }} @keyframes blink {{ 50% {{ opacity: 0 }} }}
.glow {{ animation: glow 2.4s ease-in-out infinite }} @keyframes glow {{ 0%,100% {{ stroke-opacity: .35 }} 50% {{ stroke-opacity: 1 }} }}</style>
<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="{c["bg"]}" stroke="{c["border"]}"/>
<rect class="glow" x="3" y="3" width="{W - 6}" height="{H - 6}" rx="8" fill="none" stroke="{c["accent"]}"/>
<text x="24" y="31"><tspan fill="{c["prompt"]}">aykut@cloud:~$ </tspan><tspan fill="{c["text"]}">open </tspan><tspan fill="{c["accent"]}" text-decoration="underline">https://{LINKEDIN}</tspan></text>
<rect class="blink" x="566" y="18" width="8" height="16" fill="{c["text"]}"/>
<text x="{W - 24}" y="31" text-anchor="end" fill="{c["dim"]}">click to connect ↗</text>
</svg>"""


def main() -> int:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    token = os.environ.get("GITHUB_TOKEN")
    days, created = calendar(cfg["user"], token)
    projects = load_buildings(cfg, token)
    today = dt.datetime.now(dt.timezone.utc).date()
    OUT_DIR.mkdir(exist_ok=True)
    outputs = [(f"top-{theme}.svg", render_top(theme, days, created, projects, today)) for theme in THEMES]
    # GitHub drops the link around a <picture>, so the link line is a single dark image.
    outputs.append(("link.svg", render_link("dark")))
    for name, svg in outputs:
        path = OUT_DIR / name
        path.write_text(svg, encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
