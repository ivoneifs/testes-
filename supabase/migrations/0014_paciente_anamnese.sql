-- NeuroScore — dados completos do paciente + anamnese preenchida por marcação.
--   dados    = identificação da ficha (responsável, CPF, naturalidade, fone, endereço, cidade,
--              mãe, pai, solicitante, especialidade, hipótese diagnóstica, lateralidade…)
--   anamnese = respostas do formulário "Anamnese Infantojuvenil" ({respostas, atualizado_em})
alter table public.patients add column if not exists dados    jsonb not null default '{}'::jsonb;
alter table public.patients add column if not exists anamnese jsonb not null default '{}'::jsonb;
notify pgrst, 'reload schema';
