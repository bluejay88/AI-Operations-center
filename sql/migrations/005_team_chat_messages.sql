create table if not exists team_chat_messages (
    id bigserial primary key,
    channel text not null default 'operations',
    thread_key text not null default 'global',
    actor_type text not null,
    actor_id text not null,
    machine_id text references machines(id) on delete set null,
    agent_id text references agents(id) on delete set null,
    model_provider text,
    model_name text,
    message_type text not null default 'update',
    priority integer not null default 50,
    task_id bigint references tasks(id) on delete set null,
    project_id text,
    subject text not null,
    body text not null,
    decision text,
    direction text,
    confidence integer,
    visibility text not null default 'internal',
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_team_chat_channel_time
    on team_chat_messages(channel, created_at desc);

create index if not exists idx_team_chat_thread_time
    on team_chat_messages(thread_key, created_at desc);

create index if not exists idx_team_chat_machine_time
    on team_chat_messages(machine_id, created_at desc);

create index if not exists idx_team_chat_task_time
    on team_chat_messages(task_id, created_at desc);
