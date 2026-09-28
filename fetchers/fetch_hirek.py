#!/usr/bin/env python3
"""
Piaci hírek gyűjtése komoly hangvételű hazai hír- és gazdasági portálok
RSS-feedjeiből.

Csak magyar forrásokból dolgozik: a nemzetközi jelöltek (Automotive News
Europe, Reuters Autos) nyilvános RSS-je megszűnt/bot-védett (ellenőrizve
2026-09-18-án), ha valaha elérhetővé válik egy működő feed, ide vehető fel.

A Totalcar.hu SZÁNDÉKOSAN nincs a forrásjegyzékben - a feedje túlnyomórészt
teszt/bulvár/baleseti tartalom, és még a szigorú kulcsszó-szűrés mellett is
átcsúszott rajta clickbait jellegű cikk (kérésre eltávolítva, 2026-09-18).

Két szűrő fut minden cikkre (csak a CÍMBEN, a leírás bevonása korábban
politikai/gazdasági hírekkel szennyezte a listát):
1. is_relevant() - a cím tartalmaz-e legalább egy összetett, egyértelműen
   autópiaci/iparági kifejezést. Szándékosan NEM elég önmagában a "piac" vagy
   "eladás" szó (ezek túl tágak: "kukoricapiac", "eladó a sztár autója").
2. is_clickbait() - kizárja a bulvár/szenzációhajhász címeket (felkiáltójel,
   kérdőjeles rájátszás, jellegzetes clickbait-szavak). Ez egy durva
   heurisztika, nem stíluselemzés - occasionally túl szigorú/enyhe lehet.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
OUT_PATH = DATA_DIR / "hirek.json"

# Összetett, egyértelműen autópiaci/iparági kifejezések - direkt NEM tartalmaz
# önmagában álló, túl tág szavakat ("piac", "eladás", "elad", "kínálat"),
# mert azok politikai/bulvár hírekkel is matcheltek (ld. modul docstring).
MARKET_TERMS = [
    "autóipar", "autópiac", "autóipari", "gépjárműipar", "autógyár", "autógyártó",
    "autógyártás", "elektromos autó", "villanyautó", "hibrid autó", "akkumulátorgyár",
    "autóértékesítés", "autóeladás", "autóforgalmazó", "autókereskedő",
    "üzemanyagár", "gépkocsigyártás", "-gyár", "autóalkatrész",
    "forgalomba helyez", "gépjármű-eladás",
]

# Bulvár/clickbait jellegű, szenzációhajhász hangvételű címekben tipikusan
# előforduló szavak/formák - a cél a "komoly hangvétel", nem csak a tartalmi
# relevancia, ezért egy egyébként piaci hír is kieshet, ha a CÍM bulvár-stílusú.
CLICKBAIT_MARKERS = [
    "döbbenetes", "döbbenet", "elképesztő", "elképedt", "elképed", "hihetetlen",
    "sokkoló", "brutális", "durva", "horror", "óriási", "leejtett állal",
    "nem hiszed el", "videó:", "fotó:", "képek:", "padlót fog", "botrány",
    "pánik", "őrület", "ripacskodik", "szenzáció", "kiderült,", "megríkat",
    "tuti", "köszönetet mondhat", "hatalmas", "elképesztő",
]

FEEDS = [
    {"source": "Vezess.hu", "url": "https://www.vezess.hu/feed/"},
    {"source": "Portfolio.hu", "url": "https://www.portfolio.hu/rss/all.xml"},
    {"source": "Világgazdaság", "url": "https://www.vg.hu/feed"},
]

MAX_PER_SOURCE = 8
MAX_TOTAL = 30


def fetch_feed(url: str) -> bytes | None:
    result = subprocess.run(
        ["curl", "-s", "-L", "-A", "Mozilla/5.0", "--max-time", "20", url],
        capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


def is_relevant(title: str) -> bool:
    haystack = title.lower()
    return any(kw in haystack for kw in MARKET_TERMS)


def is_clickbait(title: str) -> bool:
    if "!" in title:
        return True
    if title.rstrip().endswith("?"):
        return True
    haystack = title.lower()
    return any(marker in haystack for marker in CLICKBAIT_MARKERS)


def parse_feed(source: str, xml_bytes: bytes) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    articles = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date_raw = item.findtext("pubDate")
        if not title or not link or not is_relevant(title) or is_clickbait(title):
            continue
        try:
            published = parsedate_to_datetime(pub_date_raw).astimezone(dt.timezone.utc).isoformat()
        except (TypeError, ValueError):
            published = None
        articles.append({"title": title, "link": link, "source": source, "published": published})
        if len(articles) >= MAX_PER_SOURCE:
            break
    return articles


def main():
    all_articles = []
    seen_links = set()
    for feed in FEEDS:
        raw = fetch_feed(feed["url"])
        if raw is None:
            print(f"FIGYELEM: nem sikerült lekérni: {feed['source']} ({feed['url']})", file=sys.stderr)
            continue
        try:
            articles = parse_feed(feed["source"], raw)
        except ET.ParseError as e:
            print(f"FIGYELEM: hibás XML: {feed['source']}: {e}", file=sys.stderr)
            continue
        for a in articles:
            if a["link"] in seen_links:
                continue
            seen_links.add(a["link"])
            all_articles.append(a)
        print(f"{feed['source']}: {len(articles)} releváns cikk")

    all_articles.sort(key=lambda a: a["published"] or "", reverse=True)
    all_articles = all_articles[:MAX_TOTAL]

    OUT_PATH.write_text(
        json.dumps({"generated": dt.date.today().isoformat(), "articles": all_articles}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Elmentve: {OUT_PATH} ({len(all_articles)} cikk)")


if __name__ == "__main__":
    main()
