#!/usr/bin/env python3
"""Repo Galaxy: turns a GitHub account into two animated SVGs.

  assets/galaxy.svg    - every public repo is a star orbiting your avatar.
                         Orbit radius = age (oldest near the core), size = commits,
                         colour = language, pulsing ring = pushed in the last 30 days.
  assets/heartbeat.svg - last year's contributions drawn as a live ECG trace.

Also refreshes the "recent orbits" block in README.md between markers.
Standard library only. Set GITHUB_TOKEN (or GH_TOKEN) for the API.
"""
import base64
import datetime as dt
import json
import math
import os
import random
import re
import sys
import urllib.error
import urllib.request
from html import escape

USER = os.environ.get("GH_USER", "nhanvu0901")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
NOW = dt.datetime.now(dt.timezone.utc)

LANG_COLORS = {
    "Python": "#3572A5", "TypeScript": "#3178c6", "JavaScript": "#f1e05a",
    "Java": "#b07219", "Vue": "#41b883", "C++": "#f34b7d", "HTML": "#e34c26",
    "PLpgSQL": "#336790", "ShaderLab": "#a379ff", "CSS": "#663399",
    "Go": "#00ADD8", "Rust": "#dea584", "Shell": "#89e051", "C#": "#178600",
    "Dart": "#00B4AB", "Kotlin": "#A97BFF", "Swift": "#F05138",
}
OTHER = "#94a3b8"
FONT = "'Segoe UI', -apple-system, BlinkMacSystemFont, Helvetica, Arial, sans-serif"
MONO = "'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"


# ---------------------------------------------------------------- GitHub API
def request(url, body=None, raw=False):
    if not url.startswith("http"):
        url = "https://api.github.com" + url
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None)
    req.add_header("User-Agent", "repo-galaxy")
    if not raw:
        req.add_header("Accept", "application/vnd.github+json")
    if TOKEN and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
            return (data if raw else json.loads(data)), r.headers
    except urllib.error.HTTPError as e:
        if e.code in (404, 409):  # missing or empty repository
            return None, {}
        raise


def fetch_repos():
    repos, page = [], 1
    while True:
        data, _ = request(f"/users/{USER}/repos?per_page=100&page={page}&type=owner")
        if not data:
            break
        repos += data
        page += 1
    repos = [r for r in repos if not r["fork"] and r["name"].lower() != USER.lower()]
    for r in repos:
        data, headers = request(f"/repos/{USER}/{r['name']}/commits?per_page=1")
        link = headers.get("Link", "") if headers else ""
        m = re.search(r'[?&]page=(\d+)>; rel="last"', link)
        r["commits"] = int(m.group(1)) if m else (len(data) if data else 0)
    repos.sort(key=lambda r: r["created_at"])
    return repos


def fetch_calendar():
    if not TOKEN:
        return []
    q = ('query($u:String!){user(login:$u){contributionsCollection{contributionCalendar'
         '{totalContributions weeks{contributionDays{date contributionCount}}}}}}')
    data, _ = request("https://api.github.com/graphql", {"query": q, "variables": {"u": USER}})
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return [[(d["date"], d["contributionCount"]) for d in w["contributionDays"]] for w in cal["weeks"]]


def fetch_avatar():
    try:
        user, _ = request(f"/users/{USER}")
        img, _ = request(user["avatar_url"] + "&s=120", raw=True)
        mime = "image/png" if img[:4] == b"\x89PNG" else "image/jpeg"
        return f"data:{mime};base64," + base64.b64encode(img).decode()
    except Exception:
        return None


# ---------------------------------------------------------------- helpers
def f(x):
    return f"{x:.1f}".rstrip("0").rstrip(".")


def days_since(iso):
    return (NOW - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).days


def lang_color(lang):
    return LANG_COLORS.get(lang or "", OTHER)


# ---------------------------------------------------------------- galaxy.svg
def galaxy_svg(repos, avatar):
    W, H, CX, CY = 900, 540, 450, 280
    TILT = 0.4
    rnd = random.Random(USER)
    n = max(len(repos), 1)
    total_commits = sum(r["commits"] for r in repos)
    first_year = int(repos[0]["created_at"][:4]) if repos else NOW.year

    langs = {}
    for r in repos:
        langs[r["language"] or "Other"] = langs.get(r["language"] or "Other", 0) + 1
    top_langs = sorted(langs.items(), key=lambda kv: -kv[1])[:6]

    by_commits = sorted(repos, key=lambda r: -r["commits"])
    labelled = {r["name"] for r in by_commits[:7]}
    labelled |= {r["name"] for r in repos if days_since(r["pushed_at"]) <= 30}

    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
      f'viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">')
    a(f'<title id="t">{USER} repo galaxy</title>')
    a(f'<desc id="d">{len(repos)} repositories orbiting as stars; orbit radius is age, '
      f'size is commit count, colour is language.</desc>')

    # defs
    a('<defs>')
    a('<radialGradient id="bg" cx="50%" cy="52%" r="75%">'
      '<stop offset="0" stop-color="#1a1440"/><stop offset=".45" stop-color="#0b0f2a"/>'
      '<stop offset="1" stop-color="#03040c"/></radialGradient>')
    a('<radialGradient id="core" cx="50%" cy="50%" r="50%">'
      '<stop offset="0" stop-color="#fff7d6" stop-opacity=".95"/>'
      '<stop offset=".25" stop-color="#ffb86b" stop-opacity=".55"/>'
      '<stop offset=".6" stop-color="#a855f7" stop-opacity=".18"/>'
      '<stop offset="1" stop-color="#a855f7" stop-opacity="0"/></radialGradient>')
    for i, (lang, _) in enumerate(list(langs.items())):
        c = lang_color(None if lang == "Other" else lang)
        a(f'<radialGradient id="s{i}"><stop offset="0" stop-color="#fff"/>'
          f'<stop offset=".28" stop-color="{c}"/><stop offset=".55" stop-color="{c}" stop-opacity=".35"/>'
          f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')
    a('<linearGradient id="tail" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
      '<stop offset="1" stop-color="#fff" stop-opacity=".9"/></linearGradient>')
    a('<filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="38"/></filter>')
    a(f'<clipPath id="av"><circle cx="{CX}" cy="{CY}" r="26"/></clipPath>')
    a(f'<clipPath id="frame"><rect width="{W}" height="{H}" rx="18"/></clipPath>')
    a('</defs>')
    grad_id = {lang: f"s{i}" for i, lang in enumerate(langs)}

    a('<style>'
      '.tw{animation:tw 4s ease-in-out infinite}'
      '@keyframes tw{0%,100%{opacity:.15}50%{opacity:1}}'
      '.st{animation:st 3.2s ease-in-out infinite}'
      '@keyframes st{0%,100%{opacity:.75}50%{opacity:1}}'
      '.pulse{transform-box:fill-box;transform-origin:center;animation:pulse 2.6s ease-out infinite}'
      '@keyframes pulse{0%{transform:scale(.5);opacity:.95}100%{transform:scale(3.2);opacity:0}}'
      '.halo{transform-box:fill-box;transform-origin:center;animation:halo 6s ease-in-out infinite}'
      '@keyframes halo{0%,100%{transform:scale(1);opacity:.85}50%{transform:scale(1.12);opacity:1}}'
      '.neb{transform-box:view-box;transform-origin:50% 52%;animation:neb 90s linear infinite}'
      '@keyframes neb{to{transform:rotate(360deg)}}'
      '.comet{animation:comet 11s linear infinite;opacity:0}'
      '@keyframes comet{0%{transform:translate(0,0);opacity:0}2%{opacity:1}'
      '14%{transform:translate(760px,250px);opacity:0}100%{transform:translate(760px,250px);opacity:0}}'
      '.lbl{font:600 10.5px ' + FONT + ';fill:#e2e8f0;paint-order:stroke;stroke:#05060f;stroke-width:3px}'
      '.ring{fill:none;stroke:#c4b5fd;stroke-opacity:.09;stroke-dasharray:2 5}'
      '.yr{font:10px ' + MONO + ';fill:#a5b4fc;fill-opacity:.45}'
      '.hud{font:11px ' + MONO + ';fill:#94a3b8}'
      '.big{font:700 15px ' + MONO + ';fill:#f8fafc;letter-spacing:3px}'
      '</style>')

    a('<g clip-path="url(#frame)">')
    a(f'<rect width="{W}" height="{H}" fill="url(#bg)"/>')

    # nebula clouds (slow rotation)
    a('<g class="neb" filter="url(#blur)" opacity=".55">')
    a(f'<ellipse cx="{CX-170}" cy="{CY-60}" rx="190" ry="70" fill="#7c3aed" opacity=".35"/>')
    a(f'<ellipse cx="{CX+190}" cy="{CY+70}" rx="210" ry="80" fill="#0ea5e9" opacity=".25"/>')
    a(f'<ellipse cx="{CX+40}" cy="{CY-120}" rx="140" ry="50" fill="#ec4899" opacity=".18"/>')
    a('</g>')

    # background star field
    for _ in range(170):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.choice([.5, .6, .7, .9, 1.1, 1.4])
        a(f'<circle class="tw" cx="{f(x)}" cy="{f(y)}" r="{r}" fill="#fff" '
          f'style="animation-delay:-{f(rnd.uniform(0, 4))}s;animation-duration:{f(rnd.uniform(2.5, 6))}s"/>')

    # comets
    for i in range(3):
        sx, sy = rnd.uniform(-120, 300), rnd.uniform(-40, 140)
        a(f'<g transform="translate({f(sx)} {f(sy)}) rotate(18)"><g class="comet" style="animation-delay:{i * 3.7 + 1:.1f}s">'
          f'<rect x="-90" y="-1" width="90" height="2" rx="1" fill="url(#tail)"/>'
          f'<circle r="1.8" fill="#fff"/></g></g>')

    # radius per repo: oldest close to the core, newest on the rim
    def radius(i):
        t = i / (n - 1) if n > 1 else 0
        return 62 + (t ** 0.85) * 335

    # year rings
    seen, placed = set(), []
    for i, r in enumerate(repos):
        y = r["created_at"][:4]
        if y in seen:
            continue
        seen.add(y)
        rx = radius(i) - 4
        a(f'<ellipse class="ring" cx="{CX}" cy="{CY}" rx="{f(rx)}" ry="{f(rx * TILT)}"/>')
        # spread labels around the ring so close rings don't collide
        for ang in (0.62, 0.95, 1.25, 0.35, 2.5, 2.2):
            lx = CX + rx * math.cos(ang)
            ly = CY + rx * TILT * math.sin(ang) + 11
            if all(abs(lx - px) > 34 or abs(ly - py) > 13 for px, py in placed):
                placed.append((lx, ly))
                a(f'<text class="yr" x="{f(lx)}" y="{f(ly)}">{y}</text>')
                break

    # galactic core + avatar
    a(f'<circle class="halo" cx="{CX}" cy="{CY}" r="95" fill="url(#core)"/>')
    if avatar:
        a(f'<image href="{avatar}" x="{CX - 26}" y="{CY - 26}" width="52" height="52" clip-path="url(#av)"/>')
        a(f'<circle cx="{CX}" cy="{CY}" r="26.5" fill="none" stroke="#fde68a" stroke-opacity=".7" stroke-width="1.5"/>')

    # stars (repos) on elliptical orbits, inner ones faster
    golden = math.pi * (3 - math.sqrt(5))
    for i, r in enumerate(repos):
        rx = radius(i)
        ry = rx * TILT
        theta = i * golden * 2.2
        x0, y0 = CX + rx * math.cos(theta), CY + ry * math.sin(theta)
        x1, y1 = CX - rx * math.cos(theta), CY - ry * math.sin(theta)
        path = (f"M{f(x0)} {f(y0)}A{f(rx)} {f(ry)} 0 1 1 {f(x1)} {f(y1)}"
                f"A{f(rx)} {f(ry)} 0 1 1 {f(x0)} {f(y0)}")
        period = 26 * (rx / 62) ** 1.5  # Kepler-ish
        size = 1.6 + 1.25 * math.log1p(r["commits"])
        lang = r["language"] or "Other"
        color = lang_color(r["language"])
        recent = days_since(r["pushed_at"]) <= 30
        a(f'<g><animateMotion dur="{f(period)}s" repeatCount="indefinite" path="{path}"/>')
        if recent:
            a(f'<circle class="pulse" r="{f(size * 1.4)}" fill="none" stroke="{color}" stroke-width="1.4"/>')
        a(f'<circle class="st" r="{f(size * 2.6)}" fill="url(#{grad_id[lang]})" '
          f'style="animation-delay:-{f(rnd.uniform(0, 3))}s"/>')
        if r["name"] in labelled:
            a(f'<text class="lbl" x="{f(size + 5)}" y="3.5">{escape(r["name"])}</text>')
        a('</g>')

    # HUD
    a(f'<text class="big" x="28" y="40">{escape(USER.upper())}</text>')
    a(f'<text class="hud" x="28" y="60">// repo galaxy · radius = age · size = commits</text>')
    a(f'<text class="hud" x="{W - 28}" y="40" text-anchor="end">sync {NOW:%Y-%m-%d}</text>')
    years = NOW.year - first_year
    a(f'<text class="hud" x="28" y="{H - 26}"><tspan fill="#f8fafc" font-weight="700">{len(repos)}</tspan> stars · '
      f'<tspan fill="#f8fafc" font-weight="700">{total_commits:,}</tspan> commits · '
      f'<tspan fill="#f8fafc" font-weight="700">{years}</tspan> years in orbit · '
      f'<tspan fill="#fbbf24">◉</tspan> pulsing = active this month</text>')
    x = W - 28
    for lang, _ in reversed(top_langs):
        w = len(lang) * 6.6 + 22
        x -= w
        a(f'<circle cx="{f(x + 5)}" cy="56" r="4" fill="{lang_color(None if lang == "Other" else lang)}"/>')
        a(f'<text class="hud" x="{f(x + 13)}" y="60">{escape(lang)}</text>')

    a(f'<rect width="{W}" height="{H}" rx="18" fill="none" stroke="#a78bfa" stroke-opacity=".25"/>')
    a('</g></svg>')
    return "\n".join(out)


# ---------------------------------------------------------------- heartbeat.svg
def heartbeat_svg(weeks):
    W, H, B = 900, 190, 122
    days = [d for w in weeks for d in w]
    total = sum(c for _, c in days)
    best = max(days, key=lambda d: d[1]) if days else ("-", 0)
    longest = cur = 0
    for _, c in days:
        cur = cur + 1 if c else 0
        longest = max(longest, cur)
    current = 0
    for _, c in reversed(days):
        if not c:
            if current == 0 and _ == days[-1][0]:
                continue  # today may still be empty
            break
        current += 1

    x0, x1 = 28, W - 28
    step = (x1 - x0) / max(len(weeks), 1)
    pts = [(x0, B)]
    for i, w in enumerate(weeks):
        c = sum(cnt for _, cnt in w)
        amp = min(50, 6.5 * math.sqrt(c))
        x = x0 + i * step
        if amp < 1:
            pts.append((x + step, B))
            continue
        pts += [(x + step * .30, B), (x + step * .40, B + 3), (x + step * .52, B - amp),
                (x + step * .64, B + amp * .32), (x + step * .74, B), (x + step, B)]
    d = "M" + " L".join(f"{f(x)} {f(y)}" for x, y in pts)

    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'role="img" aria-labelledby="t2"><title id="t2">{total} contributions in the last year, drawn as a heartbeat</title>')
    a('<defs><linearGradient id="ecg" x1="0" x2="1"><stop offset="0" stop-color="#22d3ee"/>'
      '<stop offset=".55" stop-color="#a78bfa"/><stop offset="1" stop-color="#f472b6"/></linearGradient>'
      '<filter id="glow" x="-10%" y="-50%" width="120%" height="200%"><feGaussianBlur stdDeviation="3.5"/></filter>'
      '<pattern id="grid" width="18" height="18" patternUnits="userSpaceOnUse">'
      '<path d="M18 0H0V18" fill="none" stroke="#22d3ee" stroke-opacity=".07"/></pattern>'
      f'<clipPath id="fr2"><rect width="{W}" height="{H}" rx="18"/></clipPath></defs>')
    a('<style>'
      '.trace{stroke-dasharray:1000;stroke-dashoffset:1000;animation:draw 9s cubic-bezier(.4,0,.2,1) infinite}'
      '@keyframes draw{0%{stroke-dashoffset:1000;opacity:1}70%{stroke-dashoffset:0;opacity:1}'
      '90%{stroke-dashoffset:0;opacity:1}100%{stroke-dashoffset:0;opacity:0}}'
      '.hud{font:11px ' + MONO + ';fill:#94a3b8}'
      '.num{font:700 20px ' + MONO + ';fill:#f8fafc}'
      '.mo{font:9.5px ' + MONO + ';fill:#64748b}'
      '.blink{animation:blink 1.1s steps(2) infinite}@keyframes blink{50%{opacity:0}}'
      '</style>')
    a(f'<g clip-path="url(#fr2)"><rect width="{W}" height="{H}" fill="#060914"/>'
      f'<rect width="{W}" height="{H}" fill="url(#grid)"/>')
    a(f'<line x1="{x0}" x2="{x1}" y1="{B}" y2="{B}" stroke="#22d3ee" stroke-opacity=".12"/>')

    # month ticks
    last = None
    for i, w in enumerate(weeks):
        m = w[0][0][:7]
        if m != last and i:
            month = dt.date.fromisoformat(w[0][0]).strftime("%b")
            a(f'<text class="mo" x="{f(x0 + i * step)}" y="{H - 14}">{month}</text>')
        last = m

    a(f'<path class="trace" d="{d}" pathLength="1000" fill="none" stroke="url(#ecg)" stroke-width="6" '
      f'stroke-opacity=".55" filter="url(#glow)" stroke-linejoin="round"/>')
    a(f'<path class="trace" d="{d}" pathLength="1000" fill="none" stroke="url(#ecg)" stroke-width="1.8" '
      f'stroke-linejoin="round" stroke-linecap="round"/>')
    a('<circle r="3.2" fill="#fff"><animateMotion dur="9s" repeatCount="indefinite" '
      f'keyPoints="0;1;1;1" keyTimes="0;.7;.9;1" calcMode="spline" keySplines=".4 0 .2 1;0 0 1 1;0 0 1 1" path="{d}"/>'
      '<animate attributeName="opacity" values="1;1;1;0" keyTimes="0;.7;.9;1" dur="9s" repeatCount="indefinite"/></circle>')

    a(f'<text class="hud" x="28" y="30"><tspan class="blink" fill="#f472b6">●</tspan> LIVE · commit heartbeat · last 12 months</text>')
    stats = [(f"{total:,}", "contributions"), (f"{longest}d", "longest streak"),
             (f"{current}d", "current streak"), (f"{best[1]}", f"best day {best[0][5:]}")]
    x = W - 28
    for val, label in reversed(stats):
        a(f'<text class="num" x="{x}" y="34" text-anchor="end">{val}</text>')
        a(f'<text class="hud" x="{x}" y="50" text-anchor="end">{escape(label)}</text>')
        x -= 128
    a(f'<rect width="{W}" height="{H}" rx="18" fill="none" stroke="#22d3ee" stroke-opacity=".2"/></g></svg>')
    return "\n".join(out)


# ---------------------------------------------------------------- README block
def update_readme(repos):
    path = os.path.join(ROOT, "README.md")
    if not os.path.exists(path):
        return
    recent = sorted(repos, key=lambda r: r["pushed_at"], reverse=True)[:5]
    rows = ["| | repo | language | commits | last signal |", "|---|---|---|---|---|"]
    for r in recent:
        days = days_since(r["pushed_at"])
        when = "today" if days == 0 else f"{days}d ago"
        dot = "🟢" if days <= 7 else "🟡" if days <= 30 else "⚪"
        rows.append(f"| {dot} | [**{r['name']}**]({r['html_url']}) | {r['language'] or '—'} | "
                    f"{r['commits']} | {when} |")
    block = "\n".join(rows)
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"(<!--RECENT:START-->).*?(<!--RECENT:END-->)",
                  lambda m: f"{m.group(1)}\n{block}\n{m.group(2)}", text, flags=re.S)
    open(path, "w", encoding="utf-8").write(text)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    repos = fetch_repos()
    print(f"{len(repos)} repos, {sum(r['commits'] for r in repos)} commits", file=sys.stderr)
    with open(os.path.join(ASSETS, "galaxy.svg"), "w", encoding="utf-8") as fh:
        fh.write(galaxy_svg(repos, fetch_avatar()))
    weeks = fetch_calendar()
    if weeks:
        with open(os.path.join(ASSETS, "heartbeat.svg"), "w", encoding="utf-8") as fh:
            fh.write(heartbeat_svg(weeks))
    update_readme(repos)


if __name__ == "__main__":
    main()
