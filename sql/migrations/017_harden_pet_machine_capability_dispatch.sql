create table if not exists pet_machine_capability_dispatch_intents (
    request_id uuid primary key references pet_machine_capability_requests(request_id) on delete restrict,
    envelope jsonb not null check(jsonb_typeof(envelope)='object'),
    dispatched_by text not null,
    created_at timestamptz not null default now(),
    check(envelope ? 'dispatch_sha256' and envelope ? 'nonce' and envelope ? 'issued_at' and envelope ? 'expires_at')
);
create trigger trg_pet_machine_dispatch_intents_immutable before update or delete on pet_machine_capability_dispatch_intents for each row execute function reject_pet_capability_authority_mutation();

create unique index if not exists uq_pet_machine_capability_receipt_request_machine
    on pet_machine_capability_receipts(request_id, machine_id);

create table if not exists pet_machine_execution_nonces (
    machine_id text not null references machines(id) on delete restrict,
    nonce uuid not null,
    request_id uuid not null references pet_machine_capability_requests(request_id) on delete restrict,
    expires_at timestamptz not null,
    consumed_at timestamptz not null default now(),
    primary key(machine_id, nonce)
);
create trigger trg_pet_machine_execution_nonces_immutable before update or delete on pet_machine_execution_nonces for each row execute function reject_pet_capability_authority_mutation();
revoke all on table pet_machine_capability_dispatch_intents, pet_machine_execution_nonces from public;
