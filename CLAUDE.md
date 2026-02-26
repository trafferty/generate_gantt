# Nexus PEC Schedule — Project Context

## What This Is

A data-driven Gantt chart generator. Task data lives in a YAML file;
a Python script reads it and produces a PNG and/or PDF chart.

The source notes that kicked this off are in `Nexus_2026_goals.txt`.

---

## Files

| File | Purpose |
|------|---------|
| `nexus_tasks.yaml` | Task data for the Nexus PEC project — edit this to update the chart |
| `generate_gantt.py` | General-purpose Gantt generator — reads any conforming YAML file |
| `Nexus_2026_goals.txt` | Original freeform planning notes (read-only reference) |

Generated output files follow the naming pattern:
`{Project_Name}-{YYYY-MM-DD}_Gantt.{png|pdf}`

---

## Running the Script

```bash
source ~/venv/data/bin/activate

python3 generate_gantt.py --tasks nexus_tasks.yaml            # PNG (default)
python3 generate_gantt.py --tasks nexus_tasks.yaml --format pdf
python3 generate_gantt.py --tasks nexus_tasks.yaml --format both
python3 generate_gantt.py --tasks nexus_tasks.yaml --output my_name  # override filename base
```

**Dependencies** (already installed in `~/venv/data`): `pyyaml`, `matplotlib`

---

## YAML Schema

### `project` section

```yaml
project:
  name: "My Project"           # required — used in chart title and output filename
  subtitle: "Q1 Roadmap"       # optional — appended to title as "Name — Subtitle"
  start: "2026-01-15"          # optional — pins the left edge of the chart;
                               #   defaults to earliest task start date
  workdays: "M,T,W,Th,F"      # optional — working days for duration calculation;
                               #   default is M–F; valid tokens: M T W Th F Sa Su
```

### `groups` section

Groups contain tasks and are rendered as labelled, colour-coded sections.

```yaml
groups:
  - name: "Group Name"
    tasks:
      - id: unique_task_id          # required, used internally (no spaces)
        name: "Human-readable name" # required
        assignee: "Alice, Bob"      # optional
        start: "2026-02-01"         # required
        due: "2026-02-14"           # use EITHER due OR duration (not both)
        duration: "2w"              # alternative to due — see Duration Formats below
```

### Duration Formats

When using `duration:` instead of `due:`, the due date is computed by advancing
`start` by the specified number of **working days** (respecting `workdays`).

| Format | Meaning |
|--------|---------|
| `3d`   | 3 working days |
| `2w`   | 2 × working-days-per-week (5 for M–F) |
| `40h`  | 40 hours ÷ 8 hrs/day → working days |
| `1.5m` | 1.5 months × ~21.7 working days/month (for M–F week) |

Fractional values are supported (e.g. `2.5d`, `1.7m`). Results are rounded up
to the nearest whole working day.

---

## Chart Features

- **Colour-coded groups** — one colour per group, up to 8 (then cycles)
- **Past-due tasks** — dimmed + hatched automatically (due date < today)
- **Today marker** — red dashed vertical line labelled with current date at top
- **Dates at top** — x-axis ticks on top of chart, weekly (Mondays)
- **End-date labels** — each bar shows `Mon DD  Assignee` to its right
- **Auto filename** — output named `{Project_Name}-{YYYY-MM-DD}_Gantt.{ext}`

---

## Design Decisions / Notes

- The script is **fully general** — no hardcoded project names. All project-specific
  content comes from the YAML file.
- `project.start` anchors the chart's left edge; if omitted the chart starts
  5 days before the earliest task.
- `workdays` affects duration calculations only; it does not shade weekends on
  the chart (potential future enhancement).
- The matplotlib backend is set to `"Agg"` (non-interactive). Change to
  `"TkAgg"` at the top of the script if you want an interactive preview window.
- PDF output is vector-based (no `dpi` arg); PNG uses `dpi=150`.

---

## Potential Future Enhancements

- Shade non-working days on the chart
- `depends_on:` field to auto-compute start dates from predecessor task due dates
- Milestone markers (zero-duration tasks rendered as a diamond)
- Per-task colour override
- Hours-per-day configurable in project section (currently hardcoded to 8)
