create table if not exists pet_feature_assignments (
    id bigserial primary key,
    assignment_key text not null unique,
    target_machine_id text not null,
    assigned_agent_id text not null,
    pet_id text not null,
    task_id bigint references tasks(id) on delete set null,
    feature_ids jsonb not null,
    acceptance_rubric jsonb not null default '{}',
    status text not null default 'assigned' check (status in ('assigned', 'in_progress', 'submitted', 'accepted', 'changes_requested', 'cancelled')),
    due_at timestamptz,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (jsonb_typeof(feature_ids) = 'array' and jsonb_array_length(feature_ids) > 0),
    check (jsonb_typeof(acceptance_rubric) = 'object')
);

create index if not exists idx_pet_assignments_target_status
    on pet_feature_assignments(target_machine_id, status, due_at, created_at desc);
create index if not exists idx_pet_assignments_agent_status
    on pet_feature_assignments(assigned_agent_id, status, created_at desc);

create table if not exists pet_release_submissions (
    id bigserial primary key,
    submission_key text not null unique,
    assignment_id bigint references pet_feature_assignments(id) on delete set null,
    listener_event_id bigint references listener_events(id) on delete set null,
    approval_request_id bigint references approval_requests(id) on delete set null,
    machine_id text not null,
    agent_id text not null,
    pet_id text not null,
    task_id bigint references tasks(id) on delete set null,
    feature_ids jsonb not null,
    implementation_summary text not null,
    artifacts jsonb not null default '[]',
    performance jsonb not null default '{}',
    tests jsonb not null default '{}',
    audit jsonb not null default '{}',
    rollback_plan text not null default '',
    rubric jsonb not null default '{}',
    verification_state text not null default 'submitted_unverified'
        check (verification_state in ('submitted_unverified', 'brain_verified', 'verification_failed')),
    status text not null default 'processing'
        check (status in ('processing', 'needs_evidence', 'pending_brain_review', 'approved', 'rejected', 'deployed')),
    release_channel text not null default 'staged' check (release_channel in ('staged', 'canary', 'production')),
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (jsonb_typeof(feature_ids) = 'array' and jsonb_array_length(feature_ids) > 0),
    check (jsonb_typeof(artifacts) = 'array'),
    check (jsonb_typeof(performance) = 'object'),
    check (jsonb_typeof(tests) = 'object'),
    check (jsonb_typeof(audit) = 'object'),
    check (jsonb_typeof(rubric) = 'object')
);

create index if not exists idx_pet_submissions_machine_status
    on pet_release_submissions(machine_id, status, created_at desc);
create index if not exists idx_pet_submissions_approval
    on pet_release_submissions(approval_request_id) where approval_request_id is not null;
create index if not exists idx_pet_submissions_task
    on pet_release_submissions(task_id, created_at desc) where task_id is not null;

create table if not exists pet_performance_samples (
    id bigserial primary key,
    submission_id bigint not null references pet_release_submissions(id) on delete cascade,
    sample_key text not null,
    captured_at timestamptz not null,
    metrics jsonb not null,
    tags jsonb not null default '{}',
    created_at timestamptz not null default now(),
    unique (submission_id, sample_key),
    check (jsonb_typeof(metrics) = 'object'),
    check (jsonb_typeof(tags) = 'object')
);

create index if not exists idx_pet_performance_submission_time
    on pet_performance_samples(submission_id, captured_at desc);
create index if not exists idx_pet_performance_captured_brin
    on pet_performance_samples using brin(captured_at);

create table if not exists pet_release_decisions (
    id bigserial primary key,
    submission_id bigint not null references pet_release_submissions(id) on delete restrict,
    approval_request_id bigint references approval_requests(id) on delete restrict,
    decision text not null check (decision in ('approved', 'rejected', 'needs_changes', 'deployed')),
    actor text not null,
    feedback text not null,
    evidence jsonb not null default '{}',
    created_at timestamptz not null default now(),
    check (jsonb_typeof(evidence) = 'object')
);

create index if not exists idx_pet_decisions_submission_time
    on pet_release_decisions(submission_id, created_at desc);
create unique index if not exists idx_pet_decisions_idempotent
    on pet_release_decisions(submission_id, decision, actor, md5(evidence::text));

create or replace function reject_pet_release_decision_mutation()
returns trigger language plpgsql as $$
begin
    raise exception 'pet_release_decisions are append-only';
end;
$$;

drop trigger if exists trg_pet_release_decisions_append_only on pet_release_decisions;
create trigger trg_pet_release_decisions_append_only
before update or delete on pet_release_decisions
for each row execute function reject_pet_release_decision_mutation();

create or replace function prune_pet_performance_samples(retain_after timestamptz)
returns bigint language plpgsql as $$
declare removed bigint;
begin
    delete from pet_performance_samples where captured_at < retain_after;
    get diagnostics removed = row_count;
    return removed;
end;
$$;
