"""
Draws the real GitHub contribution grid (same layout as the calendar on your
profile: 7 rows, one column per week, colored by contribution count). A handful
of the actual cells take turns launching upward and shattering into smaller
squares of the same color, then the cycle repeats forever.
"""
import os
import random
import requests

TOKEN = os.environ["GITHUB_TOKEN"]
USERNAME = os.environ["USERNAME"]
HEADERS = {"Authorization": f"bearer {TOKEN}"}

CELL = 11
GAP = 3
COLORS = {
    0: "#161b22",
    1: "#0e4429",
    2: "#006d32",
    3: "#26a641",
    4: "#39d353",
}


def graphql(query, variables=None):
    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def get_calendar():
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays { contributionCount, color, weekday }
            }
          }
        }
      }
    }
    """
    data = graphql(query, {"login": USERNAME})["user"]
    return data["contributionsCollection"]["contributionCalendar"]["weeks"]


def level_from_count(count, max_count):
    if count == 0 or max_count == 0:
        return 0
    ratio = count / max_count
    if ratio > 0.75:
        return 4
    if ratio > 0.5:
        return 3
    if ratio > 0.25:
        return 2
    return 1


def main():
    weeks = get_calendar()
    all_counts = [d["contributionCount"] for w in weeks for d in w["contributionDays"]]
    max_count = max(all_counts) if all_counts else 1

    grid_w = len(weeks) * (CELL + GAP)
    grid_h = 7 * (CELL + GAP)
    margin = 40
    width = grid_w + margin * 2
    height = grid_h + margin * 2

    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">']
    parts.append('<!-- real contribution grid - a few cells take turns launching up and shattering into fragments -->')

    cells = []  # (x, y, color) for every real cell, used both to draw the grid and to pick which ones burst
    for week_i, week in enumerate(weeks):
        for day in week["contributionDays"]:
            x = margin + week_i * (CELL + GAP)
            y = margin + day["weekday"] * (CELL + GAP)
            level = level_from_count(day["contributionCount"], max_count)
            color = COLORS[level]
            cells.append((x, y, color, day["contributionCount"]))

    # draw the static grid first
    for x, y, color, count in cells:
        parts.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}"/>')

    # pick some cells with real contributions to be the ones that launch and burst,
    # favoring the more active days so it's not just picking empty squares
    active_cells = [c for c in cells if c[3] > 0]
    random.seed(3)
    chosen = random.sample(active_cells, k=min(6, len(active_cells))) if active_cells else []

    LOOP = 6
    for i, (x, y, color, count) in enumerate(chosen):
        cx, cy = x + CELL / 2, y + CELL / 2
        begin = round((LOOP / len(chosen)) * i, 2)

        # the cell itself: rises up a bit, then disappears right as it "bursts"
        parts.append(
            f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" fill="{color}">'
            f'<animate attributeName="y" values="{y};{y-40};{y-40}" keyTimes="0;0.5;1" '
            f'dur="1.4s" begin="{begin}s" repeatCount="indefinite"/>'
            f'<animate attributeName="opacity" values="1;1;0" keyTimes="0;0.55;0.6" '
            f'dur="1.4s" begin="{begin}s" repeatCount="indefinite"/>'
            f'</rect>'
        )

        # fragments: smaller squares of the same color, flying outward from the peak point
        burst_begin = begin + 0.7
        peak_y = y - 40
        num_fragments = 6
        for f in range(num_fragments):
            angle = (360 / num_fragments) * f
            import math
            dx = 22 * math.cos(math.radians(angle))
            dy = 22 * math.sin(math.radians(angle))
            end_x, end_y = cx + dx, peak_y + dy
            size = 4
            parts.append(
                f'<rect x="{cx - size/2:.1f}" y="{peak_y - size/2:.1f}" width="{size}" height="{size}" '
                f'fill="{color}" opacity="0">'
                f'<animate attributeName="x" values="{cx - size/2:.1f};{end_x - size/2:.1f}" '
                f'dur="0.8s" begin="{burst_begin:.2f}s" repeatCount="indefinite"/>'
                f'<animate attributeName="y" values="{peak_y - size/2:.1f};{end_y - size/2:.1f}" '
                f'dur="0.8s" begin="{burst_begin:.2f}s" repeatCount="indefinite"/>'
                f'<animate attributeName="opacity" values="0;1;0" keyTimes="0;0.15;1" '
                f'dur="0.8s" begin="{burst_begin:.2f}s" repeatCount="indefinite"/>'
                f'</rect>'
            )

    parts.append('</svg>')

    with open("fireworks.svg", "w") as f:
        f.write("\n".join(parts))

    print(f"wrote fireworks.svg with {len(cells)} real cells, {len(chosen)} bursting")


if __name__ == "__main__":
    main()
