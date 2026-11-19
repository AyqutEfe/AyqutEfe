"""Generate an animated terminal window for the GitHub profile.

Commands are typed one character at a time, then their output appears line
by line. The animation uses SMIL <set>, which works inside <img>, and plays
once per page load. Output: assets/terminal-dark.svg and assets/terminal-light.svg.
"""

from __future__ import annotations

import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "assets"

PROMPT = "aykut@cloud:~$ "

# Each output line is a list of (text, color role) segments.
SESSION = [
    ("kubectl describe engineer aykut", [
        [("Name:        ", "key"), ("Aykut Efe Çağlayan", "value")],
        [("Role:        ", "key"), ("4th-year IST student @ Trakya University", "value")],
        [("Focus:       ", "key"), ("Cloud & DevOps", "accent")],
        [("Location:    ", "key"), ("Istanbul, Türkiye", "value")],
        [("Status:      ", "key"), ("● ", "ok"), ("Building CloudCity (graduation project)", "value")],
        [("Experience:", "key")],
        [("  - ", "dim"), ("vMind", "accent"), (": cloud engineering intern (Jul–Sep 2026)", "value")],
        [("Skills:", "key")],
        [("  cloud   ", "dim"), ("Linux · Docker · Kubernetes · Istio · Prometheus", "value")],
        [("  ci/cd   ", "dim"), ("Jenkins · Argo CD · GitHub Actions", "value")],
        [("  code    ", "dim"), ("Python · Go · Java · TypeScript", "value")],
    ]),
    ("kubectl get projects", [
        [("NAME                  STATUS     DESCRIPTION", "head")],
        [("django-devops-lab     ", "value"), ("Running    ", "ok"), ("Swarm + Jenkins, zero-downtime deploys", "dim")],
        [("cloudcity             ", "value"), ("Building   ", "warn"), ("Kubernetes as a live 3D city", "dim")],
        [("reappkit              ", "value"), ("Building   ", "warn"), ("Fresh Windows PC, one approval, no clicks", "dim")],
        [("event-approval        ", "value"), ("Running    ", "ok"), ("Spring Boot + React approval flow", "dim")],
        [("tubitapp              ", "value"), ("Running    ", "ok"), ("Student club app, Expo + React Native", "dim")],
    ]),
]

THEMES = {
    "dark": {
        "bg": "#0d1117", "bar": "#161b22", "border": "#30363d", "title": "#8b949e",
        "prompt": "#7ee0b5", "cmd": "#e6edf3", "key": "#79c0ff", "value": "#c9d1d9",
        "accent": "#d2a8ff", "dim": "#8b949e", "head": "#8b949e", "ok": "#3fb950",
        "warn": "#d29922", "cursor": "#e6edf3",
    },
    "light": {
        "bg": "#ffffff", "bar": "#f6f8fa", "border": "#d0d7de", "title": "#57606a",
        "prompt": "#1a7f37", "cmd": "#1f2328", "key": "#0969da", "value": "#24292f",
        "accent": "#8250df", "dim": "#6e7781", "head": "#6e7781", "ok": "#1a7f37",
        "warn": "#9a6700", "cursor": "#1f2328",
    },
}

W = 860
PAD_X = 24
TOP = 64           # first line baseline
LINE = 21          # line height
FONT = 14
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"

START = 0.6        # seconds before the first keystroke
TYPE = 0.045       # seconds per character
AFTER_CMD = 0.35   # pause before output
PER_LINE = 0.07    # seconds between output lines
AFTER_OUT = 0.7    # pause before the next prompt


def appear(t: float) -> str:
    return f'<set attributeName="opacity" to="1" begin="{t:.2f}s" fill="freeze"/>'


def render(theme: str) -> str:
    c = THEMES[theme]
    lines = sum(1 + len(out) + 1 for _, out in SESSION) + 1
    h = TOP + lines * LINE + 6
    o: list[str] = []
    add = o.append
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
        f'role="img" aria-label="Terminal: kubectl describe engineer aykut and kubectl get projects">')
    add(f'<style>text{{font-family:{MONO};font-size:{FONT}px;white-space:pre}}'
        f'.cur{{animation:b 1s steps(1) infinite}}@keyframes b{{50%{{opacity:0}}}}</style>')
    add(f'<rect x=".5" y=".5" width="{W - 1}" height="{h - 1}" rx="10" fill="{c["bg"]}" stroke="{c["border"]}"/>')
    add(f'<path d="M.5 36V10.5a10 10 0 0 1 10-10h{W - 21}a10 10 0 0 1 10 10V36z" fill="{c["bar"]}"/>')
    add(f'<line x1="0" y1="36" x2="{W}" y2="36" stroke="{c["border"]}"/>')
    for k, col in enumerate(["#ff5f57", "#febc2e", "#28c840"]):
        add(f'<circle cx="{22 + k * 20}" cy="18" r="6" fill="{col}"/>')
    add(f'<text x="{W / 2}" y="23" text-anchor="middle" fill="{c["title"]}" style="font-size:12px">'
        f'aykut@cloud: ~ — zsh</text>')

    t = START
    y = TOP
    for cmd, out in SESSION:
        add(f'<text x="{PAD_X}" y="{y}" opacity="0">{appear(t - 0.3)}'
            f'<tspan fill="{c["prompt"]}">{escape(PROMPT)}</tspan>'
            + "".join(f'<tspan fill="{c["cmd"]}" opacity="0">{appear(t + i * TYPE)}{escape(ch)}</tspan>'
                      for i, ch in enumerate(cmd))
            + "</text>")
        t += len(cmd) * TYPE + AFTER_CMD
        y += LINE
        for segs in out:
            add(f'<text x="{PAD_X}" y="{y}" opacity="0">{appear(t)}'
                + "".join(f'<tspan fill="{c[role]}">{escape(txt)}</tspan>' for txt, role in segs)
                + "</text>")
            t += PER_LINE
            y += LINE
        t += AFTER_OUT
        y += LINE

    add(f'<text x="{PAD_X}" y="{y}" opacity="0">{appear(t - 0.3)}'
        f'<tspan fill="{c["prompt"]}">{escape(PROMPT)}</tspan></text>')
    cursor_x = PAD_X + len(PROMPT) * FONT * 0.6
    add(f'<g opacity="0">{appear(t)}<rect class="cur" x="{cursor_x:.0f}" y="{y - FONT + 2}" '
        f'width="8" height="{FONT + 2}" fill="{c["cursor"]}"/></g>')
    add("</svg>")
    return "\n".join(o)


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    for theme in THEMES:
        path = OUT_DIR / f"terminal-{theme}.svg"
        path.write_text(render(theme), encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
