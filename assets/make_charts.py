#!/usr/bin/env python3
"""Draw the README charts from the published benchmark reports. Standard library only.

    python3 assets/make_charts.py

Every bar's value is read from a case study's report.json, so the pictures cannot drift from the receipts.
Each chart is written twice, for light and dark pages.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", axis="#c3c2b7", accent="#2a78d6", quiet="#898781"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", axis="#383835", accent="#3987e5", quiet="#898781"),
}
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
WIDTH, LEFT, BAR_MAX, ROW, BAR = 760, 336, 320, 54, 20


def chart(title: str, subtitle: str, rows: list, theme: dict) -> str:
    """Horizontal bars from one baseline. One row is the point (accent); the rest are context (gray)."""
    top = 74
    height = top + ROW * len(rows) + 18
    longest = max(row["value"] for row in rows)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}" '
           f'role="img" aria-label="{escape(title)}. {escape("; ".join(r["name"] + " " + r["label"] for r in rows))}" '
           f'font-family=\'{FONT}\'>',
           f'<rect width="{WIDTH}" height="{height}" rx="10" fill="{theme["surface"]}"/>',
           f'<text x="24" y="34" font-size="17" font-weight="600" fill="{theme["ink"]}">{escape(title)}</text>',
           f'<text x="24" y="55" font-size="13" fill="{theme["ink2"]}">{escape(subtitle)}</text>']
    for index, row in enumerate(rows):
        y = top + ROW * index
        middle = y + ROW / 2
        length = max(4.0, BAR_MAX * row["value"] / longest)
        bar_y, r = middle - BAR / 2, 4
        weight = "600" if row.get("accent") else "400"
        out += [
            f'<text x="24" y="{middle - 3:.1f}" font-size="14" font-weight="{weight}" fill="{theme["ink"]}">{escape(row["name"])}</text>',
            f'<text x="24" y="{middle + 14:.1f}" font-size="12" fill="{theme["ink2"]}">{escape(row["note"])}</text>',
            # square at the baseline, rounded at the data end
            f'<path d="M{LEFT} {bar_y:.1f} h{length - r:.1f} a{r} {r} 0 0 1 {r} {r} v{BAR - 2 * r} a{r} {r} 0 0 1 -{r} {r} '
            f'h-{length - r:.1f} z" fill="{theme["accent"] if row.get("accent") else theme["quiet"]}"/>',
            f'<text x="{LEFT + length + 10:.1f}" y="{middle + 5:.1f}" font-size="14" font-weight="{weight}" '
            f'fill="{theme["ink"]}">{escape(row["label"])}</text>',
        ]
    out.append(f'<line x1="{LEFT}" y1="{top + 6}" x2="{LEFT}" y2="{top + ROW * len(rows) - 6}" stroke="{theme["axis"]}" stroke-width="1"/>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def charts() -> dict:
    features = json.loads((ROOT / "case-studies/feature-benchmark-2026-11-10/report.json").read_text())
    pairs = json.loads((ROOT / "case-studies/paired-features-2026-11-10/report.json").read_text())
    arm = {row["arm"]: row for row in features["arms"].values()}
    pair = {row["arm"]: row for row in pairs["arms"].values()}

    def task_row(key: str, name: str, accent: bool = False) -> dict:
        row = arm[key]
        return dict(name=name, note=f'{row["solved"]} of {row["tasks"]} tasks solved', value=float(row["usd_per_task"]),
                    label=f'${float(row["usd_per_task"]):.3f}', accent=accent)

    def pair_row(key: str, name: str, accent: bool = False) -> dict:
        row = pair[key]
        return dict(name=name, note=f'{row["solved"]} of {row["pairs"]} pairs pass both test sets',
                    value=float(row["usd_per_pair"]), label=f'${float(row["usd_per_pair"]):.3f}', accent=accent)

    def call_row(key: str, name: str, accent: bool = False) -> dict:
        row = pair[key]
        return dict(name=name, note=f'{row["solved"]} of {row["pairs"]} pairs pass, {row["sessions_woken"]} worker sessions woken',
                    value=row["model_calls"], label=f'{row["model_calls"]} calls', accent=accent)

    return {
        "benchmark-features": ("Cost per task", "66 real feature tasks in Click, Jinja and dirty-equals, graded by hidden tests", [
            task_row("astra-solo", "Heavy model alone (gpt-6-astra)"),
            task_row("frontier-solo", "Frontier model alone (gpt-6.1-sol)"),
            task_row("klp-3", "KLP Standard", accent=True)]),
        "benchmark-pairs": ("Cost per pair", "30 pairs of conflicting features, both delivered in one tree", [
            pair_row("solo", "Frontier model alone (gpt-6.1-sol)"),
            pair_row("semio", "Two KLP workers, joined by Semio", accent=True)]),
        "benchmark-coordination": ("Model calls to integrate the same 30 pairs", "Same finished features, same workers; only the coordination differs", [
            call_row("chat", "Agents coordinate by chat"),
            call_row("semio", "Semio typed handovers", accent=True)]),
    }


def main() -> None:
    for name, (title, subtitle, rows) in charts().items():
        for mode, theme in THEMES.items():
            (ROOT / "assets" / f"{name}-{mode}.svg").write_text(chart(title, subtitle, rows, theme))
    print("wrote", ", ".join(sorted(p.name for p in (ROOT / "assets").glob("benchmark-*.svg"))))


if __name__ == "__main__":
    main()
