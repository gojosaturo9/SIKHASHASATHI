-- TRUEPRESENCE AI email automation tables.
-- Run this in the Supabase SQL editor for durable email tracking,
-- retry recovery, thread memory, and AI reply escalation.

create extension if not exists pgcrypto;

create table if not exists email_logs (
    id uuid primary key default gen_random_uuid(),
    message_id text unique not null,
    student_id bigint references students(student_id) on delete set null,
    subject_id bigint references subjects(subject_id) on delete set null,
    to_email text not null,
    email_type text not null default 'attendance_proof',
    status text not null default 'queued',
    subject text,
    body_preview text,
    error_message text,
    attempt_count integer not null default 0,
    created_at timestamp with time zone not null default now(),
    last_attempt_at timestamp with time zone,
    sent_at timestamp with time zone,
    delivered_at timestamp with time zone,
    opened_at timestamp with time zone,
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_email_logs_student_id on email_logs(student_id);
create index if not exists idx_email_logs_subject_id on email_logs(subject_id);
create index if not exists idx_email_logs_status on email_logs(status);
create index if not exists idx_email_logs_created_at on email_logs(created_at desc);

create table if not exists email_threads (
    id uuid primary key default gen_random_uuid(),
    student_id bigint references students(student_id) on delete set null,
    subject_id bigint references subjects(subject_id) on delete set null,
    thread_key text unique not null,
    status text not null default 'open',
    intent text,
    escalation_status text not null default 'none',
    assigned_teacher_id bigint references teachers(teacher_id) on delete set null,
    created_at timestamp with time zone not null default now(),
    updated_at timestamp with time zone not null default now(),
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_email_threads_student_id on email_threads(student_id);
create index if not exists idx_email_threads_status on email_threads(status);

create table if not exists email_messages (
    id uuid primary key default gen_random_uuid(),
    thread_id uuid references email_threads(id) on delete cascade,
    student_id bigint references students(student_id) on delete set null,
    direction text not null,
    intent text,
    from_email text,
    to_email text,
    subject text,
    body text not null,
    ai_generated boolean not null default false,
    escalate boolean not null default false,
    created_at timestamp with time zone not null default now(),
    metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_email_messages_thread_id on email_messages(thread_id);
create index if not exists idx_email_messages_student_id on email_messages(student_id);

-- Suggested RLS baseline. Enable once policies match your production auth claims.
-- alter table email_logs enable row level security;
-- alter table email_threads enable row level security;
-- alter table email_messages enable row level security;
