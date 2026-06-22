# Base de dados sintética e requisitos de teste

Esta pasta documenta a base sintética em `../documentos/` (20 documentos jurídicos
fictícios, em Markdown, numerados de `01.md` a `20.md`) e o gabarito esperado do
sistema para as duas questões do desafio.

> ⚠️ Todos os nomes, CPFs, valores e datas são **fictícios**, gerados apenas para teste.

## Estrutura de cada documento

Todo documento tem **frontmatter YAML** (legível por máquina) e, no corpo, uma
**menção em texto** ao tipo de documento e ao CPF do cliente (simulando o texto real).

Campos do frontmatter:

| Campo | Descrição |
|-------|-----------|
| `id` | número de 1 a 20 |
| `tipo` | tipo do documento (petição inicial, sentença, etc.) |
| `caso_id` | caso ao qual o documento pertence |
| `caso_titulo` | descrição do caso |
| `cliente_nome` | nome do cliente |
| `cliente_cpf` | CPF do cliente (fictício) |
| `data` | data de referência do documento |
| `similar_a` | (docs 1–10) ids dos documentos parecidos, quando houver |
| `relacao` | (docs 1–10) tipo de relação: `cópia` ou `versão modificada` |
| `area` | (sentenças) área do direito |

## Mapa do dataset

### Documentos 1–10 — Questão 1 (comparação de documentos parecidos)
Seções obrigatórias no corpo: **Tese Principal, Nome, Data, Valores** (além de Caso e Cliente).

- **CASO-001** — cliente Maria Aparecida Souza (revisão de contrato bancário)
  - `01` petição inicial — juros abusivos ⟷ **par** com `02`
  - `02` emenda à inicial — juros abusivos (*versão modificada* de `01`)
  - `03` tutela de urgência — evitar negativação (diferente)
  - `04` réplica — inversão do ônus da prova (diferente)
  - `05` especificação de provas — perícia contábil (diferente)
- **CASO-002** — cliente João Carlos Pereira (reclamação trabalhista)
  - `06` reclamação trabalhista — horas extras ⟷ **par** com `07`
  - `07` reclamação trabalhista — horas extras (*cópia quase idêntica* de `06`)
  - `08` petição — verbas rescisórias / FGTS ⟷ **par** com `09`
  - `09` petição — verbas rescisórias / FGTS (*versão modificada* de `08`)
  - `10` petição — dano moral / assédio (diferente)

### Documentos 11–20 — Questão 2 (extração de argumentos de sentenças)
Todas são **sentenças**, cada uma com 3 argumentos identificáveis na fundamentação,
em áreas variadas (consumidor, trabalho, civil, tributário, família, locação,
previdenciário, bancário, penal).

## Arquivos de teste
- `gabarito-q1.md` — pares esperados de similaridade e classificação esperada.
- `gabarito-q2.md` — argumentos esperados por sentença.
- `casos-de-teste.md` — cenários de teste e critérios de aceitação do sistema.
