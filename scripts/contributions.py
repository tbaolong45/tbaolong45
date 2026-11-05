"""Render the last 30 days of GitHub contributions as light and dark SVG bar charts.

Usage: GITHUB_TOKEN=... python3 contributions.py <user> <out_dir>
       python3 contributions.py --demo   (self-check, no network)
"""
import json
import os
import sys
import urllib.request
from datetime import date, timedelta

DAYS = 30
W, H = 700, 190
LEFT, TOP, BASE = 16, 52, 158  # plot starts at LEFT, bars grow up from BASE to TOP
STEP, BAR = (W - 2 * LEFT) / DAYS, 16
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
# file -> (bar, title ink, label ink, baseline); bar colours pass the 3:1 contrast
# check against GitHub's light (#ffffff) and dark (#0d1117) page backgrounds.
THEMES = {
    "contributions.svg": ("#6250d6", "#1f2328", "#59636e", "#d1d9e0"),
    "contributions-dark.svg": ("#9085e9", "#f0f6fc", "#9198a1", "#3d444d"),
}
QUERY = (
    "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar"
    "{weeks{contributionDays{date contributionCount}}}}}}"
)


def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"u": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-contributions"},
    )
    body = json.load(urllib.request.urlopen(req, timeout=30))
    if body.get("errors") or not body.get("data", {}).get("user"):
        sys.exit(f"GitHub API error: {body.get('errors') or 'user not found'}")
    weeks = body["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]]
    return days[-DAYS:]


def label(iso):
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}"


def render(days, bar, ink, muted, line):
    total = sum(c for _, c in days)
    peak = max(c for _, c in days)
    peak_i = next(i for i, (_, c) in enumerate(days) if c == peak)
    summary = f"Daily contributions, last {len(days)} days: {total} in total"
    if peak:
        summary += f", most on {label(days[peak_i][0])} ({peak})"
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'role="img" font-family="{FONT}"><title>{summary}</title>',
        f'<text x="{LEFT}" y="20" font-size="14" font-weight="600" fill="{ink}">Daily contributions</text>',
        f'<text x="{W - LEFT}" y="20" font-size="12" fill="{muted}" text-anchor="end">'
        f"{total} in the last {len(days)} days</text>",
        f'<line x1="{LEFT}" x2="{W - LEFT}" y1="{BASE + 0.5}" y2="{BASE + 0.5}" stroke="{line}"/>',
    ]
    for i, (iso, count) in enumerate(days):
        x = LEFT + i * STEP + (STEP - BAR) / 2
        mid = x + BAR / 2
        if count:
            y = BASE - max(3, (BASE - TOP) * count / peak)  # 3px floor keeps a 1-commit day visible
            r = min(4, BASE - y)
            out.append(
                f'<path fill="{bar}" d="M{x:.1f} {BASE}V{y + r:.1f}Q{x:.1f} {y:.1f} {x + r:.1f} {y:.1f}'
                f'H{x + BAR - r:.1f}Q{x + BAR:.1f} {y:.1f} {x + BAR:.1f} {y + r:.1f}V{BASE}Z"/>'
            )
            if i == peak_i:  # label the tallest bar only; it gives the scale
                out.append(
                    f'<text x="{mid:.1f}" y="{y - 6:.1f}" font-size="12" font-weight="600" '
                    f'fill="{ink}" text-anchor="middle">{count}</text>'
                )
        if (len(days) - 1 - i) % 7 == 0:  # a date under every 7th day, counting back from today
            out.append(
                f'<text x="{mid:.1f}" y="{BASE + 18}" font-size="12" fill="{muted}" '
                f'text-anchor="middle">{label(iso)}</text>'
            )
    return "".join(out) + "</svg>\n"


def write_all(days, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for name, colours in THEMES.items():
        with open(os.path.join(out_dir, name), "w") as f:
            f.write(render(days, *colours))


def demo():
    start = date(2026, 1, 1)
    days = [((start + timedelta(i)).isoformat(), [0, 3, 1, 12, 0, 7][i % 6]) for i in range(DAYS)]
    svg = render(days, *THEMES["contributions.svg"])
    assert svg.count("<path") == sum(1 for _, c in days if c), "one bar per active day"
    assert ">12</text>" in svg and "115 in the last 30 days" in svg
    empty = render([(d, 0) for d, _ in days], *THEMES["contributions.svg"])
    assert "<path" not in empty, "no bars when there are no contributions"
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--demo"]:
        demo()
    else:
        user, out_dir = sys.argv[1:3]
        write_all(fetch(user, os.environ["GITHUB_TOKEN"]), out_dir)
