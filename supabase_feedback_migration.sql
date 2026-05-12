-- Student subject feedback, doubts, and teacher replies.
-- Run this in the Supabase SQL editor before using the Feedback feature.

create extension if not exists pgcrypto;

create table if not exists feedback (
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

create index if not exists idx_feedback_student_id on feedback(student_id);
create index if not exists idx_feedback_subject_id on feedback(subject_id);
create index if not exists idx_feedback_status on feedback(status);
create index if not exists idx_feedback_created_at on feedback(created_at desc);

alter table feedback
    add column if not exists feedback_type text not null default 'Feedback',
    add column if not exists understanding text not null default 'Partially understood',
    add column if not exists status text not null default 'open',
    add column if not exists teacher_reply text,
    add column if not exists reply_teacher_id bigint references teachers(teacher_id) on delete set null,
    add column if not exists reply_at timestamp with time zone,
    add column if not exists updated_at timestamp with time zone,
    add column if not exists metadata jsonb not null default '{}'::jsonb;

alter table public.feedback enable row level security;

grant select, insert, update, delete on public.feedback to anon, authenticated;

drop policy if exists "app can read feedback" on public.feedback;
create policy "app can read feedback"
on public.feedback
for select
to anon, authenticated
using (true);

drop policy if exists "students can submit feedback" on public.feedback;
create policy "students can submit feedback"
on public.feedback
for insert
to anon, authenticated
with check (
    student_id is not null
    and subject_id is not null
    and nullif(trim(message), '') is not null
);

drop policy if exists "app can update feedback" on public.feedback;
create policy "app can update feedback"
on public.feedback
for update
to anon, authenticated
using (true)
with check (true);

drop policy if exists "app can delete feedback" on public.feedback;
create policy "app can delete feedback"
on public.feedback
for delete
to anon, authenticated
using (true);
