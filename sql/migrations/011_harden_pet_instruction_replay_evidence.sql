-- Supersedes the replay evidence contract introduced by migration 010.
-- Existing version-1 rows are retained honestly: their envelope hash was not
-- captured at claim time and must never be synthesized after the fact.

do $$
begin
    if not exists (select 1 from pg_roles where rolname = 'aiops_replay_guard_owner') then
        create role aiops_replay_guard_owner nologin noinherit;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'aiops_replay_consumer') then
        create role aiops_replay_consumer nologin noinherit;
    end if;
    if not exists (select 1 from pg_roles where rolname = 'aiops_replay_maintainer') then
        create role aiops_replay_maintainer nologin noinherit;
    end if;
    -- Compatibility bridge for the current single database identity. A
    -- production worker login can instead be granted only this consumer role.
    execute format('grant aiops_replay_consumer to %I', current_user);
end;
$$;

alter table pet_instruction_nonces
    add column if not exists envelope_sha256 text,
    add column if not exists evidence_version smallint not null default 1;

alter table pet_instruction_nonces
    alter column evidence_version set default 2;

alter table pet_instruction_nonces
    add constraint pet_instruction_nonce_envelope_hash_check
    check (
        (evidence_version = 1 and envelope_sha256 is null)
        or
        (evidence_version = 2 and envelope_sha256 ~ '^[0-9a-f]{64}$')
    ) not valid;

alter table pet_instruction_nonces
    validate constraint pet_instruction_nonce_envelope_hash_check;

create table if not exists pet_instruction_nonce_archive (
    signer_id text not null,
    nonce text not null,
    instruction_id text not null,
    target_machine_id text not null,
    expires_at timestamptz not null,
    consumed_at timestamptz not null,
    envelope_sha256 text,
    evidence_version smallint not null,
    archived_at timestamptz not null default now(),
    primary key (signer_id, nonce),
    constraint pet_instruction_nonce_archive_hash_check check (
        (evidence_version = 1 and envelope_sha256 is null)
        or
        (evidence_version = 2 and envelope_sha256 ~ '^[0-9a-f]{64}$')
    )
);

create table if not exists pet_instruction_prune_audit (
    id bigserial primary key,
    cutoff_at timestamptz not null,
    pruned_rows integer not null check (pruned_rows >= 0),
    retention_interval interval not null,
    requested_by text not null,
    created_at timestamptz not null default now()
);

create or replace function reject_pet_instruction_evidence_mutation()
returns trigger
language plpgsql
as $$
begin
    if current_user <> 'aiops_replay_guard_owner' then
        raise exception 'pet instruction replay evidence is append-only'
            using errcode = '42501';
    end if;
    return old;
end;
$$;

drop trigger if exists pet_instruction_nonces_append_only on pet_instruction_nonces;
create trigger pet_instruction_nonces_append_only
before update or delete on pet_instruction_nonces
for each row execute function reject_pet_instruction_evidence_mutation();

drop trigger if exists pet_instruction_nonce_archive_append_only on pet_instruction_nonce_archive;
create trigger pet_instruction_nonce_archive_append_only
before update or delete on pet_instruction_nonce_archive
for each row execute function reject_pet_instruction_evidence_mutation();

drop trigger if exists pet_instruction_prune_audit_append_only on pet_instruction_prune_audit;
create trigger pet_instruction_prune_audit_append_only
before update or delete on pet_instruction_prune_audit
for each row execute function reject_pet_instruction_evidence_mutation();

revoke all on table pet_instruction_nonces from public;
revoke all on table pet_instruction_nonce_archive from public;
revoke all on table pet_instruction_prune_audit from public;
revoke all on sequence pet_instruction_prune_audit_id_seq from public;
revoke execute on function consume_pet_instruction_nonce(text, text, text, text, timestamptz) from public;
drop function consume_pet_instruction_nonce(text, text, text, text, timestamptz);

alter table pet_instruction_nonces owner to aiops_replay_guard_owner;
alter table pet_instruction_nonce_archive owner to aiops_replay_guard_owner;
alter table pet_instruction_prune_audit owner to aiops_replay_guard_owner;
alter sequence pet_instruction_prune_audit_id_seq owner to aiops_replay_guard_owner;
alter function reject_pet_instruction_evidence_mutation() owner to aiops_replay_guard_owner;

create or replace function consume_pet_instruction_nonce(
    p_signer_id text,
    p_nonce text,
    p_instruction_id text,
    p_target_machine_id text,
    p_expires_at timestamptz,
    p_envelope_sha256 text
) returns boolean
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    inserted integer;
begin
    if p_signer_id is null or btrim(p_signer_id) = ''
       or p_nonce is null or btrim(p_nonce) = ''
       or p_instruction_id is null or btrim(p_instruction_id) = ''
       or p_target_machine_id is null or btrim(p_target_machine_id) = ''
       or p_expires_at is null or p_expires_at <= clock_timestamp()
       or p_envelope_sha256 is null
       or p_envelope_sha256 !~ '^[0-9a-f]{64}$' then
        return false;
    end if;

    insert into public.pet_instruction_nonces (
        signer_id,
        nonce,
        instruction_id,
        target_machine_id,
        expires_at,
        envelope_sha256,
        evidence_version
    ) values (
        p_signer_id,
        p_nonce,
        p_instruction_id,
        p_target_machine_id,
        p_expires_at,
        p_envelope_sha256,
        2
    )
    on conflict (signer_id, nonce) do nothing;

    get diagnostics inserted = row_count;
    return inserted = 1;
end;
$$;

alter function consume_pet_instruction_nonce(text, text, text, text, timestamptz, text)
    owner to aiops_replay_guard_owner;
revoke all on function consume_pet_instruction_nonce(text, text, text, text, timestamptz, text) from public;
grant execute on function consume_pet_instruction_nonce(text, text, text, text, timestamptz, text)
    to aiops_replay_consumer;

create or replace function prune_pet_instruction_nonces(
    p_retention interval default interval '7 days',
    p_limit integer default 1000
) returns integer
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
declare
    cutoff timestamptz;
    removed integer;
begin
    if p_retention < interval '1 day'
       or p_retention > interval '365 days'
       or p_limit < 1
       or p_limit > 10000 then
        raise exception 'invalid replay evidence pruning policy'
            using errcode = '22023';
    end if;
    cutoff := clock_timestamp() - p_retention;

    with candidates as (
        select n.*
        from public.pet_instruction_nonces n
        where n.expires_at < cutoff
        order by n.expires_at, n.signer_id, n.nonce
        for update skip locked
        limit p_limit
    ), archived as (
        insert into public.pet_instruction_nonce_archive (
            signer_id,
            nonce,
            instruction_id,
            target_machine_id,
            expires_at,
            consumed_at,
            envelope_sha256,
            evidence_version
        )
        select
            signer_id,
            nonce,
            instruction_id,
            target_machine_id,
            expires_at,
            consumed_at,
            envelope_sha256,
            evidence_version
        from candidates
        on conflict (signer_id, nonce) do nothing
        returning signer_id, nonce
    )
    delete from public.pet_instruction_nonces n
    using archived a
    where n.signer_id = a.signer_id and n.nonce = a.nonce;

    get diagnostics removed = row_count;
    insert into public.pet_instruction_prune_audit (
        cutoff_at, pruned_rows, retention_interval, requested_by
    ) values (
        cutoff, removed, p_retention, session_user
    );
    return removed;
end;
$$;

alter function prune_pet_instruction_nonces(interval, integer)
    owner to aiops_replay_guard_owner;
revoke all on function prune_pet_instruction_nonces(interval, integer) from public;
grant execute on function prune_pet_instruction_nonces(interval, integer)
    to aiops_replay_maintainer;

comment on column pet_instruction_nonces.envelope_sha256 is
    'SHA-256 of the canonical signed envelope verified before this nonce claim; NULL only for legacy migration-010 evidence.';
comment on function prune_pet_instruction_nonces(interval, integer) is
    'Archives expired replay claims after a minimum retention window and appends a pruning audit record; maintenance-role only.';
