#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


@dataclass(frozen=True)
class EmissionStat:
    netuid: int
    avg_daily_emission_tao: float  # 14d average per day


def select_top_n_by_emission(stats: Sequence[EmissionStat], n: int = 20) -> List[EmissionStat]:
    sorted_stats = sorted(stats, key=lambda s: s.avg_daily_emission_tao, reverse=True)
    return list(sorted_stats[:n])


def normalize_weights(top: Sequence[EmissionStat]) -> Dict[int, float]:
    denom = sum(s.avg_daily_emission_tao for s in top) or 1.0
    return {s.netuid: (s.avg_daily_emission_tao / denom) for s in top}


def demo_weights(n: int = 20) -> Dict[int, float]:
    # simple synthetic emissions for testing
    demo = [EmissionStat(netuid=i, avg_daily_emission_tao=float(100 - i)) for i in range(1, n + 1)]
    top = select_top_n_by_emission(demo, n)
    return normalize_weights(top)


