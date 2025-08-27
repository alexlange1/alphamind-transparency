#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple


@dataclass(frozen=True)
class WeightedValue:
    value: float
    weight: float


def stake_weighted_median(values: Sequence[WeightedValue]) -> float:
    if not values:
        return 0.0
    # Sort by value
    sorted_vals = sorted(values, key=lambda x: x.value)
    total_w = sum(v.weight for v in sorted_vals)
    if total_w <= 0:
        return sorted_vals[len(sorted_vals) // 2].value
    cum = 0.0
    midpoint = total_w / 2.0
    for v in sorted_vals:
        cum += v.weight
        if cum >= midpoint:
            return v.value
    return sorted_vals[-1].value


def aggregate_map_median(m: Dict[int, Sequence[WeightedValue]]) -> Dict[int, float]:
    # For each key (e.g., netuid), compute the stake-weighted median of submitted values
    result: Dict[int, float] = {}
    for key, entries in m.items():
        result[key] = stake_weighted_median(entries)
    return result


