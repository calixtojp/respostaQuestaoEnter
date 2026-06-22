# Casos de teste — comportamento esperado do sistema

Cenários que o sistema deve satisfazer. Servem como requisitos executáveis antes
da implementação.

## Questão 1 — Comparação de documentos

### CT1.1 — Detectar cópia quase idêntica
- **Dado** o documento `07` inserido no CASO-002 (já contendo `06`).
- **Quando** o sistema comparar `07` com os documentos do mesmo caso.
- **Então** deve classificar `07` × `06` como **cópia** e sinalizar para revisão/dedup.

### CT1.2 — Detectar versão modificada (mesma tese, seções diferentes)
- **Dado** o documento `02` inserido no CASO-001 (já contendo `01`).
- **Quando** o sistema comparar `02` com `01`.
- **Então** deve classificar como **versão modificada** (não "cópia", não "diferente").

### CT1.3 — Não confundir vocabulário jurídico com similaridade real
- **Dado** os documentos `03`, `04`, `05` do CASO-001 (todos com jargão jurídico comum).
- **Quando** comparados entre si.
- **Então** todos devem ser **diferente** (teses distintas, apesar do vocabulário comum).

### CT1.4 — Não comparar entre casos distintos
- **Dado** o documento `19` (CASO-109, revisão bancária) e o `01` (CASO-001, revisão bancária).
- **Quando** um novo documento for inserido.
- **Então** a comparação ocorre apenas dentro do mesmo `caso_id`; pares entre casos são `diferente`.

### CT1.5 — Ação ao identificar cópia/versão
- **Dado** que `07` foi classificado como cópia de `06`.
- **Então** o sistema deve registrar o vínculo (ex.: `duplicado_de: 06`), evitar reprocessamento
  redundante e notificar o usuário (não excluir automaticamente).

### CT1.6 — Extração de campos estruturados
- **Dado** qualquer documento 1–10.
- **Então** o sistema deve extrair `tipo`, `caso_id`, `cliente_cpf`, `tese_principal`,
  `data` e `valores`, conforme `gabarito-q1.md`.

## Questão 2 — Extração de argumentos

### CT2.1 — Cobertura de argumentos
- **Dado** a sentença `11`.
- **Então** o sistema deve extrair os 3 argumentos listados em `gabarito-q2.md`
  (recall ≥ alvo definido).

### CT2.2 — Anti-alucinação (fidelidade)
- **Dado** qualquer sentença 11–20.
- **Então** todo argumento extraído deve conter `trecho_citado` que existe **literalmente**
  no documento. Argumentos sem âncora textual são rejeitados.

### CT2.3 — Classificação de tipo
- **Dado** a sentença `20` (furto).
- **Então** o argumento "princípio da insignificância" deve ter `tipo = principiologico`.

### CT2.4 — Granularidade correta
- **Dado** a sentença `14` (execução fiscal).
- **Então** "prescrição", "inaplicabilidade da Súmula 106" e "prejudicialidade da CDA"
  devem ser **três** argumentos distintos, não fundidos.

### CT2.5 — Revisão humana
- **Dado** argumentos extraídos de qualquer sentença.
- **Então** o sistema deve permitir aprovar, editar ou rejeitar cada argumento,
  registrando o estado da revisão.

### CT2.6 — Versionamento
- **Dado** uma mudança de prompt, modelo ou schema.
- **Então** as extrações devem registrar `versao_prompt`, `modelo` e `versao_schema`,
  permitindo reprocessar e comparar resultados entre versões.

## Métricas sugeridas
- **Q1**: acurácia da classificação 3-classes; matriz de confusão (cópia/modificada/diferente);
  precisão@k de pares candidatos.
- **Q2**: recall e precisão de argumentos vs. gabarito; taxa de alucinação (trechos não
  encontrados no texto); concordância de `tipo`.
