create table if not exists schema_migrations (
    version text primary key,
    name text not null,
    checksum text not null,
    applied_at timestamptz not null default now()
);

create table if not exists peer_requests (
    id bigserial primary key,
    from_machine_id text not null,
    to_machine_id text not null,
    requested_by text not null default 'brain-gaming-pc',
    request_type text not null,
    subject text not null,
    body text not null,
    task_id bigint references tasks(id) on delete set null,
    project_id text,
    priority integer not null default 80,
    status text not null default 'requested',
    due_at timestamptz,
    metadata jsonb not null default '{}',
    response_body text,
    artifacts jsonb not null default '[]',
    quality_score integer,
    responder_machine_id text,
    response_metadata jsonb not null default '{}',
    responded_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_peer_requests_target_status on peer_requests(to_machine_id, status, priority desc, created_at desc);
create index if not exists idx_peer_requests_source_time on peer_requests(from_machine_id, created_at desc);

alter table machines add column if not exists services jsonb not null default '[]';
alter table tasks add column if not exists metadata jsonb not null default '{}';
alter table tasks add column if not exists result text;
alter table tasks add column if not exists updated_at timestamptz not null default now();

create table if not exists audit_logs (
    id bigserial primary key,
    actor text not null,
    action text not null,
    entity_type text not null,
    entity_id text,
    summary text not null,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);
