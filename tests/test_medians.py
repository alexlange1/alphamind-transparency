from subnet.tao20.consensus import WeightedValue, stake_weighted_median


def test_stake_weighted_median_prices():
    vals = [WeightedValue(10.0, 1.0), WeightedValue(10.1, 2.0), WeightedValue(12.0, 0.1)]
    m = stake_weighted_median(vals)
    assert 10.0 <= m <= 10.2


def test_stake_weighted_median_emissions():
    vals = [WeightedValue(100.0, 100.0), WeightedValue(50.0, 1.0), WeightedValue(1000.0, 0.1)]
    m = stake_weighted_median(vals)
    assert 95.0 <= m <= 105.0


