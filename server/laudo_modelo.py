"""Modelo de laudo da profissional (Google Doc 1LCalEMU…): "Laudo Psicológico de Avaliação
Neuropsicológica", Times New Roman 12.

Só a ESTRUTURA e os textos-padrão do modelo ficam aqui (nada do paciente do exemplo).
Ordem das seções:
  título + nota CFP · IDENTIFICAÇÃO · DESCRIÇÃO DA DEMANDA · PROCEDIMENTOS ·
  TESTES PSICOLÓGICOS E NEUROPSICOLÓGICOS · REFERENCIAL TEÓRICO METODOLÓGICO ·
  NÚMERO DE ENCONTROS E TEMPO DE DURAÇÃO · HISTÓRICO FAMILIAR DE TRANSTORNOS MENTAIS ·
  MEDICAÇÕES EM USO · ANÁLISE DO INSTRUMENTO E INTERPRETAÇÃO · CONCLUSÃO E SÍNTESE ·
  Impressão diagnóstica · Obs.: Importante · SUGESTÕES DE ENCAMINHAMENTOS · RECOMENDAÇÕES ·
  À EQUIPE MULTIDISCIPLINAR · local e data · assinatura · rodapé.
Os textos fixos vão no laudo como `textos_fixos` (a tela, a impressão e o .docx usam os mesmos).
"""
from __future__ import annotations

TITULO = 'Laudo Psicológico de Avaliação Neuropsicológica'

NOTA_CFP = (
    'Laudo realizado de acordo com as Resoluções 06/2019, 01/2009 e 09/2018, do Conselho Federal de Psicologia '
    '(CFP), as quais instituem o Manual de Elaboração de Documentos Escritos produzidos pelo psicólogo, '
    'decorrentes de avaliação psicológica, assim como regras do registro documental elaborado pela (o) '
    'psicóloga (o), interpretação e análise dos dados obtidos por meio de métodos, técnicas e instrumentos '
    'reconhecidos cientificamente para uso na prática profissional.'
)

REFERENCIAL = (
    'Miotto (2017) relata que a Neuropsicologia é uma ciência interdisciplinar, que tem como objetivo o estudo '
    'da cognição e do comportamento de um indivíduo relacionado ao seu Sistema Nervoso Central (SNC). Miotto, '
    'Campanholo, Trevisan e Serrão (2018) compreendem a avaliação neuropsicológica como um processo técnico e '
    'científico em que se obtêm informações a partir de instrumentos, técnicas e métodos específicos, nas quais '
    'são realizadas interpretações das informações obtidas. Assim como os dados quantitativos obtidos na '
    'testagem cognitiva, é importante realizar a análise qualitativa que envolve observação clínica das '
    'verbalizações, gestos, humor, tom de voz, hábitos e demais peculiaridades que podem oferecer informações '
    'acerca do ajustamento comportamental, dinâmica familiar e estilo de vida do paciente (Campanholo & Serrão, '
    '2018). Lezak, Howieson & Loring (2004) propõem seis objetivos principais para a avaliação '
    'neuropsicológica: pesquisa, resposta a solicitação forense, diagnóstico, cuidado com o paciente, '
    'identificação das necessidades e eficácia do tratamento.'
)

OBS_IMPORTANTE = (
    'Ressalta-se que, o ser humano possui uma natureza dinâmica; não definitiva e não cristalizada. Sendo assim, '
    'os resultados aqui expostos dizem respeito ao funcionamento das funções cognitivas de {nome} no momento '
    'presente, podendo haver alterações posteriores, dependendo das contingências ambientais vivenciadas e/ou '
    'do(s) acompanhamento(s) recebido(s).'
)

EQUIPE = [
    'O Exame Neuropsicológico é de extrema importância para nortear a reabilitação cognitiva, bem como auxiliar '
    'outros profissionais nos diagnósticos de suas respectivas áreas de atuação.',
    'Lembrando que na Avaliação Neuropsicológica o uso apropriado das informações deve ser feito de forma ética, '
    'preservando e zelando a integridade socioemocional do examinando em questão, não o expondo, portanto, a '
    'qualquer situação de constrangimento ou discriminação.',
    'Sem mais para o momento, à disposição para maiores esclarecimentos.',
]

RODAPE = [
    'Importante ressaltar que este documento:',
    '1. Não pode ser utilizado para fins diferentes do apontado no item de identificação do documento.',
    '2. Tem caráter sigiloso, extrajudicial, não cabendo à psicóloga responsabilizar-se por seu uso após a entrega do laudo.',
    '3. Refazer depois de 2 (dois) anos a partir da data de entrega deste laudo.',
]

PROCEDIMENTOS_PADRAO = [
    'Anamnese para compreender sua história de vida.',
    'Rapport e Hora do jogo. Objetivo: Estabelecer vínculo com o paciente e avaliar, por meio do jogo, aspectos '
    'relacionados às funções cognitivas e à afetividade.',
    'Observação clínica.',
]

# Guia de redação por seção (vai no prompt). Cada item = (campo do schema, o que escrever).
GUIA = (
    'MODELO DO LAUDO (siga a ordem, os títulos e o estilo; texto corrido, formal, terceira pessoa, '
    'chamando o paciente pelo primeiro e segundo nome):\n'
    '- identificacao: copie do formulário. data_construcao = mês e ano por extenso (ex.: "Dezembro de 2025"). '
    'Campo sem dado = "".\n'
    '- descricao_demanda: "<Nome> paciente de <idade> anos, foi encaminhado(a) à avaliação neuropsicológica por '
    'apresentar …" — queixas, quando os sintomas ficaram evidentes, comportamentos atuais; termine com '
    '"Levando em consideração a demanda descrita, objetivou-se avaliar as funções cognitivas do paciente, a fim '
    'de melhor compreender o seu perfil neuropsicológico."\n'
    '- procedimentos: os procedimentos não-testes (anamnese, rapport e hora do jogo, observação clínica e '
    'outros informados), uma frase cada, com "Objetivo:" quando couber.\n'
    '- instrumentos_utilizados: SÓ os testes efetivamente aplicados, na ordem em que aparecem na análise. '
    'nome = nome completo + sigla; referencia = autor(es) e ano da edição brasileira, se conhecidos com '
    'segurança (senão ""); objetivo = o que avalia, uma frase.\n'
    '- numero_encontros: "Foram realizadas N sessões de forma presencial com duração de X cada." (dados do formulário).\n'
    '- historico_familiar_transtornos e medicacoes_em_uso: frase curta com o que foi informado; nada informado = '
    '"Não informado." / "Nenhuma." só se o formulário disser que não usa.\n'
    '- analise_testes: UM item por instrumento. instrumento = nome do teste com sigla; descricao = uma frase '
    '("Avalia …"). tabelas = as tabelas do instrumento como no modelo (ex.: WAIS/WISC: tabela de subtestes '
    '[Subteste | Funções avaliadas | Ptos ponder | Interpretação] e tabela de índices [Escala | P. Composto | '
    'Percentil | Interv. Conf. 95% | Interpretação]; FDT: tabela de tempo e tabela de erros; Vineland: '
    'subdomínios e domínios; escalas: [Escala | Pontuação/Escore T | Interpretação]). Transcreva os valores '
    'EXATAMENTE. base_conceitual = parágrafo teórico curto sobre os índices/construtos quando o teste tiver '
    '(senão ""). interpretacao = análise clínica aprofundada como no modelo: desempenho global, pontos fortes '
    'e fracos relativos, discrepâncias, impacto funcional e no dia a dia, articulação com a queixa — vários '
    'parágrafos separados por linha em branco.\n'
    '- conclusao_sintese: vários parágrafos: (1) apresentação e comportamento nas sessões (observação clínica); '
    '(2) síntese da história de vida (gestação, desenvolvimento, alimentação/sono, família/social, autonomia, '
    'escola); (3) integração dos resultados por domínio (funcionamento intelectual, forças relativas, '
    'fraquezas centrais, atenção e funções executivas, memória e aprendizagem, comportamento adaptativo).\n'
    '- impressao_diagnostica: texto com "Perfil compatível:" e os critérios do DSM-5-TR que os dados sustentam; '
    'hipoteses com códigos DSM-5-TR/CID. Só o que os dados sustentam, sempre condicional; sem sustentação, '
    'hipoteses vazio e texto dizendo que os achados não configuram hipótese diagnóstica.\n'
    '- sugestoes_encaminhamentos: itens (avaliações médicas, psicoterapia, reabilitação neuropsicológica, '
    'intervenção psicopedagógica…) individualizados ao caso, cada um com a justificativa.\n'
    '- recomendacoes.familia e recomendacoes.escolares: orientações práticas e individualizadas (escolares só '
    'para criança/adolescente ou estudante; senão lista vazia).\n'
    '- local_data: "<Cidade>, <dia> de <mês> de <ano>." com a cidade e a data do laudo do formulário '
    '(sem cidade: só a data).\n'
    'NÃO escreva no corpo do laudo frases sobre o que deixou de ser informado ("não foram fornecidos…"): '
    'escreva só com o que existe; as faltas vão em alertas_para_revisao.\n'
    'NÃO escreva o referencial teórico, a nota do CFP, a "Obs.: Importante", o texto à equipe nem o rodapé: '
    'são textos fixos do modelo, inseridos pelo sistema.'
)


def textos_fixos(nome: str) -> dict:
    primeiro = ' '.join((nome or 'o(a) paciente').split()[:3])
    return {
        'titulo': TITULO,
        'nota_cfp': NOTA_CFP,
        'referencial_teorico': REFERENCIAL,
        'obs_importante': OBS_IMPORTANTE.format(nome=primeiro),
        'equipe_multidisciplinar': EQUIPE,
        'rodape': RODAPE,
    }
