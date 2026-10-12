-- NeuroScore — aba "Vídeos": links para vídeos explicativos dos testes, cadastrados pelo admin.
-- Só o link fica aqui; o vídeo abre na plataforma de origem, com o acesso de quem assiste.

create table if not exists public.videos (
  id          uuid primary key default gen_random_uuid(),
  title       text not null,
  test        text,                       -- instrumento relacionado (livre)
  url         text not null,
  description text,
  sort        integer not null default 0,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
alter table public.videos enable row level security;
drop policy if exists "videos_read"  on public.videos;
drop policy if exists "videos_write" on public.videos;
create policy "videos_read"  on public.videos for select using (auth.role() = 'authenticated');
create policy "videos_write" on public.videos for all
  using (public.is_admin()) with check (public.is_admin());
drop trigger if exists t_videos_touch on public.videos;
create trigger t_videos_touch before update on public.videos
  for each row execute function public.touch_updated_at();
grant select, insert, update, delete on public.videos to authenticated;
