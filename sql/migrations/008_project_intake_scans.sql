create table if not exists project_intake_scans (
    id bigserial primary key,
    source text not null,
    project_count integer not null default 0,
    summary jsonb not null default '{}',
    payload jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_project_intake_scans_time on project_intake_scans(created_at desc);
create index if not exists idx_project_intake_scans_source_time on project_intake_scans(source, created_at desc);
