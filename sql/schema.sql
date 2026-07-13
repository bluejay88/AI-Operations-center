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

create table if not exists operator_requests (
    id bigserial primary key,
    title text not null,
    request_body text not null,
    requester text not null default 'owner',
    target_machine_id text,
    target_agent_id text,
    priority integer not null default 70,
    status text not null default 'queued',
    delivery_methods jsonb not null default '["dashboard"]',
    output_format text not null default 'dashboard',
    due_at timestamptz,
    routed_task_ids jsonb not null default '[]',
    response_summary text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_operator_requests_status_priority on operator_requests(status, priority desc, created_at desc);

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

create table if not exists approval_requests (
    id bigserial primary key,
    title text not null,
    request_type text not null,
    requester_machine_id text,
    requester_agent_id text,
    risk_level text not null default 'medium',
    status text not null default 'pending',
    summary text not null,
    proposed_changes text not null,
    audit_feedback text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    reviewed_at timestamptz,
    approved_at timestamptz,
    deployed_at timestamptz,
    updated_at timestamptz not null default now()
);

create index if not exists idx_approval_requests_status_time on approval_requests(status, created_at desc);
create index if not exists idx_approval_requests_requester on approval_requests(requester_machine_id, requester_agent_id);

create table if not exists approval_events (
    id bigserial primary key,
    approval_request_id bigint not null references approval_requests(id) on delete cascade,
    event_type text not null,
    actor text not null default 'brain-gaming-pc',
    message text not null,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_approval_events_request_time on approval_events(approval_request_id, created_at desc);

create table if not exists integration_runs (
    id bigserial primary key,
    provider text not null,
    purpose text not null,
    status text not null default 'created',
    request_body text not null,
    response_body text,
    task_id bigint references tasks(id) on delete set null,
    approval_request_id bigint references approval_requests(id) on delete set null,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    completed_at timestamptz
);

create index if not exists idx_integration_runs_provider_time on integration_runs(provider, created_at desc);

create table if not exists listener_events (
    id bigserial primary key,
    source_type text not null default 'machine',
    source_id text not null,
    event_type text not null,
    subject text not null,
    body text not null,
    priority integer not null default 50,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    processed_at timestamptz
);

create index if not exists idx_listener_events_type_time on listener_events(event_type, created_at desc);
create index if not exists idx_listener_events_source_time on listener_events(source_id, created_at desc);

create table if not exists speaker_messages (
    id bigserial primary key,
    target_type text not null default 'machine',
    target_id text not null,
    message_type text not null,
    subject text not null,
    body text not null,
    priority integer not null default 50,
    status text not null default 'pending',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    delivered_at timestamptz,
    acknowledged_at timestamptz
);

create index if not exists idx_speaker_messages_target_status on speaker_messages(target_id, status, priority desc, created_at desc);

create table if not exists users (
    id text primary key,
    display_name text not null,
    role text not null default 'owner',
    email text,
    status text not null default 'active',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists projects (
    id text primary key,
    name text not null,
    project_type text not null default 'general',
    status text not null default 'active',
    current_owner_agent_id text,
    current_owner_machine_id text,
    progress integer not null default 0,
    estimated_completion timestamptz,
    risk_score integer not null default 50,
    cost_estimate numeric(14, 2) not null default 0,
    quality_score integer not null default 50,
    test_coverage numeric(6, 2) not null default 0,
    outstanding_blockers jsonb not null default '[]',
    goals jsonb not null default '[]',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table projects add column if not exists revenue_target numeric(14, 2);

create index if not exists idx_projects_status_risk on projects(status, risk_score desc);

create table if not exists project_phases (
    id bigserial primary key,
    project_id text not null references projects(id) on delete cascade,
    phase_name text not null,
    owner_agent_id text,
    owner_machine_id text,
    status text not null default 'queued',
    progress integer not null default 0,
    due_at timestamptz,
    quality_gate text not null default 'brain-review',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(project_id, phase_name)
);

create index if not exists idx_project_phases_project_status on project_phases(project_id, status);

create table if not exists project_notes (
    id bigserial primary key,
    project_id text references projects(id) on delete cascade,
    note_type text not null,
    title text not null,
    body text not null,
    source text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_project_notes_project_type on project_notes(project_id, note_type, created_at desc);

create table if not exists documents (
    id bigserial primary key,
    project_id text references projects(id) on delete set null,
    title text not null,
    document_type text not null,
    path text,
    status text not null default 'draft',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists git_repositories (
    id bigserial primary key,
    project_id text references projects(id) on delete set null,
    name text not null,
    remote_url text not null,
    default_branch text not null default 'master',
    status text not null default 'active',
    last_seen_commit text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(remote_url)
);

create table if not exists knowledge_items (
    id bigserial primary key,
    project_id text references projects(id) on delete set null,
    domain text not null,
    title text not null,
    body text not null,
    confidence integer not null default 70,
    source text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_knowledge_items_domain_project on knowledge_items(domain, project_id, created_at desc);

create table if not exists prompts (
    id bigserial primary key,
    name text not null,
    owner_agent_id text,
    purpose text not null,
    prompt_text text not null,
    version integer not null default 1,
    status text not null default 'active',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique(name, version)
);

create table if not exists work_logs (
    id bigserial primary key,
    project_id text references projects(id) on delete set null,
    task_id bigint references tasks(id) on delete set null,
    machine_id text,
    agent_id text,
    work_type text not null,
    summary text not null,
    status text not null default 'logged',
    quality_score integer,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_work_logs_project_time on work_logs(project_id, created_at desc);

create table if not exists kpis (
    id bigserial primary key,
    metric_date date not null default current_date,
    domain text not null,
    name text not null,
    value numeric(14, 2) not null,
    unit text not null default 'count',
    target numeric(14, 2),
    source text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    unique(metric_date, domain, name)
);

create table if not exists customers (
    id bigserial primary key,
    name text not null,
    status text not null default 'lead',
    email text,
    company text,
    segment text,
    satisfaction_score integer,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists products (
    id bigserial primary key,
    name text not null,
    product_type text not null,
    status text not null default 'idea',
    price numeric(12, 2),
    recurring_price numeric(12, 2),
    owner_agent_id text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists finances (
    id bigserial primary key,
    metric_date date not null default current_date,
    category text not null,
    name text not null,
    amount numeric(14, 2) not null,
    status text not null default 'recorded',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create table if not exists notifications (
    id bigserial primary key,
    recipient text not null,
    channel text not null,
    subject text not null,
    body text not null,
    status text not null default 'draft',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    sent_at timestamptz
);

alter table notifications add column if not exists priority integer not null default 50;
alter table notifications add column if not exists category text not null default 'general';
alter table notifications add column if not exists project_id text;
alter table notifications add column if not exists eta_at timestamptz;
alter table notifications add column if not exists actions jsonb not null default '[]';
alter table notifications add column if not exists acknowledged_at timestamptz;
alter table notifications add column if not exists snoozed_until timestamptz;

create table if not exists remote_operation_requests (
    id bigserial primary key,
    machine_id text not null references machines(id),
    requested_by text not null default 'brain-gaming-pc',
    operation_type text not null,
    command_summary text not null,
    approval_policy text not null default 'preapproved',
    status text not null default 'queued',
    priority integer not null default 50,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    approved_at timestamptz,
    completed_at timestamptz,
    updated_at timestamptz not null default now()
);

create index if not exists idx_remote_operation_requests_machine_status on remote_operation_requests(machine_id, status, priority desc);

create table if not exists resource_recommendations (
    id bigserial primary key,
    machine_id text references machines(id),
    recommendation_type text not null,
    priority integer not null default 50,
    summary text not null,
    rationale text not null,
    metadata jsonb not null default '{}',
    status text not null default 'open',
    created_at timestamptz not null default now(),
    resolved_at timestamptz
);

create index if not exists idx_resource_recommendations_status_priority on resource_recommendations(status, priority desc, created_at desc);

create table if not exists workstation_updates (
    id bigserial primary key,
    machine_id text not null references machines(id),
    agent_id text references agents(id),
    project_id text,
    task_id bigint references tasks(id) on delete set null,
    update_type text not null,
    priority integer not null default 50,
    summary text not null,
    logs text,
    metrics jsonb not null default '{}',
    errors jsonb not null default '[]',
    recommendations jsonb not null default '[]',
    estimated_completion_at timestamptz,
    duration_ms numeric(14, 2),
    resource_consumption jsonb not null default '{}',
    outcome text,
    created_by text not null default 'workstation',
    created_at timestamptz not null default now()
);

create index if not exists idx_workstation_updates_machine_time on workstation_updates(machine_id, created_at desc);
create index if not exists idx_workstation_updates_project_task on workstation_updates(project_id, task_id, created_at desc);

create table if not exists device_telemetry (
    id bigserial primary key,
    machine_id text not null references machines(id),
    device_name text,
    hostname text,
    operating_system text,
    cpu text,
    gpu text,
    ram_mb numeric(14, 2),
    storage_free_mb numeric(14, 2),
    battery_percent numeric(6, 2),
    current_user_name text,
    network_status text,
    tailscale_status text,
    current_ai_model text,
    installed_models jsonb not null default '[]',
    active_projects jsonb not null default '[]',
    current_tasks jsonb not null default '[]',
    idle_percentage numeric(6, 2),
    temperature_c numeric(6, 2),
    load_average numeric(8, 2),
    health_score integer,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_device_telemetry_machine_time on device_telemetry(machine_id, created_at desc);

create table if not exists security_events (
    id bigserial primary key,
    event_type text not null,
    severity text not null default 'info',
    source text not null,
    subject text not null,
    body text not null,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_security_events_severity_time on security_events(severity, created_at desc);

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

create index if not exists idx_audit_logs_entity_time on audit_logs(entity_type, entity_id, created_at desc);

create table if not exists ai_metrics (
    id bigserial primary key,
    provider text not null,
    model text,
    agent_id text,
    tokens_input integer not null default 0,
    tokens_output integer not null default 0,
    inference_ms numeric(14, 2),
    quality_score integer,
    success boolean not null default true,
    cost_estimate numeric(14, 4) not null default 0,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_ai_metrics_provider_time on ai_metrics(provider, created_at desc);

create table if not exists model_solution_packets (
    id bigserial primary key,
    purpose text not null,
    requester text not null default 'brain-gaming-pc',
    target_id text not null default 'brain-gaming-pc',
    project_id text references projects(id) on delete set null,
    task_id bigint references tasks(id) on delete set null,
    status text not null default 'created',
    risk_level text not null default 'low',
    prompt text not null,
    provider_results jsonb not null default '[]',
    synthesized_response text not null,
    created_task_ids jsonb not null default '[]',
    approval_request_id bigint references approval_requests(id) on delete set null,
    listener_event_id bigint references listener_events(id) on delete set null,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_model_solution_packets_status_time on model_solution_packets(status, created_at desc);
create index if not exists idx_model_solution_packets_project_time on model_solution_packets(project_id, created_at desc);

create table if not exists backups (
    id bigserial primary key,
    backup_type text not null,
    status text not null default 'unknown',
    target text not null,
    verified_at timestamptz,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);
