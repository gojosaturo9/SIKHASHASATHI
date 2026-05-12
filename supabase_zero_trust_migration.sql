alter table public.attendance_logs
add column if not exists id uuid default gen_random_uuid(),
add column if not exists source text not null default 'legacy',
add column if not exists photo_detected boolean not null default false,
add column if not exists manual_override boolean not null default false,
add column if not exists override_by_role text,
add column if not exists override_by_id text,
add column if not exists override_by_name text,
add column if not exists override_reason text,
add column if not exists override_at timestamp,
add column if not exists editable_until timestamp;

update public.attendance_logs
set editable_until = coalesce(editable_until, timestamp + interval '6 hours')
where editable_until is null;

update public.attendance_logs
set id = gen_random_uuid()
where id is null;

create index if not exists attendance_logs_editable_idx
on public.attendance_logs (editable_until, photo_detected);

create index if not exists attendance_logs_manual_override_idx
on public.attendance_logs (manual_override, override_at);
