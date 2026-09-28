#!/usr/bin/env python3
"""
Automatizált piaci előrejelző riport generátor.

Használat:
    python3 generate_report.py [--scenario alap|pesszimista|optimista]

Kimenet: markdown riport a reports/ mappába, dátumozott fájlnévvel.
Ütemezve (pl. cron / Claude Code /schedule) futtatva ez adja az "automatizált
riportolási rendszer" magját: minden futáskor újraértékeli a szegmenseket a
config/factors.json aktuális (vagy frissített) feltételezései alapján.
"""

from __future__ import annotations

import argparse
import datetime as dt
from collections import defaultdict
from pathlib import Path

from engine import SCENARIOS, classify, compute_segments

REPORTS_DIR = Path(__file__).parent / "reports"


def fmt_pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def aggregate(results, scenario: str, key_fn, label_fn):
    buckets = defaultdict(list)
    for r in results:
        buckets[key_fn(r)].append(r.scores[scenario])
    rows = []
    for key, scores in buckets.items():
        avg = sum(scores) / len(scores)
        rows.append((label_fn(key), avg))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


def build_report(scenario: str) -> str:
    results, factors = compute_segments()
    results_sorted = sorted(results, key=lambda r: r.scores[scenario], reverse=True)

    today = dt.date.today().isoformat()
    lines = []
    lines.append(f"# Autópiaci előrejelző riport — {today}")
    lines.append("")
    lines.append(f"Forgatókönyv: **{scenario}** | Horizont: 12 hónap")
    lines.append("")
    lines.append(
        "> Ez a riport valós adatból kalibrált forgatókönyv-sávokból (5 tényező "
        "automata forrásból, 3 kézi, forrásmegjelölt adatfájlból) számolt "
        "RELATÍV kitettségi pontszámokat mutat be szegmensenként, nem "
        "abszolút eladási előrejelzést. A számok iránya és nagyságrendje "
        "informál, a pontos érték a mögöttes feltételezések finomításával "
        "(ld. README) pontosítható."
    )
    lines.append(
        "> **Fontos:** a \"pesszimista/alap/optimista\" tengely a "
        "**zöld átállás (EV-adaptáció) szempontjából** pesszimista/optimista "
        "forgatókönyvet jelenti, nem általános gazdasági borúlátást/derülátást. "
        "Pl. a pesszimista olajár-forgatókönyvben az olajár *esik* (ami rossz "
        "az EV-knek), ezért ilyenkor a benzin/dízel szegmensek is nőhetnek — "
        "ez nem hiba, hanem a tengely definíciójából következik."
    )
    lines.append("")

    lines.append("## 1. Vizsgált tényezők és feltételezett elmozdulásuk")
    lines.append("")
    lines.append("| Tényező | Pesszimista | Alap | Optimista |")
    lines.append("|---|---|---|---|")
    for f in factors.values():
        s = f["scenarios"]
        unit = f["unit"]
        sep = "" if unit == "%" else " "  # "%" simán a szám után, "pp"/"index" elé szóköz kell
        lines.append(
            f"| {f['label']} | {s['pesszimista']:+.1f}{sep}{unit} "
            f"| {s['alap']:+.1f}{sep}{unit} | {s['optimista']:+.1f}{sep}{unit} |"
        )
    lines.append("")

    lines.append("## 2. Összegzés hajtástípus szerint")
    lines.append("")
    lines.append("| Hajtástípus | Átlagos kitettségi pontszám | Irány |")
    lines.append("|---|---|---|")
    for label, avg in aggregate(
        results, scenario, lambda r: r.drivetrain, lambda k: next(
            r.drivetrain_label for r in results if r.drivetrain == k
        )
    ):
        lines.append(f"| {label} | {fmt_pct(avg)} | {classify(avg)} |")
    lines.append("")

    lines.append("## 3. Összegzés márkakategória szerint")
    lines.append("")
    lines.append("| Márkakategória | Átlagos kitettségi pontszám | Irány |")
    lines.append("|---|---|---|")
    for label, avg in aggregate(
        results, scenario, lambda r: r.brand_tier, lambda k: next(
            r.brand_tier_label for r in results if r.brand_tier == k
        )
    ):
        lines.append(f"| {label} | {fmt_pct(avg)} | {classify(avg)} |")
    lines.append("")

    lines.append("## 4. Összegzés évjárat-sáv szerint")
    lines.append("")
    lines.append("| Évjárat | Átlagos kitettségi pontszám | Irány |")
    lines.append("|---|---|---|")
    for label, avg in aggregate(
        results, scenario, lambda r: r.year_bucket, lambda k: next(
            r.year_bucket_label for r in results if r.year_bucket == k
        )
    ):
        lines.append(f"| {label} | {fmt_pct(avg)} | {classify(avg)} |")
    lines.append("")

    lines.append("## 5. Legerősebb nyertes szegmensek")
    lines.append("")
    for r in results_sorted[:5]:
        top_drivers = ", ".join(
            f"{name} ({fmt_pct(val)})" for name, val in r.drivers[scenario][:2]
        )
        lines.append(
            f"- **{r.drivetrain_label} / {r.brand_tier_label} / {r.year_bucket_label}** "
            f"— {classify(r.scores[scenario])} ({fmt_pct(r.scores[scenario])}). "
            f"Fő hajtóerő: {top_drivers}."
        )
    lines.append("")

    lines.append("## 6. Legerősebb vesztes szegmensek")
    lines.append("")
    for r in results_sorted[-5:][::-1]:
        top_drivers = ", ".join(
            f"{name} ({fmt_pct(val)})" for name, val in r.drivers[scenario][:2]
        )
        lines.append(
            f"- **{r.drivetrain_label} / {r.brand_tier_label} / {r.year_bucket_label}** "
            f"— {classify(r.scores[scenario])} ({fmt_pct(r.scores[scenario])}). "
            f"Fő hajtóerő: {top_drivers}."
        )
    lines.append("")

    lines.append("## 7. Teljes szegmensmátrix")
    lines.append("")
    lines.append("| Hajtástípus | Márkakategória | Évjárat | Pontszám | Irány |")
    lines.append("|---|---|---|---|---|")
    for r in results_sorted:
        lines.append(
            f"| {r.drivetrain_label} | {r.brand_tier_label} | {r.year_bucket_label} "
            f"| {fmt_pct(r.scores[scenario])} | {classify(r.scores[scenario])} |"
        )
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario", choices=SCENARIOS, default="alap",
        help="Melyik forgatókönyvre készüljön a fő riport (default: alap)",
    )
    parser.add_argument(
        "--all-scenarios", action="store_true",
        help="Mindhárom forgatókönyvre külön szakaszt generál egy fájlba",
    )
    args = parser.parse_args()

    REPORTS_DIR.mkdir(exist_ok=True)
    today = dt.date.today().isoformat()

    if args.all_scenarios:
        parts = [build_report(s) for s in SCENARIOS]
        content = "\n\n---\n\n".join(parts)
        out_path = REPORTS_DIR / f"riport_{today}_minden-forgatokonyv.md"
    else:
        content = build_report(args.scenario)
        out_path = REPORTS_DIR / f"riport_{today}_{args.scenario}.md"

    out_path.write_text(content, encoding="utf-8")
    print(f"Riport elkészült: {out_path}")


if __name__ == "__main__":
    main()
