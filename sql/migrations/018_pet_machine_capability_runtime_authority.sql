-- Durable second-pass authority for PET machine execution. Migrations 001-017
-- are immutable; this migration supersedes their process-local gaps.

create table if not exists pet_machine_capability_keys (
    key_id text primary key,
    machine_id text not null references machines(id) on delete restrict,
    direction text not null check (direction in ('dispatch','receipt')),
    secret_fingerprint_sha256 text not null check (secret_fingerprint_sha256 ~ '^[0-9a-f]{64}$'),
    not_before timestamptz not null,
    not_after timestamptz not null,
    revoked_at timestamptz,
    created_by text not null,
    created_at timestamptz not null default now(),
    check (not_after > not_before),
    check (revoked_at is null or revoked_at >= not_before),
    unique(machine_id, direction, key_id)
);
create unique index if not exists uq_pet_machine_active_key_window
    on pet_machine_capability_keys(machine_id, direction)
    where revoked_at is null;

create table if not exists pet_machine_capability_key_events (
    id bigserial primary key,
    key_id text not null references pet_machine_capability_keys(key_id) on delete restrict,
    event_type text not null check (event_type in ('registered','revoked')),
    actor text not null,
    reason text not null,
    created_at timestamptz not null default now()
);
create trigger trg_pet_machine_key_events_immutable before update or delete on pet_machine_capability_key_events
    for each row execute function reject_pet_capability_authority_mutation();

create or replace function consume_pet_machine_execution_nonce(
    p_machine_id text,
    p_nonce uuid,
    p_request_id uuid,
    p_expires_at timestamptz,
    p_dispatch_sha256 text
) returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
    if p_expires_at <= clock_timestamp() or p_dispatch_sha256 !~ '^[0-9a-f]{64}$' then
        return false;
    end if;
    insert into pet_machine_execution_nonces(machine_id, nonce, request_id, expires_at)
    select p_machine_id, p_nonce, p_request_id, p_expires_at
    where exists (
        select 1 from pet_machine_capability_dispatch_intents i
        where i.request_id = p_request_id
          and i.envelope->>'machine_id' = p_machine_id
          and i.envelope->>'nonce' = p_nonce::text
          and i.envelope->>'dispatch_sha256' = p_dispatch_sha256
    )
    on conflict(machine_id, nonce) do nothing;
    return found;
end;
$$;

create table if not exists pet_machine_capability_outbox (
    request_id uuid primary key references pet_machine_capability_requests(request_id) on delete restrict,
    idempotency_key text not null unique,
    target_machine_id text not null references machines(id) on delete restrict,
    envelope jsonb not null check(jsonb_typeof(envelope)='object'),
    dispatched_by text not null,
    state text not null default 'pending' check(state in ('pending','published')),
    speaker_message_id bigint unique references speaker_messages(id) on delete restrict,
    created_at timestamptz not null default now(),
    published_at timestamptz,
    check ((state='pending' and speaker_message_id is null and published_at is null)
        or (state='published' and speaker_message_id is not null and published_at is not null))
);
create unique index if not exists uq_pet_capability_speaker_idempotency
    on speaker_messages((metadata->>'idempotency_key'))
    where message_type='pet_capability_signed_execution' and metadata ? 'idempotency_key';

create or replace function publish_pet_machine_capability_dispatch(
    p_request_id uuid,
    p_target_machine_id text,
    p_envelope jsonb,
    p_dispatched_by text
) returns bigint
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_idempotency_key text := 'pet-capability-dispatch:' || p_request_id::text;
    v_speaker_id bigint;
begin
    if coalesce(p_dispatched_by, '') = '' or p_envelope->>'request_id' <> p_request_id::text
       or p_envelope->>'machine_id' <> p_target_machine_id
       or coalesce(p_envelope->>'dispatch_sha256','') !~ '^[0-9a-f]{64}$' then
        raise exception 'invalid PET capability dispatch authority';
    end if;

    insert into pet_machine_capability_dispatch_intents(request_id,envelope,dispatched_by)
    values(p_request_id,p_envelope,p_dispatched_by)
    on conflict(request_id) do nothing;

    insert into pet_machine_capability_outbox(request_id,idempotency_key,target_machine_id,envelope,dispatched_by)
    values(p_request_id,v_idempotency_key,p_target_machine_id,p_envelope,p_dispatched_by)
    on conflict(request_id) do nothing;

    select speaker_message_id into v_speaker_id
      from pet_machine_capability_outbox where request_id=p_request_id for update;
    if v_speaker_id is null then
        insert into speaker_messages(target_type,target_id,message_type,subject,body,priority,metadata)
        values('machine',p_target_machine_id,'pet_capability_signed_execution',
               'Approved PET execution ' || p_request_id::text,
               'Verify signature, key lifecycle, target, expiry, and nonce before local execution.',80,
               p_envelope || jsonb_build_object('idempotency_key',v_idempotency_key))
        on conflict ((metadata->>'idempotency_key'))
          where message_type='pet_capability_signed_execution' and metadata ? 'idempotency_key'
        do update set target_id=excluded.target_id
        returning id into v_speaker_id;

        insert into pet_machine_capability_dispatches(request_id,speaker_message_id,envelope,dispatched_by)
        values(p_request_id,v_speaker_id,p_envelope,p_dispatched_by)
        on conflict(request_id) do nothing;

        update pet_machine_capability_outbox
           set state='published', speaker_message_id=v_speaker_id, published_at=clock_timestamp()
         where request_id=p_request_id and state='pending';
    end if;
    return v_speaker_id;
end;
$$;

revoke all on table pet_machine_capability_keys, pet_machine_capability_key_events,
    pet_machine_capability_outbox from public;
revoke all on function consume_pet_machine_execution_nonce(text,uuid,uuid,timestamptz,text) from public;
revoke all on function publish_pet_machine_capability_dispatch(uuid,text,jsonb,text) from public;
