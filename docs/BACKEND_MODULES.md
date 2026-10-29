# Backend modules

This release keeps the presentation layer private and exposes the reproducible
backend contracts used by a local API or a separate visual client.

## Realtime Agent

`src/agent/realtime.py` defines a provider boundary and a location-first
`RealtimeWeatherAgent`. `OpenMeteoProvider` reads current temperature,
precipitation, precipitation probability, wind and humidity. An authorised CMA
adapter can implement the same `WeatherProvider.fetch()` contract. If the
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
