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

create table if not exists activity_features (
  activity_id bigint primary key references activities(activity_id) on delete cascade,
  athlete_id bigint not null references athletes(athlete_id) on delete cascade,
  start_date timestamptz,
  moving_time_s int,
  distance_m double precision,
  elevation_gain_m double precision,
  pace_s_per_km double precision,
  elev_m_per_km double precision,
  avg_hr double precision,
  max_hr double precision,
  avg_watts double precision,
  max_watts double precision,
  hr_x_time double precision,
  dist_7d_m double precision,
  elev_7d_m double precision,
  time_7d_s double precision,
  dist_28d_m double precision,
  elev_28d_m double precision,
  time_28d_s double precision,
  updated_at timestamptz default now()
);

create index if not exists idx_activity_features_athlete_startdate
  on activity_features (athlete_id, start_date desc);

create table if not exists model_predictions (
  id bigserial primary key,
  athlete_id bigint not null,
  activity_id bigint,
  prediction_type text not null,
  predicted_pace_s_per_km double precision,
  predicted_time_s double precision,
  model_name text not null,
  model_version text not null,
  features jsonb,
  created_at timestamptz default now(),
  constraint uniq_prediction
    unique (athlete_id, activity_id, prediction_type, model_version)
);

create table if not exists app_users (
  id bigserial primary key,
  provider text not null,
  provider_user_id text not null,
  email text,
  name text,
  raw jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  constraint uniq_app_user unique (provider, provider_user_id)
);

create table if not exists oauth_tokens (
  id bigserial primary key,
  user_id bigint not null references app_users(id) on delete cascade,
  provider text not null,
  access_token text not null,
  refresh_token text,
  expires_at bigint,
  scope text,
  raw jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  constraint uniq_oauth_token unique (user_id, provider)
);
