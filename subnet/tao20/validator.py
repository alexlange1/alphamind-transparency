#!/usr/bin/env python3
from __future__ import annotations

from typing import Dict, Iterable, List

from .consensus import WeightedValue, aggregate_map_median
from .models import EmissionsReport
from .index_design import EmissionStat, select_top_n_by_emission, normalize_weights


def aggregate_emissions(reports: Iterable[EmissionsReport]) -> Dict[int, float]:
    # Build per-netuid weighted value lists
    buckets: Dict[int, List[WeightedValue]] = {}
    for rep in reports:
        for netuid, val in rep.emissions_by_netuid.items():
            buckets.setdefault(netuid, []).append(WeightedValue(value=float(val), weight=max(0.0, float(rep.stake_tao))))
    return aggregate_map_median(buckets)


def compute_index_weights_from_reports(reports: Iterable[EmissionsReport], top_n: int = 20) -> Dict[int, float]:
    agg = aggregate_emissions(list(reports))
    stats = [EmissionStat(netuid=k, avg_daily_emission_tao=v) for k, v in agg.items()]
    top = select_top_n_by_emission(stats, n=top_n)
    return normalize_weights(top)


