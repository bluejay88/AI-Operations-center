create table if not exists brain_device_identity_reservations (
    device_id text primary key,
    identity_fingerprint text not null check (identity_fingerprint ~ '^[0-9a-f]{64}$'),
    reserved_by text not null check (length(btrim(reserved_by)) > 0),
    approval_ref text not null check (length(btrim(approval_ref)) > 0),
    reserved_at timestamptz not null default now(),
    check (device_id = lower(device_id)),
    check (device_id ~ '^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')
);

comment on table brain_device_identity_reservations is
    'Append-only atomic device identity reservations; public Brain profile APIs are read-only.';

create or replace function reject_brain_device_identity_mutation()
returns trigger language plpgsql as $$
begin
    raise exception 'Brain device identity reservations are append-only';
end;
$$;

drop trigger if exists trg_brain_device_identity_reservations_immutable
    on brain_device_identity_reservations;
create trigger trg_brain_device_identity_reservations_immutable
before update or delete on brain_device_identity_reservations
for each row execute function reject_brain_device_identity_mutation();

insert into brain_device_identity_reservations
    (device_id, identity_fingerprint, reserved_by, approval_ref)
values
    ('brain-gaming-pc', '12af592628bf0934ca8a4019a61c195dfa3fb74975fefbd2a79db14ff70fb8ef',
     'migration-013', 'migration-013-bootstrap')
on conflict (device_id) do nothing;
