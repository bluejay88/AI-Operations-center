create table if not exists ssh_broker_executions (
    execution_id uuid primary key,
    remote_operation_request_id bigint not null references remote_operation_requests(id) on delete restrict,
    approval_request_id bigint not null references approval_requests(id) on delete restrict,
    target_machine_id text not null references machines(id) on delete restrict,
    requested_by text not null,
    executed_by text not null,
    command_id text not null,
    arguments_sha256 text not null check (arguments_sha256 ~ '^[0-9a-f]{64}$'),
    envelope_sha256 text not null check (envelope_sha256 ~ '^[0-9a-f]{64}$'),
    host_key_fingerprint text not null,
    identity_public_fingerprint text not null,
    status text not null check (status in ('completed', 'failed', 'blocked', 'timed_out')),
    exit_code integer,
    output_sha256 text check (output_sha256 is null or output_sha256 ~ '^[0-9a-f]{64}$'),
    redacted_output text not null default '',
    duration_ms integer not null check (duration_ms >= 0),
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    check (jsonb_typeof(metadata) = 'object')
);

create index if not exists idx_ssh_broker_executions_target_time
    on ssh_broker_executions(target_machine_id, created_at desc);

create or replace function reject_ssh_broker_audit_mutation()
returns trigger
language plpgsql
as $$
begin
    raise exception 'SSH broker execution records are append-only' using errcode = '42501';
end;
$$;

drop trigger if exists ssh_broker_executions_append_only on ssh_broker_executions;
create trigger ssh_broker_executions_append_only
before update or delete on ssh_broker_executions
for each row execute function reject_ssh_broker_audit_mutation();

revoke all on table ssh_broker_executions from public;
revoke execute on function reject_ssh_broker_audit_mutation() from public;

comment on table ssh_broker_executions is
    'Append-only evidence for approved, signed, pinned-host, allowlisted SSH diagnostic executions.';
