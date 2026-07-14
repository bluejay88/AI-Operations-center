create table if not exists pet_capability_action_receipts (
    id bigserial primary key,
    manifest_sha256 text not null references pet_capability_manifests(manifest_sha256) on delete restrict,
    action_key text not null,
    action_type text not null check (
        action_type in ('browser_navigation', 'external_navigation', 'remote_control', 'music_control', 'local_model')
    ),
    target_machine_id text not null references machines(id) on delete restrict,
    status text not null check (status in ('held', 'completed', 'failed')),
    task_id bigint references tasks(id) on delete restrict,
    listener_event_id bigint references listener_events(id) on delete restrict,
    approval_request_id bigint references approval_requests(id) on delete restrict,
    result_sha256 text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now(),
    unique (manifest_sha256, action_key),
    check (jsonb_typeof(metadata) = 'object'),
    check (result_sha256 is null or result_sha256 ~ '^[0-9a-f]{64}$')
);

create index if not exists idx_pet_capability_action_receipts_manifest
    on pet_capability_action_receipts(manifest_sha256, created_at, id);
create index if not exists idx_pet_capability_action_receipts_target
    on pet_capability_action_receipts(target_machine_id, action_type, created_at desc);

drop trigger if exists pet_capability_action_receipts_append_only on pet_capability_action_receipts;
create trigger pet_capability_action_receipts_append_only
before update or delete on pet_capability_action_receipts
for each row execute function reject_pet_capability_authority_mutation();

revoke all on table pet_capability_action_receipts from public;
revoke all on sequence pet_capability_action_receipts_id_seq from public;

comment on table pet_capability_action_receipts is
    'Append-only machine-originated receipts for browser, music, remote-control, and local-model actions. Certification correlates these receipts and approval records; caller success assertions are ignored.';
