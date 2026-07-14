create table if not exists pet_machine_capability_dispatches (
    request_id uuid primary key references pet_machine_capability_requests(request_id) on delete restrict,
    speaker_message_id bigint not null references speaker_messages(id) on delete restrict,
    envelope jsonb not null check (jsonb_typeof(envelope)='object'),
    dispatched_by text not null,
    dispatched_at timestamptz not null default now()
);
create table if not exists pet_machine_capability_receipts (
    id bigserial primary key,
    request_id uuid not null references pet_machine_capability_requests(request_id) on delete restrict,
    machine_id text not null references machines(id) on delete restrict,
    pet_id text not null,
    status text not null check(status in ('held','completed','failed')),
    detail text not null,
    receipt jsonb not null check(jsonb_typeof(receipt)='object'),
    listener_event_id bigint not null references listener_events(id) on delete restrict,
    created_at timestamptz not null default now(),
    unique(request_id, machine_id, id)
);
create trigger trg_pet_machine_dispatches_immutable before update or delete on pet_machine_capability_dispatches for each row execute function reject_pet_capability_authority_mutation();
create trigger trg_pet_machine_receipts_immutable before update or delete on pet_machine_capability_receipts for each row execute function reject_pet_capability_authority_mutation();
revoke all on table pet_machine_capability_dispatches, pet_machine_capability_receipts from public;
