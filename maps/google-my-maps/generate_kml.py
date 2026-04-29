#!/usr/bin/env python3
"""Generate Google My Maps KML files from pages/plan-a-cn.html.

The HTML itinerary remains the source of truth. This script extracts the
itinerary data without executing the page JavaScript, geocodes route points,
and writes one KML file per day for Google My Maps import.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
HTML_PATH = ROOT / "pages" / "plan-a-cn.html"
OUT_DIR = ROOT / "maps" / "google-my-maps"
CACHE_PATH = OUT_DIR / "geocode-cache.json"
UNRESOLVED_PATH = OUT_DIR / "unresolved-locations.md"
ICON_DIR = OUT_DIR / "icons"
ICON_URL_BASE = "https://raw.githubusercontent.com/vanilla178/2026-Glasgow/stonfur/maps/google-my-maps/icons"

PHASE_ORDER = ["上午", "下午", "晚上", "其他"]
PHASE_STYLES = {
    "上午": {"line": "cc70640b", "icon": "ff70640b"},
    "下午": {"line": "cc2e62c4", "icon": "ff2e62c4"},
    "晚上": {"line": "cc60401e", "icon": "ff60401e"},
    "其他": {"line": "cc66725a", "icon": "ff66725a"},
}

PLACE_QUERIES: dict[str, str] = {
    "Aparthotel Adagio Glasgow Central": "Aparthotel Adagio Glasgow Central",
    "Ashton Lane": "55.874014,-4.293583|Ashton Lane",
    "Bettys Cafe Tea Rooms York": "53.959779,-1.083508|Bettys Cafe Tea Rooms York",
    "Buchanan Bus Station": "Buchanan Bus Station, Glasgow",
    "Calton Hill Edinburgh": "55.955174,-3.182576|Calton Hill",
    "Clyde Arc": "Clyde Arc, Glasgow",
    "Edinburgh Castle": "55.948611,-3.199913|Edinburgh Castle",
    "Edinburgh Waverley Station": "55.952245,-3.189944|Edinburgh Waverley Station",
    "Fort Augustus / Loch Ness": "57.144826,-4.680073|Fort Augustus / Loch Ness",
    "Gallery of Modern Art Glasgow": "55.8601675,-4.2526408|Gallery of Modern Art Glasgow",
    "George Square": "55.8611567,-4.2502189|George Square",
    "Glasgow Cathedral": "Glasgow Cathedral",
    "Glasgow Central": "Glasgow Central",
    "Glasgow Queen Street Station": "55.862229,-4.251227|Glasgow Queen Street Station",
    "Glencoe": "Glencoe, Scotland",
    "Grassmarket Edinburgh": "Grassmarket Edinburgh",
    "Kelvingrove Art Gallery and Museum": "55.8685825,-4.2906278|Kelvingrove Art Gallery and Museum",
    "Cathedral of the Isles": "55.756289,-4.925959|Cathedral of the Isles",
    "Crocodile Rock": "55.752996,-4.923101|Crocodile Rock",
    "Cumbrae Slip Ferry Terminal": "55.786372,-4.906553|Cumbrae Slip Ferry Terminal",
    "Largs Ferry Terminal": "55.794853,-4.871033|Largs Ferry Terminal",
    "Largs Railway Station": "55.792497,-4.867033|Largs Railway Station",
    "Largs waterfront": "55.797000,-4.868762|Largs waterfront",
    "Loch Lomond": "56.101506,-4.639122|Loch Lomond",
    "Makars Mash Bar Edinburgh": "Makars Mash Bar Edinburgh",
    "Mapes of Millport": "55.753643,-4.926052|Mapes of Millport",
    "Merchant City": "Merchant City, Glasgow, UK",
    "Millport": "55.753558,-4.928565|Millport",
    "Millport Promenade": "55.752950,-4.927511|Millport Promenade",
    "Museum Context Edinburgh": "55.948464,-3.193748|Museum Context Edinburgh",
    "Greyfriars Bobby Statue": "55.946934,-3.191443|Greyfriars Bobby Statue",
    "Greyfriars Kirkyard Edinburgh": "55.946732,-3.192410|Greyfriars Kirkyard",
    "Howies Victoria Street": "55.948471,-3.193769|Howies Victoria Street",
    "Howies Waterloo Place": "55.953813,-3.186054|Howies Waterloo Place",
    "National Museum of Scotland": "55.947500,-3.189260|National Museum of Scotland",
    "Oink Victoria Street": "55.948623,-3.193646|Oink Victoria Street",
    "Pitlochry": "56.703468,-3.729967|Pitlochry",
    "Riverside Museum": "Riverside Museum, Glasgow",
    "Scott Monument": "Scott Monument Edinburgh",
    "Scottish Event Campus": "Scottish Event Campus, Glasgow",
    "St Giles' Cathedral": "55.949521,-3.190640|St Giles' Cathedral",
    "Theatre Royal": "Theatre Royal, Glasgow, UK",
    "The Vennel Edinburgh": "55.947182,-3.196806|The Vennel Edinburgh",
    "University of Glasgow": "55.8721211,-4.2882005|University of Glasgow",
    "The Real Mary King's Close": "55.950082,-3.190527|The Real Mary King's Close",
    "Victoria Street Edinburgh": "55.948594,-3.193862|Victoria Street",
    "Waverley Bridge Edinburgh": "Waverley Bridge Edinburgh",
    "York Railway Station": "York Railway Station",
}

ITEM_POINT_OVERRIDES: list[dict[str, object]] = [
    {"day": "0524", "title": "酒店 → Glasgow Central", "points": ["Aparthotel Adagio Glasgow Central", "Glasgow Central"]},
    {"day": "0524", "title": "Glasgow Central → Largs", "points": ["Glasgow Central", "Largs Railway Station"]},
    {"day": "0524", "title": "Largs 火车站", "points": ["Largs Railway Station", "Largs Ferry Terminal"]},
    {"day": "0524", "title": "Largs → Cumbrae Slip", "points": ["Largs Ferry Terminal", "Cumbrae Slip Ferry Terminal"]},
    {"day": "0524", "title": "Cumbrae Slip → Millport", "points": ["Cumbrae Slip Ferry Terminal", "Millport"]},
    {"day": "0524", "title": "Millport promenade", "points": ["Millport Promenade", "Crocodile Rock"]},
    {"day": "0524", "title": "Millport 午餐", "points": ["Millport"]},
    {"day": "0524", "title": "天气好", "points": ["Mapes of Millport", "Millport Promenade"]},
    {"day": "0524", "title": "Cathedral of the Isles", "points": ["Cathedral of the Isles"]},
    {"day": "0524", "title": "返回 Largs", "points": ["Millport", "Cumbrae Slip Ferry Terminal", "Largs Ferry Terminal"]},
    {"day": "0524", "title": "Largs 海边", "points": ["Largs waterfront"]},
    {"day": "0524", "title": "Largs → Glasgow Central", "points": ["Largs Railway Station", "Glasgow Central"]},
    {"day": "0524", "title": "Glasgow 市区晚餐", "points": ["Merchant City"]},
    {"day": "0525", "title": "转去市中心", "points": ["Glasgow Cathedral", "George Square"]},
    {"day": "0525", "title": "George Square", "points": ["George Square"]},
    {"day": "0525", "title": "现代艺术馆", "points": ["Gallery of Modern Art Glasgow"]},
    {"day": "0525", "title": "午餐", "points": ["George Square"]},
    {"day": "0525", "title": "晚餐 / 放松", "points": ["Merchant City"]},
    {"day": "0526", "title": "前往 Buchanan Bus Station", "points": ["Aparthotel Adagio Glasgow Central", "Buchanan Bus Station"]},
    {"day": "0526", "title": "Highlands / Loch Ness / Glencoe", "points": ["Loch Lomond", "Glencoe", "Fort Augustus / Loch Ness", "Pitlochry"]},
    {"day": "0526", "title": "返回酒店附近", "points": ["Buchanan Bus Station", "Aparthotel Adagio Glasgow Central"]},
    {"day": "0526", "title": "晚餐", "points": ["Merchant City"]},
    {"day": "0527", "title": "酒店 → Glasgow Queen Street", "points": ["Aparthotel Adagio Glasgow Central", "Glasgow Queen Street Station"]},
    {"day": "0527", "title": "Glasgow Queen Street → Edinburgh Waverley", "points": ["Glasgow Queen Street Station", "Edinburgh Waverley Station"]},
    {"day": "0527", "title": "Waverley → Edinburgh Castle", "points": ["Edinburgh Waverley Station", "Edinburgh Castle"]},
    {"day": "0527", "title": "Edinburgh Castle", "points": ["Edinburgh Castle"]},
    {"day": "0527", "title": "Castle → St Giles", "points": ["Edinburgh Castle", "St Giles' Cathedral"]},
    {"day": "0527", "title": "St Giles", "points": ["St Giles' Cathedral"]},
    {"day": "0527", "title": "Royal Mile / Victoria Street 午餐", "points": ["Howies Victoria Street", "Oink Victoria Street"]},
    {"day": "0527", "title": "走到 The Real Mary King’s Close", "points": ["St Giles' Cathedral", "The Real Mary King's Close"]},
    {"day": "0527", "title": "The Real Mary King’s Close", "points": ["The Real Mary King's Close"]},
    {"day": "0527", "title": "Mary King’s Close → Victoria Street", "points": ["The Real Mary King's Close", "Victoria Street Edinburgh"]},
    {"day": "0527", "title": "Victoria Street / West Bow / Museum Context", "points": ["Victoria Street Edinburgh", "Museum Context Edinburgh"]},
    {"day": "0527", "title": "Greyfriars Bobby", "points": ["Greyfriars Bobby Statue", "Greyfriars Kirkyard Edinburgh"]},
    {"day": "0527", "title": "二选一：National Museum", "points": ["National Museum of Scotland"]},
    {"day": "0527", "title": "Old Town → Calton Hill", "points": ["National Museum of Scotland", "Calton Hill Edinburgh"]},
    {"day": "0527", "title": "Calton Hill", "points": ["Calton Hill Edinburgh"]},
    {"day": "0527", "title": "爱丁堡晚餐", "points": ["Howies Waterloo Place"]},
    {"day": "0527", "title": "回到 Edinburgh Waverley", "points": ["Howies Waterloo Place", "Edinburgh Waverley Station"]},
    {"day": "0527", "title": "Edinburgh Waverley → Glasgow Queen Street", "points": ["Edinburgh Waverley Station", "Glasgow Queen Street Station"]},
    {"day": "0528", "title": "吃早餐后前往 West End", "points": ["Aparthotel Adagio Glasgow Central", "Kelvingrove Art Gallery and Museum"]},
    {"day": "0528", "title": "开尔文格罗夫", "points": ["Kelvingrove Art Gallery and Museum"]},
    {"day": "0528", "title": "格拉斯哥大学", "points": ["University of Glasgow"]},
    {"day": "0528", "title": "简短午餐", "points": ["Ashton Lane"]},
    {"day": "0528", "title": "前往会场", "points": ["Ashton Lane", "Scottish Event Campus"]},
    {"day": "0528", "title": "Riverside Museum", "points": ["Riverside Museum"]},
    {"day": "0528", "title": "庆祝晚餐", "points": ["Merchant City"]},
    {"day": "0528", "title": "晚间活动", "points": ["Theatre Royal"]},
]

LOCATION_OVERRIDES: dict[str, str] = {
    "GLA": "Glasgow Airport",
    "city centre": PLACE_QUERIES["George Square"],
    "City Centre": PLACE_QUERIES["George Square"],
    "East End": "Glasgow Cathedral",
    "Near Cathedral": "Glasgow Necropolis",
    "Cathedral precinct": "St Mungo Museum of Religious Life and Art, Glasgow",
    "St Mungo Museum of Religious Life and Art, Glasgow": "55.862533,-4.236453|St Mungo Museum of Religious Life and Art",
    "Clyde Riverside": "Riverside Museum, Glasgow",
    "Riverside": "Riverside Museum, Glasgow",
    "SEC": "Scottish Event Campus, Glasgow",
    "Venue": "Scottish Event Campus, Glasgow",
    "Exhibit Hall": "Scottish Event Campus, Glasgow",
    "Alsh 2": "Scottish Event Campus, Glasgow",
    "Near Clyde": "Clyde Arc, Glasgow",
    "West End": "University of Glasgow",
    "University of Glasgow": PLACE_QUERIES["University of Glasgow"],
    "Old Town": "Edinburgh Old Town",
    "Royal Mile": "Royal Mile, Edinburgh",
    "Royal Mile / Victoria Street": "Victoria Street, Edinburgh",
    "St Giles' Cathedral": PLACE_QUERIES["St Giles' Cathedral"],
    "The Real Mary King's Close": PLACE_QUERIES["The Real Mary King's Close"],
    "Victoria Street / West Bow / Museum Context": PLACE_QUERIES["Victoria Street Edinburgh"],
    "Greyfriars Bobby / Greyfriars Kirkyard": PLACE_QUERIES["Greyfriars Kirkyard Edinburgh"],
    "National Museum of Scotland / Princes Street": PLACE_QUERIES["National Museum of Scotland"],
    "Howies Waterloo Place / Waverley area": PLACE_QUERIES["Howies Waterloo Place"],
    "Canongate": "Canongate, Edinburgh",
    "Edinburgh city centre": "Makars Mash Bar Edinburgh",
    "The Vennel Edinburgh": PLACE_QUERIES["The Vennel Edinburgh"],
    "Princes Street Edinburgh": "Scott Monument Edinburgh",
    "York city centre": "York Minster",
    "York Minster area": "York Minster",
    "York old town": "The Shambles, York",
    "York riverside": "Ouse Bridge, York",
    "Near York station": "York Railway Station",
    "Buchanan Bus Station": PLACE_QUERIES["Buchanan Bus Station"],
    "Cumbrae Slip": PLACE_QUERIES["Cumbrae Slip Ferry Terminal"],
    "Largs": PLACE_QUERIES["Largs waterfront"],
    "Largs Railway Station": PLACE_QUERIES["Largs Railway Station"],
    "Largs Ferry Terminal": PLACE_QUERIES["Largs Ferry Terminal"],
    "Millport Isle of Cumbrae": PLACE_QUERIES["Millport"],
    "Millport Promenade": PLACE_QUERIES["Millport Promenade"],
    "Mapes of Millport": PLACE_QUERIES["Mapes of Millport"],
    "York": "York Railway Station",
    "Glasgow": "Aparthotel Adagio Glasgow Central",
    "Scottish Highlands": "Glencoe, Scotland",
}


@dataclass
class Day:
    id: str
    short: str
    label: str
    title: str
    items: list["Item"]


@dataclass
class Item:
    time: str
    title: str
    location: str
    notes: str = ""
    route_origin: str = ""
    route_dest: str = ""


@dataclass
class RoutePoint:
    phase: str
    name: str
    query: str
    time: str
    title: str
    original_location: str
    lat: float
    lon: float


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-geocode", action="store_true", help="Use cache only; do not query Nominatim.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = load_cache()
    days = sorted(parse_days(HTML_PATH.read_text(encoding="utf-8")), key=lambda day: day.short)
    unresolved: list[dict[str, str]] = []

    for day in days:
        phase_points: dict[str, list[RoutePoint]] = {phase: [] for phase in PHASE_ORDER}
        for item in day.items:
            phase = get_day_part(item.time)
            for name, query in item_route_points(item, day):
                geocoded = geocode(query, cache, skip=args.skip_geocode)
                if not geocoded:
                    unresolved.append(
                        {
                            "day": day.short,
                            "phase": phase,
                            "item": item.title,
                            "point": name,
                            "query": query,
                        }
                    )
                    continue
                phase_points[phase].append(
                    RoutePoint(
                        phase=phase,
                        name=name,
                        query=query,
                        time=item.time,
                        title=item.title,
                        original_location=item.location,
                        lat=geocoded["lat"],
                        lon=geocoded["lon"],
                    )
                )

        write_kml(day, phase_points)

    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_unresolved(unresolved)


def load_cache() -> dict[str, dict[str, float | str]]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def parse_days(source: str) -> list[Day]:
    itinerary = extract_array(source, "const itinerary =")
    day_blocks = split_top_level_objects(itinerary)
    return [parse_day(block) for block in day_blocks]


def extract_array(source: str, marker: str) -> str:
    start = source.index(marker)
    start = source.index("[", start)
    end = find_matching(source, start, "[", "]")
    return source[start + 1 : end]


def extract_object_array(source: str, marker: str) -> str:
    start = source.index(marker)
    start = source.index("[", start)
    end = find_matching(source, start, "[", "]")
    return source[start + 1 : end]


def find_matching(source: str, start: int, open_char: str, close_char: str) -> int:
    depth = 0
    quote = ""
    escape = False
    for index in range(start, len(source)):
        char = source[index]
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f"No matching {close_char} for {open_char} at {start}")


def split_top_level_objects(source: str) -> list[str]:
    blocks: list[str] = []
    depth = 0
    start = -1
    quote = ""
    escape = False
    for index, char in enumerate(source):
        if quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = ""
            continue
        if char in {"'", '"', "`"}:
            quote = char
            continue
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                blocks.append(source[start : index + 1])
                start = -1
    return blocks


def parse_day(block: str) -> Day:
    items_source = extract_object_array(block, "items:")
    item_blocks = split_top_level_objects(items_source)
    return Day(
        id=read_prop(block, "id"),
        short=read_prop(block, "short"),
        label=read_prop(block, "dayLabel"),
        title=read_prop(block, "title"),
        items=[parse_item(item) for item in item_blocks],
    )


def parse_item(block: str) -> Item:
    return Item(
        time=read_prop(block, "time"),
        title=read_prop(block, "title"),
        location=read_prop(block, "location"),
        notes=read_prop(block, "notes"),
        route_origin=read_prop(block, "routeOrigin"),
        route_dest=read_prop(block, "routeDest"),
    )


def read_prop(block: str, prop: str) -> str:
    match = re.search(rf"\b{re.escape(prop)}\s*:\s*(['\"])(.*?)\1", block, re.S)
    if not match:
        return ""
    return match.group(2).replace('\\"', '"').replace("\\'", "'").strip()


def item_route_points(item: Item, day: Day) -> list[tuple[str, str]]:
    override = item_point_override(item, day)
    if override:
        return override
    if item.route_origin and item.route_dest:
        return [
            route_point(item.route_origin, day),
            route_point(item.route_dest, day),
        ]
    if "->" in item.location:
        parts = [part.split("/")[0].strip() for part in item.location.split("->")]
        return [
            route_point(parts[0], day),
            route_point(parts[-1], day),
        ]
    return [route_point(item.location.split("/")[0].strip(), day)]


def item_point_override(item: Item, day: Day) -> list[tuple[str, str]] | None:
    for rule in ITEM_POINT_OVERRIDES:
        if rule["day"] == day.id and str(rule["title"]) in item.title:
            return [named_point(point_name) for point_name in rule["points"]]
    return None


def named_point(name: object) -> tuple[str, str]:
    display_name = str(name)
    return display_name, PLACE_QUERIES.get(display_name, display_name)


def route_point(raw: str, day: Day) -> tuple[str, str]:
    name = clean_point_name(raw)
    query_base = LOCATION_OVERRIDES.get(name, name)
    query_base = LOCATION_OVERRIDES.get(query_base, query_base)
    display_name = point_display_name(name, query_base)
    lower = query_base.lower()
    if is_coordinate_override(query_base):
        query = query_base
    elif any(anchor in lower for anchor in ["glasgow", "gla", "edinburgh", "york", "scotland", "uk"]):
        query = query_base
    elif day.id == "0524":
        query = f"{query_base}, North Ayrshire, Scotland, UK"
    elif day.id == "0527":
        query = f"{query_base}, Edinburgh, UK"
    elif day.id == "0526":
        query = f"{query_base}, Scotland, UK"
    else:
        query = f"{query_base}, Glasgow, UK"
    return display_name, query


def point_display_name(original: str, query_base: str) -> str:
    literal = coordinate_override(query_base)
    if literal and literal.get("display_name"):
        return str(literal["display_name"])
    if original in LOCATION_OVERRIDES:
        return clean_point_name(LOCATION_OVERRIDES[original].split(",", 1)[0])
    return original


def clean_point_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value or "Unknown point"


def get_day_part(time_value: str) -> str:
    lower = time_value.lower()
    match = re.search(r"(\d{1,2}):(\d{2})", lower)
    if not match:
        if "evening" in lower or "after" in lower:
            return "晚上"
        return "其他"
    hour = int(match.group(1))
    if hour < 5:
        return "晚上"
    if hour < 12:
        return "上午"
    if hour < 18:
        return "下午"
    return "晚上"


def geocode(query: str, cache: dict[str, dict[str, float | str]], skip: bool) -> dict[str, float] | None:
    literal = coordinate_override(query)
    if literal:
        cache[query] = literal
        return {"lat": float(literal["lat"]), "lon": float(literal["lon"])}
    if query in cache:
        cached = cache[query]
        if "lat" in cached and "lon" in cached:
            return {"lat": float(cached["lat"]), "lon": float(cached["lon"])}
        return None
    if skip:
        return None

    params = urllib.parse.urlencode({"q": query, "format": "jsonv2", "limit": 1})
    request = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/search?{params}",
        headers={"User-Agent": "2026-Glasgow-KML-generator/1.0 (local itinerary planning)"},
    )
    time.sleep(1.1)
    with urllib.request.urlopen(request, timeout=30) as response:
        results = json.loads(response.read().decode("utf-8"))
    if not results:
        cache[query] = {"status": "unresolved"}
        return None
    result = results[0]
    cache[query] = {
        "lat": float(result["lat"]),
        "lon": float(result["lon"]),
        "display_name": result.get("display_name", ""),
        "source": "Nominatim",
    }
    return {"lat": float(result["lat"]), "lon": float(result["lon"])}


def is_coordinate_override(query: str) -> bool:
    return bool(re.match(r"^-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?(?:\|.+)?$", query))


def coordinate_override(query: str) -> dict[str, float | str] | None:
    if not is_coordinate_override(query):
        return None
    coords, _, label = query.partition("|")
    lat, lon = coords.split(",", 1)
    return {
        "lat": float(lat),
        "lon": float(lon),
        "display_name": label or "Manual coordinate override",
        "source": "manual override",
    }


def write_kml(day: Day, phase_points: dict[str, list[RoutePoint]]) -> None:
    numbered_points = numbered_day_points(phase_points)
    ensure_number_icons(len(numbered_points))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "  <Document>",
        f"    <name>{xml(day.short)}｜{xml(day.title)}</name>",
        f"    <description>{xml(day.short)} {xml(day.label)} {xml(day.title)}，由 pages/plan-a-cn.html 自动生成。</description>",
    ]
    for number, _, _ in numbered_points:
        icon_url = f"{ICON_URL_BASE}/{number:02d}.png"
        lines.extend(
            [
                f'    <Style id="number-{number:02d}-point">',
                "      <IconStyle>",
                "        <scale>1.15</scale>",
                f"        <Icon><href>{xml(icon_url)}</href></Icon>",
                "      </IconStyle>",
                "      <LabelStyle><scale>0.8</scale></LabelStyle>",
                "    </Style>",
            ]
        )
    for phase in PHASE_ORDER:
        style = PHASE_STYLES[phase]
        lines.extend(
            [
                f'    <Style id="{phase}-line">',
                "      <LineStyle>",
                f"        <color>{style['line']}</color>",
                "        <width>4</width>",
                "      </LineStyle>",
                "    </Style>",
            ]
        )
    for number, phase, point in numbered_points:
        label = f"{number:02d}｜{phase}｜{point.name}"
        lines.extend(
            [
                "    <Placemark>",
                f"      <name>{xml(label)}</name>",
                f"      <description>{xml(point.time)}｜{xml(point.title)}｜{xml(point.original_location)}</description>",
                f"      <styleUrl>#number-{number:02d}-point</styleUrl>",
                "      <Point>",
                f"        <coordinates>{point.lon:.7f},{point.lat:.7f},0</coordinates>",
                "      </Point>",
                "    </Placemark>",
            ]
        )
    for phase in PHASE_ORDER:
        points = dedupe_route_points(phase_points.get(phase, []))
        if len(points) >= 2:
            coordinates = " ".join(f"{point.lon:.7f},{point.lat:.7f},0" for point in points)
            lines.extend(
                [
                    "    <Placemark>",
                    f"      <name>{xml(day.short)}｜{phase}动线</name>",
                    f"      <styleUrl>#{phase}-line</styleUrl>",
                    "      <LineString>",
                    "        <tessellate>1</tessellate>",
                    f"        <coordinates>{coordinates}</coordinates>",
                    "      </LineString>",
                    "    </Placemark>",
                ]
            )
    lines.extend(["  </Document>", "</kml>", ""])
    output = OUT_DIR / f"plan-a-cn-{day.id}.kml"
    output.write_text("\n".join(lines), encoding="utf-8")


def numbered_day_points(phase_points: dict[str, list[RoutePoint]]) -> list[tuple[int, str, RoutePoint]]:
    numbered: list[tuple[int, str, RoutePoint]] = []
    next_number = 1
    last_key: tuple[float, float] | None = None
    for phase in PHASE_ORDER:
        for point in dedupe_route_points(phase_points.get(phase, [])):
            key = (round(point.lat, 6), round(point.lon, 6))
            if key == last_key:
                continue
            numbered.append((next_number, phase, point))
            next_number += 1
            last_key = key
    return numbered


def ensure_number_icons(count: int) -> None:
    if count <= 0:
        return
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return

    ICON_DIR.mkdir(parents=True, exist_ok=True)
    font = load_icon_font(ImageFont)
    for number in range(1, count + 1):
        icon_path = ICON_DIR / f"{number:02d}.png"
        if icon_path.exists():
            continue
        image = Image.new("RGBA", (96, 120), (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        fill = (246, 188, 52, 255)
        outline = (92, 74, 26, 255)
        draw.ellipse((14, 8, 82, 76), fill=fill, outline=outline, width=4)
        draw.polygon([(25, 60), (71, 60), (48, 114)], fill=fill, outline=outline)
        draw.line([(25, 60), (48, 114), (71, 60)], fill=outline, width=4, joint="curve")
        text = str(number)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        draw.text(
            ((96 - text_width) / 2, 40 - text_height / 2 - bbox[1]),
            text,
            fill=(25, 25, 25, 255),
            font=font,
        )
        image.save(icon_path)


def load_icon_font(image_font_module):
    font_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/Arial.ttf"),
    ]
    for font_path in font_candidates:
        if font_path.exists():
            return image_font_module.truetype(str(font_path), 34)
    return image_font_module.load_default()


def dedupe_route_points(points: Iterable[RoutePoint]) -> list[RoutePoint]:
    deduped: list[RoutePoint] = []
    for point in points:
        key = (round(point.lat, 6), round(point.lon, 6))
        last = deduped[-1] if deduped else None
        last_key = (round(last.lat, 6), round(last.lon, 6)) if last else None
        if key != last_key:
            deduped.append(point)
    return deduped


def write_unresolved(unresolved: list[dict[str, str]]) -> None:
    if not unresolved:
        UNRESOLVED_PATH.write_text(
            "# 待确认地点\n\n当前没有未解析地点。\n",
            encoding="utf-8",
        )
        return
    lines = ["# 待确认地点", "", "以下地点未能自动解析到坐标，导入 My Maps 前建议手动确认：", ""]
    for item in unresolved:
        lines.append(f"- {item['day']}｜{item['phase']}｜{item['item']}｜{item['point']}｜查询：`{item['query']}`")
    lines.append("")
    UNRESOLVED_PATH.write_text("\n".join(lines), encoding="utf-8")


def xml(value: str) -> str:
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    main()
