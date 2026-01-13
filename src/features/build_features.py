import os
import psycopg
from dotenv import load_dotenv

def must_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v

FEATURE_SQL = """
with base as (
  select
    activity_id,
    athlete_id,
    start_date,
    moving_time as moving_time_s,
    distance_m,
    total_elevation_gain_m as elevation_gain_m,
    average_heartrate as avg_hr,
    max_heartrate as max_hr,
    average_watts as avg_watts,
    max_watts as max_watts
  from activities
  where start_date is not null
),
feat as (
  select
    b.*,
    case
      when b.distance_m is not null and b.distance_m > 0 and b.moving_time_s is not null
      then (b.moving_time_s::double precision) / (b.distance_m/1000.0)
      else null
    end as pace_s_per_km,

    case
      when b.distance_m is not null and b.distance_m > 0 and b.elevation_gain_m is not null
      then (b.elevation_gain_m::double precision) / (b.distance_m/1000.0)
      else null
    end as elev_m_per_km,

    case
      when b.avg_hr is not null and b.moving_time_s is not null
      then b.avg_hr * b.moving_time_s
      else null
    end as hr_x_time,

    -- Rolling windows par athlète (7 jours et 28 jours)
    sum(b.distance_m) over (
      partition by b.athlete_id
      order by b.start_date
      range between interval '7 days' preceding and current row
    ) as dist_7d_m,

    sum(b.elevation_gain_m) over (
      partition by b.athlete_id
      order by b.start_date
      range between interval '7 days' preceding and current row
    ) as elev_7d_m,

    sum(b.moving_time_s) over (
      partition by b.athlete_id
      order by b.start_date
      range between interval '7 days' preceding and current row
    ) as time_7d_s,

    sum(b.distance_m) over (
      partition by b.athlete_id
      order by b.start_date
      range between interval '28 days' preceding and current row
    ) as dist_28d_m,

    sum(b.elevation_gain_m) over (
      partition by b.athlete_id
      order by b.start_date
      range between interval '28 days' preceding and current row
    ) as elev_28d_m,

    sum(b.moving_time_s) over (
      partition by b.athlete_id
      order by b.start_date
      range between interval '28 days' preceding and current row
    ) as time_28d_s

  from base b
)
insert into activity_features (
  activity_id, athlete_id, start_date,
  moving_time_s, distance_m, elevation_gain_m,
  pace_s_per_km, elev_m_per_km,
  avg_hr, max_hr, avg_watts, max_watts,
  hr_x_time,
  dist_7d_m, elev_7d_m, time_7d_s,
  dist_28d_m, elev_28d_m, time_28d_s,
  updated_at
)
select
  activity_id, athlete_id, start_date,
  moving_time_s, distance_m, elevation_gain_m,
  pace_s_per_km, elev_m_per_km,
  avg_hr, max_hr, avg_watts, max_watts,
  hr_x_time,
  dist_7d_m, elev_7d_m, time_7d_s,
  dist_28d_m, elev_28d_m, time_28d_s,
  now()
from feat
on conflict (activity_id) do update set
  athlete_id = excluded.athlete_id,
  start_date = excluded.start_date,
  moving_time_s = excluded.moving_time_s,
  distance_m = excluded.distance_m,
  elevation_gain_m = excluded.elevation_gain_m,
  pace_s_per_km = excluded.pace_s_per_km,
  elev_m_per_km = excluded.elev_m_per_km,
  avg_hr = excluded.avg_hr,
  max_hr = excluded.max_hr,
  avg_watts = excluded.avg_watts,
  max_watts = excluded.max_watts,
  hr_x_time = excluded.hr_x_time,
  dist_7d_m = excluded.dist_7d_m,
  elev_7d_m = excluded.elev_7d_m,
  time_7d_s = excluded.time_7d_s,
  dist_28d_m = excluded.dist_28d_m,
  elev_28d_m = excluded.elev_28d_m,
  time_28d_s = excluded.time_28d_s,
  updated_at = now();
"""

def main():
    load_dotenv()

    db_url = must_env("DATABASE_URL")
    with psycopg.connect(db_url) as conn:
        conn.execute("set timezone to 'UTC';")
        conn.execute(FEATURE_SQL)
        conn.commit()
    print("✅ activity_features updated")

if __name__ == "__main__":
    main()
