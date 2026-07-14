create table if not exists pet_machine_capability_requests (
    request_id uuid primary key,
    machine_id text not null references machines(id) on delete restrict,
    pet_id text not null,
    capability_type text not null check (capability_type in ('browser_navigation', 'music_playback', 'device_model_chat')),
    requester text not null check (length(btrim(requester)) > 0),
    status text not null check (status in ('requested', 'pending_approval')),
    payload jsonb not null check (jsonb_typeof(payload) = 'object'),
    approval_request_id bigint references approval_requests(id) on delete restrict,
    listener_event_id bigint not null references listener_events(id) on delete restrict,
    speaker_message_id bigint not null references speaker_messages(id) on delete restrict,
    created_at timestamptz not null default now(),
    check ((capability_type in ('browser_navigation', 'music_playback') and status = 'pending_approval' and approval_request_id is not null)
        or (capability_type = 'device_model_chat' and status = 'requested' and approval_request_id is null))
);

create index if not exists idx_pet_machine_capability_requests_target
    on pet_machine_capability_requests(machine_id, created_at desc);

drop trigger if exists trg_pet_machine_capability_requests_immutable on pet_machine_capability_requests;
create trigger trg_pet_machine_capability_requests_immutable
before update or delete on pet_machine_capability_requests
for each row execute function reject_pet_capability_authority_mutation();

revoke all on table pet_machine_capability_requests from public;
comment on table pet_machine_capability_requests is
    'Append-only audited PET requests. Rows are not execution receipts and never prove success.';
