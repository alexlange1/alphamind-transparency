# AlphaMind Transparency

This repository publishes transparent data for AlphaMind's TAO20 index fund.

## Data Structure

### Daily Emissions (`/emissions/`)
- **File**: `emissions_YYYYMMDD.json` 
- **Schedule**: Daily
- **Content**: Emission rates for all active Bittensor subnets

### TAO20 Portfolio (`/tao20/`)
- **File**: `tao20_YYYYMMDD.json`
- **Schedule**: Bi-weekly on Sundays
- **Content**: Top 20 subnet weights based on 14-day average emissions

## Data Format

All data is published in JSON format with timestamps for transparency and verification.
