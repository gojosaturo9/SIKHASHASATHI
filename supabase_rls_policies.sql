-- Run this after creating the tables.
-- This app uses custom Streamlit login. These policies allow the app API role
-- to perform the reads/writes the UI needs.

create extension if not exists pgcrypto;

create table if not exists public.announcements (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    content text not null,
    category text not null default 'General',
    created_at timestamp with time zone not null default now()
);

create index if not exists announcements_created_at_idx
on public.announcements (created_at desc);

create table if not exists public.feedback (
    id uuid primary key default gen_random_uuid(),
    student_id bigint references students(student_id) on delete cascade,
    subject_id bigint references subjects(subject_id) on delete cascade,
    feedback_type text not null default 'Feedback',
    understanding text not null default 'Partially understood',
    message text not null,
    status text not null default 'open',
    teacher_reply text,
    reply_teacher_id bigint references teachers(teacher_id) on delete set null,
    reply_at timestamp with time zone,
    created_at timestamp with time zone not null default now(),
    updated_at timestamp with time zone,
    metadata jsonb not null default '{}'::jsonb
);

alter table public.teachers enable row level security;
alter table public.students enable row level security;
alter table public.subjects enable row level security;
alter table public.subject_students enable row level security;
alter table public.attendance_logs enable row level security;
alter table public.announcements enable row level security;
alter table public.feedback enable row level security;

grant select, insert, update, delete on public.teachers to anon, authenticated;
grant select, insert, update, delete on public.students to anon, authenticated;
grant select, insert, update, delete on public.subjects to anon, authenticated;
grant select, insert, update, delete on public.subject_students to anon, authenticated;
grant select, insert, update, delete on public.attendance_logs to anon, authenticated;
grant select, insert, update, delete on public.announcements to anon, authenticated;
grant select, insert, update, delete on public.feedback to anon, authenticated;
grant usage, select on all sequences in schema public to anon, authenticated;

drop policy if exists "app all teachers" on public.teachers;
create policy "app all teachers" on public.teachers
for all to anon, authenticated
using (true)
with check (true);

drop policy if exists "app all students" on public.students;
create policy "app all students" on public.students
for all to anon, authenticated
using (true)
with check (true);

drop policy if exists "app all subjects" on public.subjects;
create policy "app all subjects" on public.subjects
for all to anon, authenticated
using (true)
with check (true);

drop policy if exists "app all subject_students" on public.subject_students;
create policy "app all subject_students" on public.subject_students
for all to anon, authenticated
using (true)
with check (true);

drop policy if exists "app all attendance_logs" on public.attendance_logs;
create policy "app all attendance_logs" on public.attendance_logs
for all to anon, authenticated
using (true)
with check (true);

drop policy if exists "app all announcements" on public.announcements;
create policy "app all announcements" on public.announcements
for all to anon, authenticated
using (true)
with check (true);

drop policy if exists "app all feedback" on public.feedback;
create policy "app all feedback" on public.feedback
for all to anon, authenticated
using (true)
with check (true);
