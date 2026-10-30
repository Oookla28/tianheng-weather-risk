"""Low-frequency public data adapters for the frontend.

The adapters are intentionally separate from the research risk service. Public
Open-Meteo weather and OpenStreetMap overlays enrich the cockpit, while the
backend still owns model risk and authorised CMA/municipal provenance.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any
import xml.etree.ElementTree as ET


USER_AGENT = "tianheng-weather-impact-ui/0.4 (public-data-demo)"
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
NOMINATIM_ENDPOINT = "https://nominatim.openstreetmap.org/reverse"
OPEN_METEO_ENDPOINT = "https://api.open-meteo.com/v1/forecast"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _get_json(url: str, *, timeout: float = 10.0, accept_language: str | None = None) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if accept_language:
        headers["Accept-Language"] = accept_language
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _live_result(source: str, data: Any, *, license_name: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {"status": "LIVE", "source": source, "is_live": True, "retrieved_at": _now(), "data": data}
    if license_name:
        result["license"] = license_name
    return result


def _unavailable(source: str, error: str) -> dict[str, Any]:
    return {"status": "UNAVAILABLE", "source": source, "is_live": False, "retrieved_at": _now(), "error": error, "data": None}


def fetch_open_meteo(latitude: float, longitude: float, *, forecast_hours: int = 24) -> dict[str, Any]:
    """Fetch current plus hourly public weather for the selected point."""
    params = {
        "latitude": f"{latitude:.5f}",
        "longitude": f"{longitude:.5f}",
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code",
        "hourly": "temperature_2m,precipitation_probability,precipitation,wind_speed_10m,weather_code",
        "forecast_hours": str(max(1, min(forecast_hours, 48))),
        "timezone": "auto",
    }
    url = OPEN_METEO_ENDPOINT + "?" + urllib.parse.urlencode(params)
    try:
        payload = _get_json(url, timeout=8.0)
        hourly = payload.get("hourly", {})
        times = hourly.get("time", [])
        rows = []
        for index, timestamp in enumerate(times):
            rows.append(
                {
                    "time": timestamp,
                    "temperature_c": (hourly.get("temperature_2m") or [None])[index],
                    "precipitation_probability": (hourly.get("precipitation_probability") or [None])[index],
                    "precipitation_mm": (hourly.get("precipitation") or [None])[index],
                    "wind_speed_kmh": (hourly.get("wind_speed_10m") or [None])[index],
                    "weather_code": (hourly.get("weather_code") or [None])[index],
                }
            )
        return _live_result("open-meteo", {"current": payload.get("current", {}), "hourly": rows, "timezone": payload.get("timezone", "")}, license_name="CC BY 4.0")
    except Exception as exc:
        return _unavailable("open-meteo", f"{type(exc).__name__}: {exc}")


def fetch_nominatim(latitude: float, longitude: float) -> dict[str, Any]:
    """Reverse-geocode the current point using the public Nominatim API."""
    params = {"format": "jsonv2", "lat": f"{latitude:.5f}", "lon": f"{longitude:.5f}", "zoom": "10", "addressdetails": "1", "accept-language": "zh-CN,zh;q=0.9,en;q=0.5"}
    url = NOMINATIM_ENDPOINT + "?" + urllib.parse.urlencode(params)
    try:
        payload = _get_json(url, timeout=8.0, accept_language="zh-CN,zh;q=0.9,en;q=0.5")
        return _live_result("nominatim", {"display_name": payload.get("display_name", ""), "address": payload.get("address", {})}, license_name="OpenStreetMap Nominatim")
    except Exception as exc:
        return _unavailable("nominatim", f"{type(exc).__name__}: {exc}")


def _parse_overpass(payload: dict[str, Any]) -> dict[str, Any]:
    hospitals: list[dict[str, Any]] = []
    roads: list[dict[str, Any]] = []
    boundaries: list[dict[str, Any]] = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        kind = element.get("type")
        if tags.get("amenity") == "hospital":
            center = element.get("center") or {}
            lat = element.get("lat", center.get("lat"))
            lon = element.get("lon", center.get("lon"))
            if lat is not None and lon is not None:
                hospitals.append({"name": tags.get("name") or "未命名医院", "lat": float(lat), "lon": float(lon), "risk": "中", "osm_id": element.get("id")})
        elif tags.get("highway"):
            geometry = element.get("geometry") or []
            if len(geometry) >= 2:
                roads.append({"name": tags.get("name") or tags.get("ref") or "未命名道路", "highway": tags.get("highway"), "lat": [point["lat"] for point in geometry], "lon": [point["lon"] for point in geometry], "osm_id": element.get("id")})
        elif tags.get("boundary") == "administrative":
            geometry = element.get("geometry") or []
            if len(geometry) >= 2:
                boundaries.append({"name": tags.get("name") or "行政区", "admin_level": tags.get("admin_level"), "lat": [point["lat"] for point in geometry], "lon": [point["lon"] for point in geometry], "osm_id": element.get("id")})
    return {"hospitals": hospitals, "roads": roads, "boundaries": boundaries, "count": len(payload.get("elements", []))}


def _parse_osm_xml(body: bytes) -> dict[str, Any]:
    """Parse a small OSM map extract as a fallback when Overpass is busy."""
    root = ET.fromstring(body)
    nodes: dict[str, tuple[float, float, dict[str, str]]] = {}
    for node in root.findall("node"):
        tags = {str(tag.attrib.get("k")): str(tag.attrib.get("v", "")) for tag in node.findall("tag")}
        nodes[str(node.attrib["id"])] = (float(node.attrib["lat"]), float(node.attrib["lon"]), tags)
    hospitals = []
    for lat, lon, tags in nodes.values():
        if tags.get("amenity") == "hospital":
            hospitals.append({"name": tags.get("name") or "未命名医院", "lat": lat, "lon": lon, "risk": "中"})
    roads, boundaries = [], []
    for way in root.findall("way"):
        tags = {str(tag.attrib.get("k")): str(tag.attrib.get("v", "")) for tag in way.findall("tag")}
        points = [nodes[str(nd.attrib["ref"])] for nd in way.findall("nd") if str(nd.attrib["ref"]) in nodes]
        if len(points) < 2:
            continue
        if tags.get("amenity") == "hospital":
            hospitals.append({"name": tags.get("name") or "未命名医院", "lat": sum(p[0] for p in points) / len(points), "lon": sum(p[1] for p in points) / len(points), "risk": "中"})
        if tags.get("highway") in {"primary", "secondary", "tertiary", "trunk"}:
            roads.append({"name": tags.get("name") or tags.get("ref") or "未命名道路", "highway": tags.get("highway"), "lat": [p[0] for p in points], "lon": [p[1] for p in points]})
        if tags.get("boundary") == "administrative":
            boundaries.append({"name": tags.get("name") or "行政区", "admin_level": tags.get("admin_level"), "lat": [p[0] for p in points], "lon": [p[1] for p in points]})
    return {"hospitals": hospitals, "roads": roads, "boundaries": boundaries, "count": len(nodes)}


def _fetch_osm_map_api(latitude: float, longitude: float) -> dict[str, Any]:
    delta = 0.0055
    params = {"bbox": f"{longitude - delta:.5f},{latitude - delta:.5f},{longitude + delta:.5f},{latitude + delta:.5f}"}
    url = "https://api.openstreetmap.org/api/0.6/map?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml"})
    with urllib.request.urlopen(request, timeout=12.0) as response:
        parsed = _parse_osm_xml(response.read())
    return _live_result("openstreetmap-map-api", parsed, license_name="ODbL 1.0")


def fetch_osm_layers(latitude: float, longitude: float, *, radius_m: int = 4000) -> dict[str, Any]:
    """Fetch small hospital/road/admin layers from a public Overpass instance."""
    query = f"""[out:json][timeout:12];(
      node[\"amenity\"=\"hospital\"](around:{radius_m},{latitude:.5f},{longitude:.5f});
      way[\"highway\"~\"primary|secondary|tertiary\"](around:{radius_m},{latitude:.5f},{longitude:.5f});
      relation[\"boundary\"=\"administrative\"][\"admin_level\"~\"6|7|8\"](around:{radius_m},{latitude:.5f},{longitude:.5f});
    );out center geom;"""
    url = OVERPASS_ENDPOINT + "?" + urllib.parse.urlencode({"data": query})
    try:
        payload = _get_json(url, timeout=15.0)
        return _live_result("openstreetmap-overpass", _parse_overpass(payload), license_name="ODbL 1.0")
    except Exception as exc:
        try:
            fallback = _fetch_osm_map_api(latitude, longitude)
            fallback["fallback_reason"] = f"overpass unavailable: {type(exc).__name__}: {exc}"
            return fallback
        except Exception as fallback_exc:
            return _unavailable("openstreetmap-overpass", f"{type(exc).__name__}: {exc}; map-api fallback: {type(fallback_exc).__name__}: {fallback_exc}")


def fetch_public_bundle(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch all low-frequency public enrichments without failing the UI."""
    with ThreadPoolExecutor(max_workers=3) as executor:
        weather_future = executor.submit(fetch_open_meteo, latitude, longitude)
        osm_future = executor.submit(fetch_osm_layers, latitude, longitude)
        geocode_future = executor.submit(fetch_nominatim, latitude, longitude)
        weather = weather_future.result()
        osm = osm_future.result()
        geocode = geocode_future.result()
    return {"weather": weather, "osm": osm, "geocode": geocode, "retrieved_at": _now()}


__all__ = ["fetch_open_meteo", "fetch_nominatim", "fetch_osm_layers", "fetch_public_bundle"]
