#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple
from decimal import Decimal, getcontext
getcontext().prec = 50


@dataclass(frozen=True)
class EmissionStat:
    netuid: int
    avg_daily_emission_tao: float  # 14d average per day


def select_top_n_by_emission(stats: Sequence[EmissionStat], n: int = 20) -> List[EmissionStat]:
    sorted_stats = sorted(stats, key=lambda s: s.avg_daily_emission_tao, reverse=True)
    return list(sorted_stats[:n])


def normalize_weights(top: Sequence[EmissionStat]) -> Dict[int, float]:
    # Guard near-zero sum: caller should freeze to previous weights if empty
    denom = sum(s.avg_daily_emission_tao for s in top)
    if denom <= 1e-10:
        return {}
    dden = Decimal(str(denom))
    return {s.netuid: float(Decimal(str(s.avg_daily_emission_tao)) / dden) for s in top}

def to_bps_exact(weights: Dict[int, float], total_bps: int = 10000) -> Tuple[Dict[int, int], Dict[int, float]]:
    if not weights:
        return {}, {}
    d = {k: Decimal(str(v)) for k, v in weights.items()}
    s = sum(d.values())
    if s <= Decimal("1e-10"):
        return {}, {}
    fracs = {k: (v / s) * Decimal(total_bps) for k, v in d.items()}
    ints = {k: int(fracs[k]) for k in fracs}
    rems = {k: fracs[k] - Decimal(ints[k]) for k in fracs}
    remaining = total_bps - sum(ints.values())
    if remaining > 0:
        import heapq
        heap = [(-rems[k], k) for k in rems]
        heapq.heapify(heap)
        for _ in range(remaining):
            _, kk = heapq.heappop(heap)
            ints[kk] += 1
    assert sum(ints.values()) == total_bps
    return ints, weights


def demo_weights(n: int = 20) -> Dict[int, float]:
    # simple synthetic emissions for testing
    demo = [EmissionStat(netuid=i, avg_daily_emission_tao=float(100 - i)) for i in range(1, n + 1)]
    top = select_top_n_by_emission(demo, n)
    return normalize_weights(top)


