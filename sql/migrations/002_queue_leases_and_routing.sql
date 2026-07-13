alter table tasks add column if not exists execution_machine_id text references machines(id);
alter table tasks add column if not exists claimed_by_machine text references machines(id);
alter table tasks add column if not exists claim_token text;
alter table tasks add column if not exists lease_expires_at timestamptz;
alter table tasks add column if not exists attempt_count integer not null default 0;
alter table tasks add column if not exists max_attempts integer not null default 3;
alter table tasks add column if not exists next_attempt_at timestamptz;
alter table tasks add column if not exists assignment_generation integer not null default 0;
alter table tasks add column if not exists last_error text;

update tasks t
set execution_machine_id = a.machine_id
from agents a
where t.agent_id = a.id
  and t.execution_machine_id is null;

create index if not exists idx_tasks_execution_queue
    on tasks(execution_machine_id, status, next_attempt_at, priority desc, created_at);

create index if not exists idx_tasks_running_lease
    on tasks(status, lease_expires_at)
    where status = 'running';
