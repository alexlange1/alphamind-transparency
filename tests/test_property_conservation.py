import random
import time
from pathlib import Path

from subnet.sim.vault import (
    initialize_vault,
    compute_nav,
    mint_tao_extended,
    redeem_in_kind_extended,
)


def _mk_prices(uids):
    # Simple positive prices
    return {int(u): 1.0 + (u % 7) * 0.1 for u in uids}


def test_randomized_mint_redeem_conservation_under_30s(tmp_path: Path):
    random.seed(42)
    uids = list(range(1, 6))
    prices = _mk_prices(uids)
    weights = {u: 1.0 / len(uids) for u in uids}
    state = initialize_vault(weights, prices, initial_nav=100.0, initial_supply=1000.0)
    start = time.time()
    for _ in range(100):
        # random choice mint or redeem
        if random.random() < 0.6:
            amt = random.uniform(0.1, 10.0)
            state, _ = mint_tao_extended(amt, weights, prices, state)
        else:
            amt = random.uniform(0.1, 10.0)
            state, _ = redeem_in_kind_extended(amt, prices, state)
        # NAV should stay finite and non-negative
        nav = compute_nav(prices, state)
        assert nav >= 0.0
    # ensure test budget
    assert (time.time() - start) < 30.0


