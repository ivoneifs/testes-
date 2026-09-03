-- NeuroScore — instrumentos corrigidos fora do sistema (TAVIS, SON-R, Perfil Sensorial…)
-- O profissional digita os resultados já corrigidos; a IA integra no laudo.

alter table public.evaluations add column if not exists external_results jsonb not null default '[]'::jsonb;
