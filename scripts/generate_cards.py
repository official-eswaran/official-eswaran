#!/usr/bin/env python3
"""Render the profile stat cards as SVGs committed to this repo.

Third-party widget services (github-readme-stats, github-profile-trophy) are
shared instances that rate-limit and run out of quota — they were returning 503
and 402 on this profile. These cards are generated from the GitHub API and
committed here instead, so they always render.

Run:  GITHUB_TOKEN=... python scripts/generate_cards.py
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER = "official-eswaran"
API = "https://api.github.com"
OUT = Path(__file__).resolve().parent.parent / "assets"

BG = "#0D1117"
BORDER = "#21262D"
ACCENT = "#22D3EE"
TEXT = "#C9D1D9"
MUTED = "#8B949E"

# Brand colours for the languages that actually appear in these repos.
LANG_COLORS = {
    "Python": "#3572A5",
    "JavaScript": "#F1E05A",
    "Kotlin": "#A97BFF",
    "Jupyter Notebook": "#DA5B0B",
    "CSS": "#663399",
    "Shell": "#89E051",
    "HCL": "#844FBA",
    "Dockerfile": "#384D54",
    "HTML": "#E34C26",
    "Mako": "#7E858D",
    "TypeScript": "#3178C6",
    "Java": "#B07219",
    "C++": "#F34B7D",
}
FALLBACK = "#6E7681"

FONT = (
    "-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif"
)

# Both cards render at the same height so they line up side by side in the README.
CARD_H = 278

# Long names collide with the percentage column in the two-up legend.
SHORT_NAMES = {"Jupyter Notebook": "Jupyter"}


def api(path: str) -> tuple[object, dict[str, str]]:
    req = urllib.request.Request(f"{API}{path}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", f"{USER}-profile-cards")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode()), dict(r.headers)


def commit_count(repo: str) -> int:
    """Total commits, read off the pagination Link header."""
    try:
        body, headers = api(f"/repos/{USER}/{repo}/commits?per_page=1")
    except Exception:
        return 0
    link = headers.get("Link", "")
    match = re.search(r'[?&]page=(\d+)>; rel="last"', link)
    if match:
        return int(match.group(1))
    return len(body) if isinstance(body, list) else 0


def collect() -> dict:
    user, _ = api(f"/users/{USER}")
    repos, _ = api(f"/users/{USER}/repos?per_page=100&type=owner")
    repos = [r for r in repos if not r["fork"]]

    languages: dict[str, int] = {}
    stars = commits = 0
    for repo in repos:
        stars += repo["stargazers_count"]
        commits += commit_count(repo["name"])
        langs, _ = api(f"/repos/{USER}/{repo['name']}/languages")
        for name, size in langs.items():
            languages[name] = languages.get(name, 0) + size

    prs, _ = api(f"/search/issues?q=author:{USER}+type:pr&per_page=1")
    issues, _ = api(f"/search/issues?q=author:{USER}+type:issue&per_page=1")

    return {
        "repos": len(repos),
        "stars": stars,
        "commits": commits,
        "followers": user["followers"],
        "prs": prs.get("total_count", 0),
        "issues": issues.get("total_count", 0),
        "languages": dict(
            sorted(languages.items(), key=lambda kv: kv[1], reverse=True)
        ),
    }


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def stats_card(d: dict) -> str:
    rows = [
        ("Public repositories", d["repos"]),
        ("Total commits", d["commits"]),
        ("Pull requests", d["prs"]),
        ("Issues opened", d["issues"]),
        ("Stars earned", d["stars"]),
        ("Followers", d["followers"]),
    ]
    w, pad, top, step, h = 440, 28, 78, 30, CARD_H

    body = []
    for i, (label, value) in enumerate(rows):
        y = top + i * step
        body.append(
            f'<text x="{pad}" y="{y}" fill="{TEXT}" font-size="14" '
            f'font-family="{FONT}" style="animation:fade .5s ease {0.1 + i * .08}s both">{esc(label)}</text>'
            f'<text x="{w - pad}" y="{y}" fill="{ACCENT}" font-size="15" font-weight="700" '
            f'text-anchor="end" font-family="{FONT}" '
            f'style="animation:fade .5s ease {0.1 + i * .08}s both">{value}</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="GitHub statistics">
  <style>@keyframes fade{{from{{opacity:0;transform:translateX(-6px)}}to{{opacity:1;transform:translateX(0)}}}}</style>
  <rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="10" fill="{BG}" stroke="{BORDER}"/>
  <text x="{pad}" y="38" fill="{ACCENT}" font-size="17" font-weight="700" font-family="{FONT}">GitHub Statistics</text>
  <line x1="{pad}" y1="52" x2="{w - pad}" y2="52" stroke="{BORDER}"/>
  {"".join(body)}
</svg>
"""


def languages_card(d: dict) -> str:
    langs = list(d["languages"].items())
    total = sum(v for _, v in langs) or 1
    shown = langs[:8]

    w, pad, bar_y, bar_h, h = 460, 28, 88, 12, CARD_H
    bar_w = w - pad * 2
    cols = 2
    col_w = bar_w / cols

    segments, legend, x = [], [], float(pad)
    for i, (name, size) in enumerate(shown):
        frac = size / total
        seg_w = max(frac * bar_w, 2.0)
        color = LANG_COLORS.get(name, FALLBACK)
        segments.append(
            f'<rect x="{x:.2f}" y="{bar_y}" width="{seg_w:.2f}" height="{bar_h}" fill="{color}"/>'
        )
        x += seg_w

        col, row = i % cols, i // cols
        lx = pad + col * col_w
        ly = bar_y + bar_h + 36 + row * 30
        label = SHORT_NAMES.get(name, name)
        legend.append(
            f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{color}"/>'
            f'<text x="{lx + 18}" y="{ly}" fill="{TEXT}" font-size="12.5" font-family="{FONT}">{esc(label)}</text>'
            f'<text x="{lx + col_w - 20}" y="{ly}" fill="{MUTED}" font-size="12.5" '
            f'text-anchor="end" font-family="{FONT}">{frac * 100:.1f}%</text>'
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Most used languages">
  <rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="10" fill="{BG}" stroke="{BORDER}"/>
  <text x="{pad}" y="38" fill="{ACCENT}" font-size="17" font-weight="700" font-family="{FONT}">Most Used Languages</text>
  <line x1="{pad}" y1="52" x2="{w - pad}" y2="52" stroke="{BORDER}"/>
  <clipPath id="r"><rect x="{pad}" y="{bar_y}" width="{bar_w}" height="{bar_h}" rx="5"/></clipPath>
  <g clip-path="url(#r)">{"".join(segments)}</g>
  {"".join(legend)}
</svg>
"""


def main() -> None:
    data = collect()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stats.svg").write_text(stats_card(data), encoding="utf-8")
    (OUT / "languages.svg").write_text(languages_card(data), encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (OUT / "generated.txt").write_text(f"{stamp}\n", encoding="utf-8")
    print(f"generated at {stamp}")
    print(json.dumps({k: v for k, v in data.items() if k != "languages"}, indent=2))
    print(json.dumps(data["languages"], indent=2))


if __name__ == "__main__":
    main()
