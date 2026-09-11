"""
Pulls real numbers from the GitHub API and draws the 4 radar charts.
Three of the four charts (Languages, Git Activity, Consistency) use real
data fetched here. The fourth (Skills) stays a manual self-rating, since
things like "frontend" vs "backend" aren't something GitHub tracks - that
one is clearly labeled so it doesn't pretend to be measured data.
"""
import os
import math
import requests

TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ["USERNAME"]

HEADERS = {"Authorization": f"bearer {TOKEN}"}


def graphql(query, variables=None):
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def get_contribution_data():
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          totalPullRequestReviewContributions
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays { contributionCount }
            }
          }
        }
        repositories(first: 100, ownerAffiliations: OWNER) {
          totalCount
        }
      }
    }
    """
    data = graphql(query, {"login": USERNAME})["user"]
    cc = data["contributionsCollection"]

    days = [d["contributionCount"] for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    active_days = sum(1 for d in days if d > 0)

    # current streak: count backwards from the most recent day
    current_streak = 0
    for d in reversed(days):
        if d > 0:
            current_streak += 1
        else:
            break

    # best streak: longest run of consecutive active days anywhere in the calendar
    best_streak = 0
    running = 0
    for d in days:
        if d > 0:
            running += 1
            best_streak = max(best_streak, running)
        else:
            running = 0

    return {
        "commits": cc["totalCommitContributions"],
        "pull_requests": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "reviews": cc["totalPullRequestReviewContributions"],
        "repos": data["repositories"]["totalCount"],
        "total_contributions": cc["contributionCalendar"]["totalContributions"],
        "current_streak": current_streak,
        "best_streak": best_streak,
        "active_days": active_days,
    }


def get_language_breakdown():
    resp = requests.get(
        f"https://api.github.com/users/{USERNAME}/repos?per_page=100",
        headers={"Authorization": f"token {TOKEN}"},
    )
    resp.raise_for_status()
    repos = resp.json()

    totals = {}
    for repo in repos:
        lang_resp = requests.get(repo["languages_url"], headers={"Authorization": f"token {TOKEN}"})
        if lang_resp.status_code != 200:
            continue
        for lang, byte_count in lang_resp.json().items():
            totals[lang] = totals.get(lang, 0) + byte_count

    top5 = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return top5


def normalize(values):
    """Scale a list of raw numbers to 0-1 range based on the largest value in the set."""
    if not values:
        return []
    max_val = max(values) or 1
    return [v / max_val for v in values]


def point_on_axis(cx, cy, angle_deg, distance):
    angle_rad = math.pi / 180 * angle_deg
    return cx + distance * math.cos(angle_rad), cy + distance * math.sin(angle_rad)


def pentagon_angles(start=-90):
    return [start + i * 72 for i in range(5)]


def draw_radar(cx, cy, max_radius, axes, title, note=None):
    parts = []
    angles = pentagon_angles()
    parts.append(f'<text x="{cx}" y="{cy - max_radius - 55}" font-family="Fira Code, monospace" font-size="20" '
                 f'fill="#e6edf3" text-anchor="middle" font-weight="bold">{title}</text>')
    if note:
        parts.append(f'<text x="{cx}" y="{cy - max_radius - 32}" font-family="Fira Code, monospace" font-size="11" '
                     f'fill="#6b6b6b" text-anchor="middle" font-style="italic">{note}</text>')

    for ring_fraction in [0.25, 0.5, 0.75, 1.0]:
        pts = [f"{x:.1f},{y:.1f}" for x, y in (point_on_axis(cx, cy, a, max_radius * ring_fraction) for a in angles)]
        parts.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#e3b341" stroke-width="1" opacity="0.25"/>')

    for angle in angles:
        x, y = point_on_axis(cx, cy, angle, max_radius)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#e3b341" stroke-width="1" opacity="0.25"/>')

    filled_pts = [f"{x:.1f},{y:.1f}" for (label, level), angle in zip(axes, angles)
                  for x, y in [point_on_axis(cx, cy, angle, max_radius * level)]]
    parts.append(f'<polygon points="{" ".join(filled_pts)}" fill="#39D353" fill-opacity="0.45" stroke="#e3b341" stroke-width="3">')
    parts.append('<animate attributeName="fill-opacity" values="0.45;0.65;0.45" dur="3s" repeatCount="indefinite"/>')
    parts.append('</polygon>')

    for (label, level), angle in zip(axes, angles):
        x, y = point_on_axis(cx, cy, angle, max_radius * level)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#e3b341"/>')

    for (label, level), angle in zip(axes, angles):
        x, y = point_on_axis(cx, cy, angle, max_radius + 30)
        anchor = "start" if angle == 0 else "end" if angle == 180 else "middle"
        parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="Fira Code, monospace" font-size="13" '
                     f'fill="#8b949e" text-anchor="{anchor}" dominant-baseline="middle">{label}</text>')

    return "\n".join(parts)


def main():
    contrib = get_contribution_data()
    languages = get_language_breakdown()

    lang_names = [name for name, _ in languages] or ["N/A"] * 5
    lang_levels = normalize([count for _, count in languages]) or [0] * 5
    while len(lang_names) < 5:
        lang_names.append("-")
        lang_levels.append(0)

    git_activity_raw = [contrib["commits"], contrib["pull_requests"], contrib["issues"], contrib["reviews"], contrib["repos"]]
    git_activity_levels = normalize(git_activity_raw)

    consistency_raw = [contrib["current_streak"], contrib["best_streak"], contrib["total_contributions"],
                        contrib["active_days"], contrib["repos"]]
    consistency_levels = normalize(consistency_raw)

    charts = [
        {
            "title": "Languages", "cx": 220, "cy": 260, "note": "real data, top 5 by bytes",
            "axes": list(zip(lang_names, lang_levels)),
        },
        {
            "title": "Git Activity", "cx": 660, "cy": 260, "note": "real data, this year",
            "axes": list(zip(["Commits", "Pull Requests", "Issues", "Reviews", "Repos"], git_activity_levels)),
        },
        {
            "title": "Skills", "cx": 1100, "cy": 260, "note": "self-rated, not measured",
            "axes": [("Frontend", 0.8), ("Backend", 0.5), ("AI & Automation", 0.65), ("Design", 0.4), ("Systems", 0.45)],
        },
        {
            "title": "Consistency", "cx": 1540, "cy": 260, "note": "real data",
            "axes": list(zip(["Current Streak", "Best Streak", "Contributions", "Active Days", "Repos"], consistency_levels)),
        },
    ]

    max_radius = 110
    parts = ['<svg viewBox="0 0 1760 480" xmlns="http://www.w3.org/2000/svg">',
             '<!-- radar charts: Languages, Git Activity, Consistency use real data from the GitHub API. Skills is a manual self-rating, labeled as such. -->']
    for chart in charts:
        parts.append(draw_radar(chart["cx"], chart["cy"], max_radius, chart["axes"], chart["title"], chart.get("note")))
    parts.append("</svg>")

    with open("hex-stats.svg", "w") as f:
        f.write("\n".join(parts))

    print("wrote hex-stats.svg with real data")


if __name__ == "__main__":
    main()
