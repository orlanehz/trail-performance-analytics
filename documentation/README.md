# 🏃‍♂️ Trail Performance Analytics
### End-to-end data science project using Strava data

## Overview
This project implements an end-to-end data pipeline to predict running pace (sec/km) using Strava activity data.  
It focuses on training load dynamics, terrain characteristics, and time-aware modeling.

---

## Data source
- Strava API (OAuth authenticated)
- Activity summary data:
  - distance
  - moving time
  - elevation gain
- Rolling training load features (7-day / 28-day windows)

Physiological streams (HR, power) are not yet included.

---

## Data pipeline
- Secure ingestion via Strava API
- Automated daily ingestion (GitHub Actions cron)
- PostgreSQL storage (Supabase)
- SQL-based feature aggregation
- Modeling-ready feature table

---

## Feature engineering
Key feature groups:
- External load: distance, elevation, duration
- Training load: rolling sums (7d / 28d)
- Load ratios: short-term vs long-term stress
- Terrain density features
- Log-transformations to reduce skew

---

## Modeling
- **Target**: `pace_s_per_km`
- **Validation**: time-based train/test split
- **Models**:
  - Baseline (mean pace)
  - Random Forest Regressor

### Performance
- MAE ≈ 36 sec/km
- RMSE ≈ 45 sec/km

The model significantly outperforms the baseline, despite the absence of physiological data.

---

## Key insights
- Recent training load explains performance better than cumulative volume
- Elevation density has a strong impact on pace
- Time-aware validation is critical to avoid leakage

---

## Limitations
- No heart rate or power streams
- No weather or surface data
- No race context or pacing strategy

---

## Future work
- Stream ingestion (HR, power, altitude)
- Cardiac drift and intensity zones
- Race time prediction
- Multi-athlete modeling

---

## Privacy & ethics
- Explicit athlete consent via Strava OAuth
- Private data usage only
- Access revocable at any time

---

## Author
**Orlane Houzet**  
Data Scientist – Marketing & Performance Analytics
