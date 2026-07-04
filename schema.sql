-- Mochu's Productivity Tracker - Supabase schema
-- Run this once in Supabase SQL Editor.

create extension if not exists pgcrypto;

create table if not exists public.mochu_tasks (
  id uuid primary key default gen_random_uuid(),
  year int not null,
  month int not null check (month between 1 and 12),
  task_name text not null,
  priority text not null default 'Medium',
  category text not null default 'Other',
  frequency text not null default 'Daily',
  target int not null default 0,
  notes text default '',
  sort_order int not null default 0,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_mochu_tasks_month on public.mochu_tasks(year, month, sort_order);

create table if not exists public.mochu_completions (
  id uuid primary key default gen_random_uuid(),
  task_id uuid not null references public.mochu_tasks(id) on delete cascade,
  year int not null,
  month int not null check (month between 1 and 12),
  day int not null check (day between 1 and 31),
  completed boolean not null default false,
  updated_at timestamptz not null default now(),
  unique(task_id, year, month, day)
);

create index if not exists idx_mochu_completions_month on public.mochu_completions(year, month, day);

create table if not exists public.mochu_reflections (
  id uuid primary key default gen_random_uuid(),
  year int not null,
  month int not null check (month between 1 and 12),
  went_well text default '',
  needs_improvement text default '',
  focus_next_month text default '',
  updated_at timestamptz not null default now(),
  unique(year, month)
);

-- For a personal app, the simplest free setup is to keep tables unprotected but do NOT share your app URL publicly.
-- For stricter security, enable RLS and add policies matching your Supabase auth setup.
