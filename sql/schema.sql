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

create table if not exists machine_status_current (
    machine_id text primary key references machines(id),
    status text not null default 'online',
    last_seen_at timestamptz not null default now(),
    hostname text,
    tailscale_ip text,
    worker_version text,
    active_task_id bigint references tasks(id) on delete set null,
    load numeric(8, 2),
    metadata jsonb not null default '{}',
    updated_at timestamptz not null default now()
);

create index if not exists idx_machine_status_current_status_seen on machine_status_current(status, last_seen_at desc);

create table if not exists machine_links (
    id bigserial primary key,
    machine_id text not null references machines(id),
    tailscale_name text,
    tailscale_ip text,
    hostname text,
    device_fingerprint text,
    is_primary boolean not null default false,
    last_seen_at timestamptz,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(machine_id, tailscale_name, tailscale_ip)
);

create table if not exists agent_machine_assignments (
    id bigserial primary key,
    agent_id text not null references agents(id),
    machine_id text not null references machines(id),
    priority integer not null default 100,
    status text not null default 'active',
    max_concurrent_tasks integer not null default 1,
    capabilities_required jsonb not null default '[]',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(agent_id, machine_id)
);

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

create table if not exists machine_connections (
    id bigserial primary key,
    source_machine_id text not null references machines(id),
    target_machine_id text not null references machines(id),
    channel text not null,
    status text not null default 'unknown',
    latency_ms numeric(14, 2),
    last_checked_at timestamptz,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(source_machine_id, target_machine_id, channel)
);

create index if not exists idx_machine_connections_status on machine_connections(status, updated_at desc);

create table if not exists agent_messages (
    id bigserial primary key,
    source_agent_id text references agents(id),
    target_agent_id text references agents(id),
    task_id bigint references tasks(id) on delete set null,
    message_type text not null default 'status',
    subject text not null,
    body text not null,
    status text not null default 'created',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    delivered_at timestamptz,
    acknowledged_at timestamptz
);

create index if not exists idx_agent_messages_target_status on agent_messages(target_agent_id, status, created_at desc);

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

create table if not exists phoenix_events (
    id bigserial primary key,
    event_type text not null,
    subject text not null,
    body text not null,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_phoenix_events_type_time on phoenix_events(event_type, created_at desc);

create table if not exists phoenix_voice_settings (
    id text primary key default 'default',
    persona text not null default 'Phoenix',
    voice_provider text not null default 'browser-speech-synthesis',
    voice_name text,
    speaking_rate numeric(5, 2) not null default 1.00,
    pitch numeric(5, 2) not null default 1.00,
    metadata jsonb not null default '{}',
    updated_at timestamptz not null default now()
);
