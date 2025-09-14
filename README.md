# AlphaMind Transparency

This repository publishes transparent data from AlphaMind's TAO20 index fund operations.

## Purpose

This repository serves as the public transparency portal for:
- **Daily Emissions**: Subnet emission rates collected from Bittensor network
- **TAO20 Composition**: Bi-weekly portfolio weights for the TAO20 index

## Data Sources

All data is automatically collected and processed on VPS `138.68.69.71` and published here for public transparency.

## Data Structure

### Daily Emissions (`/data/emissions/`)
- **File**: `emissions_YYYYMMDD.json` 
- **Schedule**: Daily at 16:00 UTC
- **Content**: Emission rates for all active Bittensor subnets
- **Format**: Decimal values (e.g., 0.098567 = 9.8567%)

### TAO20 Portfolio (`/data/tao20/`)
- **File**: `tao20_YYYYMMDD.json`
- **Schedule**: Bi-weekly on Sundays at 12:00 UTC
- **Content**: Top 20 subnet weights based on 14-day average emissions
- **Format**: Normalized weights summing to 1.0

## Verification

All data includes cryptographic signatures for integrity verification.

## Automation

Data collection and publishing is fully automated via:
- VPS-based collection system
- Automated GitHub publishing
- Real-time transparency updates