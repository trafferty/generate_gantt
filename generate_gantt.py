#!/usr/bin/env python3
"""
Gantt Chart Generator
=====================
Edit your tasks YAML file to update tasks/dates, then run:

    python generate_gantt.py --tasks my_project.yaml
    python generate_gantt.py --tasks my_project.yaml --format both

Dependencies: pip install pyyaml matplotlib
"""

import math
import re
import textwrap
import yaml
import matplotlib
matplotlib.use("Agg")  # non-interactive backend; change to "TkAgg" to preview
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import argparse


# ── colour palette (one per group, cycles if more groups than colours) ────────
PALETTE = [
    "#4e79a7",  # blue
    "#f28e2b",  # orange
    "#e15759",  # red
    "#76b7b2",  # teal
    "#59a14f",  # green
    "#edc948",  # yellow
    "#b07aa1",  # purple
    "#ff9da7",  # pink
]


WORKDAYS_DEFAULT = "M,T,W,Th,F"
LABEL_WRAP_WIDTH = 25   # characters; task names longer than this wrap to a second line
HOURS_PER_DAY    = 8

# Abbreviation → Python weekday (0=Mon … 6=Sun)
_DAY_MAP = {"m": 0, "t": 1, "w": 2, "th": 3, "f": 4, "sa": 5, "su": 6}


def parse_workdays(s: str) -> set:
    """'M,T,W,Th,F'  →  {0, 1, 2, 3, 4}  (Python weekday ints)."""
    result = set()
    for part in s.replace(" ", "").split(","):
        key = part.lower()
        if key not in _DAY_MAP:
            raise ValueError(
                f"Unknown workday {part!r}. Valid values: M T W Th F Sa Su"
            )
        result.add(_DAY_MAP[key])
    return result


def add_working_days(start: datetime, n: float, workday_set: set) -> datetime:
    """Return the date that is n working days after start."""
    n = math.ceil(n)
    if n <= 0:
        return start
    current, added = start, 0
    while added < n:
        current += timedelta(days=1)
        if current.weekday() in workday_set:
            added += 1
    return current


def duration_to_working_days(s: str, days_per_week: float, days_per_month: float) -> float:
    """Convert a duration string to a (possibly fractional) number of working days.

    Supported units:
        3d   → 3 working days
        2w   → 2 * days_per_week working days
        40h  → 40 / HOURS_PER_DAY working days
        1.5m → 1.5 * days_per_month working days
    """
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([dwhm])", s.strip().lower())
    if not m:
        raise ValueError(
            f"Invalid duration {s!r}. "
            "Examples: '3d' (days), '2w' (weeks), '40h' (hours), '1.5m' (months)."
        )
    value, unit = float(m.group(1)), m.group(2)
    if unit == "d":
        return value
    if unit == "w":
        return value * days_per_week
    if unit == "h":
        return value / HOURS_PER_DAY
    if unit == "m":
        return value * days_per_month


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def load_data(yaml_file: str) -> dict:
    with open(yaml_file) as f:
        return yaml.safe_load(f)


def resolve_task_dates(data: dict, workday_set: set, days_per_week: float, days_per_month: float) -> dict:
    """Compute {start, due} for every task, resolving predecessor chains.

    Returns a dict mapping task_id -> {"start": datetime, "due": datetime}.
    Tasks with 'predecessor' inherit their start date as the next working day
    after the predecessor's due date.  Circular dependencies are detected.
    """
    raw_tasks = {}
    for group in data["groups"]:
        for task in group["tasks"]:
            raw_tasks[task["id"]] = task

    resolved  = {}
    resolving = set()  # tracks the current resolution stack for cycle detection

    def resolve(task_id: str) -> dict:
        if task_id in resolved:
            return resolved[task_id]
        if task_id in resolving:
            raise ValueError(
                f"Circular predecessor dependency involving task {task_id!r}."
            )
        if task_id not in raw_tasks:
            raise ValueError(f"Unknown task id {task_id!r} referenced as predecessor.")

        resolving.add(task_id)
        task = raw_tasks[task_id]

        # ── resolve start ──────────────────────────────────────────────────────
        if "start" in task:
            start = parse_date(task["start"])
        elif "predecessor" in task:
            pred = resolve(task["predecessor"])
            # start the next working day after the predecessor's due date
            start = add_working_days(pred["due"], 1, workday_set)
        else:
            raise ValueError(
                f"Task {task_id!r} has neither 'start' nor 'predecessor'."
            )

        # ── resolve due ────────────────────────────────────────────────────────
        if "due" in task:
            due = parse_date(task["due"])
        elif "duration" in task:
            wd  = duration_to_working_days(task["duration"], days_per_week, days_per_month)
            due = add_working_days(start, wd, workday_set)
        else:
            raise ValueError(
                f"Task {task_id!r} has neither 'due' nor 'duration'."
            )

        resolving.discard(task_id)
        resolved[task_id] = {"start": start, "due": due}
        return resolved[task_id]

    for task_id in raw_tasks:
        resolve(task_id)

    return resolved


def build_rows(data: dict, workday_set: set, days_per_week: float, days_per_month: float) -> list:
    """Flatten groups + tasks into an ordered list of display rows.

    Each task must have either a 'due' date or a 'duration' field, and either
    a 'start' date or a 'predecessor' task id.  If 'predecessor' is given the
    start date is set to the next working day after that task's due date.
    """
    dates = resolve_task_dates(data, workday_set, days_per_week, days_per_month)

    rows = []
    for gi, group in enumerate(data["groups"]):
        color = PALETTE[gi % len(PALETTE)]
        rows.append({"type": "group", "label": group["name"], "color": color})
        for task in group["tasks"]:
            d = dates[task["id"]]
            rows.append(
                {
                    "type": "task",
                    "id": task["id"],
                    "label": task["name"],
                    "assignee": str(task.get("assignee", "")),
                    "start": d["start"],
                    "due": d["due"],
                    "color": color,
                    "group": group["name"],
                }
            )
    return rows


def generate_gantt(yaml_file: str, output: str, formats: list = None, show_legend: bool = None) -> None:
    if formats is None:
        formats = ["png"]
    data = load_data(yaml_file)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    # ── workday config ────────────────────────────────────────────────────────
    workday_str   = data["project"].get("workdays", WORKDAYS_DEFAULT)
    workday_set   = parse_workdays(workday_str)
    days_per_week  = float(len(workday_set))
    days_per_month = days_per_week / 7.0 * 30.44

    # ── legend visibility: CLI flag beats YAML setting, YAML beats default (True) ──
    if show_legend is None:
        show_legend = data["project"].get("legend", True)

    rows = build_rows(data, workday_set, days_per_week, days_per_month)

    # ── pre-wrap long task labels ──────────────────────────────────────────────
    wrapped_task_label = {
        row["id"]: textwrap.fill(row["label"], width=LABEL_WRAP_WIDTH)
        for row in rows if row["type"] == "task"
    }
    n_extra_lines = sum(1 for w in wrapped_task_label.values() if "\n" in w)

    # ── figure sizing ─────────────────────────────────────────────────────────
    n_rows = len(rows)
    fig_h = max(10, n_rows * 0.58 + n_extra_lines * 0.38 + 3.0)
    fig, ax = plt.subplots(figsize=(22, fig_h))

    # ── collect dates for axis limits ─────────────────────────────────────────
    all_starts = [r["start"] for r in rows if r["type"] == "task"]
    all_dues   = [r["due"]   for r in rows if r["type"] == "task"]

    # ── draw rows top-to-bottom (y=0 at top after invert_yaxis) ──────────────
    ytick_pos, ytick_labels = [], []

    for y, row in enumerate(rows):
        if row["type"] == "group":
            # ── group header row ─────────────────────────────────────────────
            # full-width tinted band
            ax.barh(
                y, 1, left=0, height=0.92,
                color=row["color"], alpha=0.12,
                transform=ax.get_yaxis_transform(), zorder=1,
            )
            ytick_pos.append(y)
            ytick_labels.append(f"▸  {row['label']}")

        else:
            # ── task bar ─────────────────────────────────────────────────────
            start = row["start"]
            due   = row["due"]
            past  = due < today
            alpha = 0.40 if past else 0.85
            duration = max((due - start).days, 1)

            ax.barh(
                y, duration,
                left=mdates.date2num(start),
                height=0.62,
                color=row["color"], alpha=alpha,
                edgecolor="white", linewidth=0.8,
                zorder=3,
            )

            # hatching for past-due tasks
            if past:
                ax.barh(
                    y, duration,
                    left=mdates.date2num(start),
                    height=0.62,
                    fill=False, hatch="////",
                    edgecolor=row["color"], linewidth=0,
                    zorder=3, alpha=0.35,
                )

            # start date label to the left of the bar
            ax.text(
                mdates.date2num(start) - 0.8, y,
                f"{start.strftime('%b')} {start.day}",
                va="center", ha="right",
                fontsize=9, color="#333",
                zorder=4,
            )

            # duration label inside the bar (only when bar is wide enough)
            if duration >= 7:
                wd_count = sum(
                    1 for i in range(1, duration + 1)
                    if (start + timedelta(days=i)).weekday() in workday_set
                )
                int_dpw = max(int(round(days_per_week)), 1)
                weeks, extra = divmod(wd_count, int_dpw)
                if extra == 0 and weeks >= 1:
                    dur_text = f"{weeks}w"
                elif weeks >= 1:
                    dur_text = f"{weeks}w {extra}d"
                else:
                    dur_text = f"{wd_count}d"
                ax.text(
                    mdates.date2num(start) + duration / 2, y,
                    dur_text,
                    va="center", ha="center",
                    fontsize=8, color="white", fontweight="bold",
                    zorder=4,
                )

            # due date + assignee label to the right of the bar
            end_label = f"{due.strftime('%b')} {due.day}"
            if row["assignee"]:
                end_label += f"  [{row['assignee']}]"
            ax.text(
                mdates.date2num(due) + 0.8, y,
                end_label,
                va="center", ha="left",
                fontsize=9, color="#333",
                zorder=4,
            )

            ytick_pos.append(y)
            ytick_labels.append(wrapped_task_label[row["id"]])

    # ── today marker ──────────────────────────────────────────────────────────
    from matplotlib.transforms import blended_transform_factory
    today_x = mdates.date2num(today)
    ax.axvline(today_x, color="#cc0000", lw=1.8, linestyle="--", zorder=5)
    # Use blended transform: data x-coords, axes y-coords (so it stays at
    # the bottom of the chart regardless of y-axis range)
    trans_today = blended_transform_factory(ax.transData, ax.transAxes)
    ax.text(
        today_x, 0.99, today.strftime("%b %-d"),
        transform=trans_today,
        color="#cc0000", fontsize=10,
        ha="center", va="top", zorder=5,
        fontweight="bold",
    )

    # ── x axis (top) ──────────────────────────────────────────────────────────
    proj_start = data["project"].get("start")
    x_min = parse_date(proj_start) if proj_start else min(all_starts) - timedelta(days=5)
    x_max = max(all_dues) + timedelta(days=28)  # extra room for end-date labels
    ax.set_xlim(mdates.date2num(x_min), mdates.date2num(x_max))  # set limits first
    ax.xaxis_date()
    ax.xaxis.tick_top()                                            # move to top
    ax.xaxis.set_label_position("top")
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))   # Mondays
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha="left", fontsize=10)

    # ── y axis ────────────────────────────────────────────────────────────────
    ax.set_yticks(ytick_pos)
    ax.set_yticklabels(ytick_labels, fontsize=10)
    ax.set_ylim(-1.2, n_rows)
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0)

    # bold + coloured group header labels
    for tick_label, row in zip(ax.get_yticklabels(), rows):
        if row["type"] == "group":
            tick_label.set_fontweight("bold")
            tick_label.set_color(row["color"])
            tick_label.set_fontsize(11)

    # ── grid & spines ─────────────────────────────────────────────────────────
    ax.grid(axis="x", alpha=0.2, linestyle=":", zorder=0)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    # ── legend ────────────────────────────────────────────────────────────────
    if show_legend:
        handles = []
        for gi, group in enumerate(data["groups"]):
            handles.append(
                mpatches.Patch(
                    color=PALETTE[gi % len(PALETTE)], alpha=0.85,
                    label=group["name"],
                )
            )
        handles.append(
            plt.Line2D([0], [0], color="#cc0000", lw=1.8, linestyle="--", label="Today")
        )
        handles.append(
            mpatches.Patch(
                facecolor="white", edgecolor="#888", hatch="////", alpha=0.6,
                label="Past due",
            )
        )
        ax.legend(
            handles=handles,
            loc="upper center",
            bbox_to_anchor=(0.5, 1.0),
            fontsize=10, framealpha=0.92,
            ncol=len(handles),
        )

    # ── title ─────────────────────────────────────────────────────────────────
    proj = data["project"]
    title_line = proj["name"]
    if proj.get("subtitle"):
        title_line += f" — {proj['subtitle']}"
    subtitle_line = f"Generated {today.strftime('%B %d, %Y')}"
    rev_str = proj.get("revision_date")
    if rev_str:
        subtitle_line += f"  ·  Rev {parse_date(rev_str).strftime('%B %d, %Y')}"
    ax.set_title(title_line, fontsize=15, fontweight="bold", pad=80)
    # Subtitle in a smaller font, placed between the tick labels and main title
    from matplotlib.transforms import ScaledTranslation
    subtitle_transform = ax.transAxes + ScaledTranslation(0, 52/72, fig.dpi_scale_trans)
    ax.text(
        0.5, 1.0, subtitle_line,
        transform=subtitle_transform,
        fontsize=10, ha="center", va="bottom", color="#555555",
    )

    plt.tight_layout()

    # ── save in requested format(s) ───────────────────────────────────────────
    import os
    if output:
        base, _ = os.path.splitext(output)
    else:
        project_slug = data["project"]["name"].replace(" ", "_")
        rev_str = data["project"].get("revision_date")
        file_date = parse_date(rev_str) if rev_str else today
        base = f"{project_slug}-{file_date.strftime('%Y-%m-%d')}_Gantt"

    for fmt in formats:
        path = f"{base}.{fmt}"
        kwargs = {"bbox_inches": "tight", "facecolor": "white"}
        if fmt == "png":
            kwargs["dpi"] = 150
        plt.savefig(path, **kwargs)
        print(f"Gantt chart saved → {path}")

    plt.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Generate a Gantt chart from a YAML task file")
    p.add_argument("--tasks",  default="tasks.yaml", help="YAML task file (default: tasks.yaml)")
    p.add_argument("--output", default=None,
                   help="Output base filename (default: auto-generated from project name and date)")
    p.add_argument(
        "--format", dest="fmt", default="png",
        choices=["png", "pdf", "both"],
        help="Output format: png, pdf, or both (default: png)",
    )
    p.add_argument(
        "--no-legend", dest="no_legend", action="store_true",
        help="Suppress the legend (overrides 'legend: false' in the YAML)",
    )
    args = p.parse_args()
    formats = ["png", "pdf"] if args.fmt == "both" else [args.fmt]
    show_legend = False if args.no_legend else None  # None → defer to YAML
    generate_gantt(args.tasks, args.output, formats, show_legend=show_legend)
