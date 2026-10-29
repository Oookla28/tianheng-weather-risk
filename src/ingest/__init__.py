"""External data adapters for authorised CMA radar and city drainage feeds."""

from .cma_radar import CmaRadarAdapter, CmaRadarConfig, RadarFetchResult
from .changchun_drainage import (
    ChangchunDrainageAdapter,
    DrainageObservation,
    DrainageObservationBatch,
)

__all__ = [
    "CmaRadarAdapter",
    "CmaRadarConfig",
    "RadarFetchResult",
    "ChangchunDrainageAdapter",
    "DrainageObservation",
    "DrainageObservationBatch",
]
