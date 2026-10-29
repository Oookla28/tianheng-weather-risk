# Backend modules

This release keeps the presentation layer private and exposes the reproducible
backend contracts used by a local API or a separate visual client.

## Realtime Agent

`src/agent/realtime.py` defines a provider boundary and a location-first
`RealtimeWeatherAgent`. `OpenMeteoProvider` reads current temperature,
precipitation, precipitation probability, wind and humidity. The provider can
be replaced with an authorised CMA or SmartWeatherAPI weather adapter. If the
network is unavailable, the deterministic fallback is explicitly labelled
`synthetic` and lowers confidence; it must not be presented as an official
warning.

## Radar voxel nowcast

`src/radar/voxel.py` uses a `(time, height, y, x)` float cube. It reports
reflectivity summaries, connected convective cores and a normalized convective
score. `nowcast()` performs a transparent advection baseline on the latest
volume. A trained ConvGRU or radar extrapolation model can replace that method
without changing the downstream service contract.

## Drainage digital twin

`src/drainage/simulator.py` models effective runoff as a function of rainfall
and imperviousness, applies drainage capacity and storage, then returns storage,
overflow and flooded-area indicators per five-minute step. The
`counterfactuals()` method keeps rainfall fixed while comparing baseline,
early pumping, blocked inlets and a rainfall reduction scenario.

## Unified service

`src/service/risk_pipeline.py` composes the three modules into one serializable
response containing weather evidence, radar metadata, impact indicators and
counterfactual results. The returned payload is suitable for an API endpoint or
a private visual client; it contains no frontend code.

```python
from src.service import RealtimeRiskService

result = RealtimeRiskService().run(43.88, 125.32)
print(result["risk"]["risk_level"])
```

The baseline implementations are research and competition components. Before
operational use, replace synthetic data with authorised feeds and calibrate
against event-level local observations.

## Authorised live data configuration

The public code does not embed private credentials or an unverified municipal URL.
Configure the authorised feeds at runtime:

```bash
export CMA_RADAR_ENDPOINT='https://<authorised-cma-endpoint>'
export CMA_RADAR_TOKEN='<runtime-secret>'
export CMA_RADAR_PRODUCT='reflectivity'
export CMA_RADAR_DATA_CODE='J.0019.0010.S001'
export CMA_RADAR_TIME_RANGE='(20261030000000,20261030000600]'
export CHANGCHUN_DRAINAGE_ENDPOINT='https://<authorised-changchun-feed>'
export CHANGCHUN_DRAINAGE_TOKEN='<runtime-secret>'
export CHANGCHUN_DRAINAGE_DEPTH_UNIT='cm'
```

Then build the service with `RealtimeRiskService.from_environment()`. The CMA
adapter accepts a JSON volume, an envelope containing a download URL, or a
NumPy NPY/NPZ volume and normalises it to `(time, height, y, x)`. The drainage
adapter accepts CSV, JSON records, and GeoJSON point features, including common
Chinese field names such as `纬度`, `经度`, `积水深度`, `时间`, and `状态`.

Every response includes `sources`, `is_live`, `label_quality`, endpoint-safe
provenance, and cache age. A request failure can use an age-limited cache; if
no cache exists, the service marks the source as synthetic or unavailable. It
never reports a fallback as a live CMA or municipal observation.

The official CMA radar data service describes near-real-time, six-minute,
0.01-degree radar products with real-name access:
<https://k.data.cma.cn/mekb/?r=radar%2Fdata>. Production configuration must use
the endpoint and file URLs issued by the logged-in CMA service. The repository
does not scrape public radar webpages or hard-code undocumented tile URLs.

Changchun drainage and waterlogging observations must come from an authorised
city or Jilin public-data interface/export. The adapter does not invent a
public endpoint: municipal network, pump, inlet and observed-depth layers may
require a data-sharing application and security-approved export. Until that
authorization is granted, the service reports `no-configured-feed` and keeps
modelled drainage output separate from observed water depth.
