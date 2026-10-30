# Tianheng Streamlit MVP

Run from the repository root:

```bash
python -m streamlit run app.py
```

The default **offline demo mode** uses deterministic synthetic weather and
radar data. Turn it off only when authorised live-source environment variables
are configured. Every source is labelled `LIVE`, `CACHED`, `SYNTHETIC`, or
`UNAVAILABLE` in the UI.

The current backend is a point-based research service. This MVP therefore does
not claim to be a city-wide risk grid, an official warning publisher, or a
production 30/60/120-minute forecast system. Official warnings must remain a
separate, human-reviewed workflow.

## Public data layer

When **公开数据层** is enabled and offline mode is disabled, the cockpit fetches
Open-Meteo current and 24-hour hourly forecasts, OpenStreetMap hospital/road/
administrative layers, and Nominatim reverse geocoding. Calls use a ten-minute
cache, short timeouts, a legal User-Agent, and visible `LIVE`/`UNAVAILABLE`
states. Overpass failures fall back to the small OSM map extract API; if that
also fails, synthetic demo layers remain visible. OpenStreetMap data is
attributed under ODbL 1.0. CMA radar web pages are not scraped as quantitative
radar data.
