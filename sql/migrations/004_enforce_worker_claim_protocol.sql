update tasks
set status = 'queued', started_at = null, updated_at = now(),
    last_error = 'Legacy unfenced claim recovered during worker protocol upgrade'
where status = 'running' and claim_token is null;

create or replace function enforce_worker_claim_protocol()
returns trigger
language plpgsql
as $$
begin
    if tg_op = 'INSERT' and new.status in ('running', 'completed') then
        raise exception 'tasks must be inserted as queued before worker execution';
    end if;

    if new.status = 'running' and old.status is distinct from 'running' then
        if new.claim_token is null or new.claimed_by_machine is null or new.lease_expires_at is null then
            raise exception 'running tasks require a claim token, machine, and lease';
        end if;
    end if;

    if new.status = 'completed' and old.status is distinct from 'completed' then
        if old.status <> 'running' or old.claim_token is null or old.claimed_by_machine is null then
            raise exception 'completed tasks require a fenced running claim';
        end if;
        if nullif(btrim(coalesce(new.result, '')), '') is null then
            raise exception 'completed tasks require non-empty result evidence';
        end if;
        if current_setting('aiops.claim_token', true) is distinct from old.claim_token
           or current_setting('aiops.machine_id', true) is distinct from old.claimed_by_machine then
            raise exception 'completed task session does not own the fenced claim';
        end if;
        if old.lease_expires_at is null or old.lease_expires_at <= now() then
            raise exception 'completed task claim lease has expired';
        end if;
    end if;

    return new;
end;
$$;

drop trigger if exists trg_enforce_worker_claim_protocol on tasks;
create trigger trg_enforce_worker_claim_protocol
before insert or update of status on tasks
for each row execute function enforce_worker_claim_protocol();
