"""
The github-gravity action bakes a one-time physics simulation into a fixed
length SVG animation - there's no setting to control how long that takes or
make it loop on a fixed interval. This script re-scales every animation
timing in the generated file so the whole thing plays out in exactly 4
seconds and loops forever, instead of whatever length it happened to render at.

Best-effort: it looks for simple "<number>s" style begin/dur values (the
normal SMIL format). If github-gravity ever outputs something more unusual
(references to other elements' timing, keyword values like "indefinite"),
those are left untouched rather than guessed at.
"""
import re
import sys

TARGET_SECONDS = 4.0

TIME_PATTERN = re.compile(r'^(-?\d+(?:\.\d+)?)s$')


def parse_seconds(value):
    match = TIME_PATTERN.match(value.strip())
    return float(match.group(1)) if match else None


def rescale(path):
    with open(path) as f:
        content = f.read()

    # find every begin="..." and dur="..." that look like plain "<number>s"
    begins = [parse_seconds(v) for v in re.findall(r'begin="([^"]+)"', content)]
    durs = [parse_seconds(v) for v in re.findall(r'dur="([^"]+)"', content)]

    begins = [b for b in begins if b is not None]
    durs = [d for d in durs if d is not None]

    if not durs:
        print("no parseable animation timing found, leaving file as-is")
        return

    # total natural length of the whole simulation
    natural_total = max((b or 0) + d for b, d in zip(begins + [0] * len(durs), durs))
    if natural_total <= 0:
        print("could not determine a natural duration, leaving file as-is")
        return

    scale = TARGET_SECONDS / natural_total

    def rescale_time_attr(match):
        attr_name, value = match.group(1), match.group(2)
        seconds = parse_seconds(value)
        if seconds is None:
            return match.group(0)
        return f'{attr_name}="{seconds * scale:.3f}s"'

    content = re.sub(r'(begin)="([^"]+)"', rescale_time_attr, content)
    content = re.sub(r'(dur)="([^"]+)"', rescale_time_attr, content)

    # make sure every animation element loops, so the 4s sequence repeats forever
    for tag in ["animate", "animateTransform", "animateMotion"]:
        content = re.sub(
            rf'(<{tag}(?![^>]*repeatCount)[^>]*)(/?>)',
            rf'\1 repeatCount="indefinite"\2',
            content,
        )

    with open(path, "w") as f:
        f.write(content)

    print(f"rescaled animation from {natural_total:.2f}s to {TARGET_SECONDS}s and set to loop")


if __name__ == "__main__":
    rescale(sys.argv[1] if len(sys.argv) > 1 else "gravity.svg")
