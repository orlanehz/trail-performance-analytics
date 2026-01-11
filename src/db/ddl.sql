-- =========================
-- Trail Performance Analytics - DDL (Postgres)
-- =========================

create table if not exists athletes (
  athlete_id bigint primary key,
  firstname text,
  lastname text,
  city text,
  country text,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  raw jsonb
);

create table if not exists strava_tokens (
  athlete_id bigint primary key references athletes(athlete_id) on delete cascade,
  access_token text,
  refresh_token text not null,
  expires_at bigint,
  scope text,
  updated_at timestamptz default now()
);

create table if not exists activities (
  activity_id bigint primary key,
  athlete_id bigint not null references athletes(athlete_id) on delete cascade,

  name text,
  sport_type text,
  start_date timestamptz,
  timezone text,

  elapsed_time int,
  moving_time int,
  distance_m double precision,
  total_elevation_gain_m double precision,

  average_speed_mps double precision,
  max_speed_mps double precision,

  average_heartrate double precision,
  max_heartrate double precision,
  average_watts double precision,
  max_watts double precision,
  average_cadence double precision,

  visibility text,
  trainer boolean,
  commute boolean,

  start_lat double precision,
  start_lng double precision,

  created_at timestamptz default now(),
  updated_at timestamptz default now(),

  raw jsonb
);

create index if not exists idx_activities_athlete_startdate
  on activities (athlete_id, start_date desc);

create table if not exists activity_streams (
  activity_id bigint references activities(activity_id) on delete cascade,
  stream_type text not null,
  resolution text,
  series jsonb not null,
  created_at timestamptz default now(),
  primary key (activity_id, stream_type, resolution)
);

create table if not exists ingestion_state (
  athlete_id bigint references athletes(athlete_id) on delete cascade,
  source text not null,
  key text not null,
  value text not null,
  updated_at timestamptz default now(),
  primary key (athlete_id, source, key)
);

create table if not exists activity_enrichment_status (
  activity_id bigint primary key references activities(activity_id) on delete cascade,
  detailed_fetched_at timestamptz,
  streams_fetched_at timestamptz,
  last_error text
);
