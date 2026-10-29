# Live data access and provenance

## CMA radar

The official [CMA radar data service](https://k.data.cma.cn/mekb/?r=radar%2Fdata)
catalogues quality-controlled radar image and grid products. The network
composite reflectivity product (`J.0019.0010.S001`) and network base
reflectivity product (`J.0017.0010.S001`) are near-real-time products with a
six-minute update interval and 0.01-degree catalogue resolution. The catalogue
requires personal or institutional real-name access.

For quantitative use, obtain the account-specific file-information endpoint or
SDK credentials from the logged-in CMA data service. The service may first
return a file URL; the client then downloads and validates the file. The
`CmaRadarAdapter` accepts a JSON envelope with `values`/`reflectivity`, a CMA
file-information envelope (`DS`/`fileInfos` with `FILE_URL`), or an NPY/NPZ
volume. Set `CMA_RADAR_DATA_CODE`, `CMA_RADAR_TIME_RANGE`, and optionally
`CMA_RADAR_STATION_IDS` when the account endpoint follows the official
`getRadaFileByTimeRange` contract. It records the product, endpoint without
query secrets, retrieval time, shape, and `label_quality`.

The public NMC radar webpage is useful for a human visual check, but it is not
used as an undocumented production scraper. This keeps the project within the
published access and copyright conditions and avoids treating a rendered image
as quantitative 3-D radar data.

## Changchun drainage observations

The [Jilin public-data portal](https://data.jl.gov.cn/) provides catalogue,
download, and interface services. Search the catalogue for `排水`, `积水`,
`内涝`, `防汛`, `泵站`, `管网`, `雨量`, and `水位`. Fine-grained municipal
network and pump data may be conditionally open or restricted. The current
adapter therefore requires an authorised endpoint or an approved CSV/JSON/
GeoJSON export instead of hard-coding a private city-system URL.

The adapter maps common fields (`纬度`, `经度`, `积水深度`, `时间`, `状态`) and
supports explicit depth units through `CHANGCHUN_DRAINAGE_DEPTH_UNIT` (`cm`,
`mm`, or `m`). It stores the source, retrieval time, observation count, cache
age, and live/cached status. A missing or expired feed is reported as
`no-configured-feed`; it is never silently converted into an observed flood.

## Runtime call

```python
from src.service import RealtimeRiskService

service = RealtimeRiskService.from_environment()
payload = service.run(43.88, 125.32)
print(payload["sources"])
```

Keep tokens in a secret manager or process environment. Do not commit a token,
municipal export, or cached observation file to the public repository.
