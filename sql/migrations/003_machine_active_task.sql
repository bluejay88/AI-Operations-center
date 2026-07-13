alter table machine_status_current add column if not exists active_task_id bigint references tasks(id);
