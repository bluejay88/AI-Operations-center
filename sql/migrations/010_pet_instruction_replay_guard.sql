create table if not exists pet_instruction_nonces (
    signer_id text not null,
    nonce text not null,
    instruction_id text not null,
    target_machine_id text not null,
    expires_at timestamptz not null,
    consumed_at timestamptz not null default now(),
    primary key (signer_id, nonce),
    constraint pet_instruction_nonce_expiry_check check (expires_at > consumed_at)
);

create index if not exists idx_pet_instruction_nonces_expiry
    on pet_instruction_nonces (expires_at);

create or replace function consume_pet_instruction_nonce(
    p_signer_id text,
    p_nonce text,
    p_instruction_id text,
    p_target_machine_id text,
    p_expires_at timestamptz
) returns boolean
language plpgsql
as $$
declare
    inserted integer;
begin
    if p_signer_id is null or btrim(p_signer_id) = ''
       or p_nonce is null or btrim(p_nonce) = ''
       or p_instruction_id is null or btrim(p_instruction_id) = ''
       or p_target_machine_id is null or btrim(p_target_machine_id) = ''
       or p_expires_at <= now() then
        return false;
    end if;

    insert into pet_instruction_nonces (
        signer_id, nonce, instruction_id, target_machine_id, expires_at
    ) values (
        p_signer_id, p_nonce, p_instruction_id, p_target_machine_id, p_expires_at
    )
    on conflict (signer_id, nonce) do nothing;

    get diagnostics inserted = row_count;
    return inserted = 1;
end;
$$;

comment on table pet_instruction_nonces is
    'Atomic cross-process replay claims for signed Brain instructions; rows are audit evidence and are not updated by workers.';
