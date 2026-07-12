create table if not exists machines (
    id text primary key,
    name text not null,
    role text not null,
    responsibilities jsonb not null default '[]',
    capacity_weight integer not null default 1,
    services jsonb not null default '[]',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists agents (
    id text primary key,
    name text not null,
    machine_id text not null references machines(id),
    category text not null,
    mission text not null,
    cadence text not null,
    tools jsonb not null default '[]',
    guardrails jsonb not null default '[]',
    status text not null default 'active',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists tasks (
    id bigserial primary key,
    title text not null,
    agent_id text not null references agents(id),
    category text not null,
    description text not null,
    priority integer not null default 50,
    status text not null default 'queued',
    metadata jsonb not null default '{}',
    result text,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    updated_at timestamptz not null default now()
);

create index if not exists idx_tasks_status_priority on tasks(status, priority desc, created_at);
create index if not exists idx_tasks_agent on tasks(agent_id);

create table if not exists task_events (
    id bigserial primary key,
    task_id bigint not null references tasks(id) on delete cascade,
    event_type text not null,
    message text not null,
    created_at timestamptz not null default now()
);

create table if not exists revenue_ideas (
    id bigserial primary key,
    title text not null,
    owning_agent_id text references agents(id),
    offer_type text not null,
    target_customer text,
    estimated_price numeric(12, 2),
    estimated_monthly_recurring numeric(12, 2),
    confidence integer not null default 50,
    status text not null default 'proposed',
    notes text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists business_metrics (
    id bigserial primary key,
    metric_date date not null default current_date,
    name text not null,
    category text not null,
    value numeric(14, 2) not null,
    unit text not null default 'count',
    source text,
    created_at timestamptz not null default now(),
    unique(metric_date, name, category)
);

create table if not exists reports (
    id bigserial primary key,
    report_type text not null,
    title text not null,
    body text not null,
    created_at timestamptz not null default now()
);

create table if not exists machine_heartbeats (
    id bigserial primary key,
    machine_id text not null references machines(id),
    status text not null default 'online',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_machine_heartbeats_machine_time on machine_heartbeats(machine_id, created_at desc);

create table if not exists machine_benchmarks (
    id bigserial primary key,
    machine_id text not null references machines(id),
    hostname text,
    platform text,
    cpu_count integer,
    cpu_score numeric(14, 2),
    memory_total_mb numeric(14, 2),
    memory_available_mb numeric(14, 2),
    disk_free_mb numeric(14, 2),
    disk_write_mb_s numeric(14, 2),
    brain_latency_ms numeric(14, 2),
    docker_available boolean not null default false,
    python_version text,
    raw jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_machine_benchmarks_machine_time on machine_benchmarks(machine_id, created_at desc);

create table if not exists files_index (
    id bigserial primary key,
    machine_id text references machines(id),
    path text not null,
    classification text,
    checksum text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(machine_id, path)
);

create table if not exists external_accounts (
    id bigserial primary key,
    provider text not null,
    account_label text not null,
    access_level text not null default 'read-only',
    status text not null default 'not_connected',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(provider, account_label)
);

create table if not exists system_state (
    key text primary key,
    value jsonb not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
