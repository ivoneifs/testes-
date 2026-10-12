-- História de Vida passa a custar 1 crédito (era 0,5). O valor cobrado está em
-- server/store.py (COST_HISTORIA); aqui só os textos dos pacotes.
update public.plans
   set features = (select jsonb_agg(replace(f, 'História de Vida por 0,5 crédito', 'História de Vida por 1 crédito'))
                     from jsonb_array_elements_text(features) f)
 where features::text like '%0,5 crédito%';
