# Gabarito — Questão 1 (comparação de documentos parecidos)

A comparação ocorre **dentro do mesmo caso** (`caso_id`). Pares em casos diferentes
devem sempre ser classificados como `diferente`.

## Classificação esperada (resultado de 3 classes)

| Par | Caso | Resultado esperado | Justificativa |
|-----|------|--------------------|---------------|
| 01 × 02 | CASO-001 | **versão modificada** | mesma tese (juros abusivos), mas mudam advogado, data, valor da causa e um parágrafo |
| 06 × 07 | CASO-002 | **cópia** | textos quase idênticos; diferenças triviais/nenhuma |
| 08 × 09 | CASO-002 | **versão modificada** | mesma tese (verbas/FGTS), mudam advogado, datas e valores recalculados |
| 03 × 04 × 05 | CASO-001 | **diferente** (entre si e dos demais) | teses distintas (tutela, réplica, provas) |
| 10 × (06,07,08,09) | CASO-002 | **diferente** | tese de dano moral, distinta das demais |
| qualquer par CASO-001 × CASO-002 | — | **diferente** | casos/clientes distintos |

### Matriz resumida por caso

**CASO-001** (docs 1–5):
- (1,2) → versão modificada
- (1,3) (1,4) (1,5) (2,3) (2,4) (2,5) (3,4) (3,5) (4,5) → diferente

**CASO-002** (docs 6–10):
- (6,7) → cópia
- (8,9) → versão modificada
- (6,8) (6,9) (6,10) (7,8) (7,9) (7,10) (8,10) (9,10) → diferente

## Extração estruturada esperada (seções dos docs 1–10)

O sistema deve conseguir extrair, de cada documento, os campos abaixo (do frontmatter
e/ou do corpo). Exemplo de saída esperada para alguns documentos:

| id | tipo | caso_id | cpf | tese_principal (resumo) | data | valor_principal |
|----|------|---------|-----|--------------------------|------|-----------------|
| 1 | petição inicial | CASO-001 | 312.456.789-01 | juros abusivos / capitalização indevida | 2025-03-14 | causa R$ 72.500,00 |
| 2 | emenda à inicial | CASO-001 | 312.456.789-01 | juros abusivos / capitalização indevida | 2025-04-22 | causa R$ 81.300,00 |
| 6 | reclamação trabalhista | CASO-002 | 987.654.321-00 | horas extras não pagas | 2025-02-10 | causa R$ 40.000,00 |
| 7 | reclamação trabalhista | CASO-002 | 987.654.321-00 | horas extras não pagas | 2025-02-10 | causa R$ 40.000,00 |
| 8 | petição | CASO-002 | 987.654.321-00 | verbas rescisórias / FGTS | 2025-03-05 | FGTS R$ 9.120,00 |
| 9 | petição | CASO-002 | 987.654.321-00 | verbas rescisórias / FGTS | 2025-04-18 | FGTS R$ 9.860,00 |

## Critério de qualidade (Q1)
- O sistema **não** pode classificar 01×02 e 08×09 como "cópia" (são modificações).
- O sistema **deve** distinguir 06×07 (cópia) de 08×09 (modificada), mesmo ambos sendo "parecidos".
- O sistema **não** pode marcar como parecidos documentos que só compartilham vocabulário
  jurídico genérico (ex.: 03, 04, 05 usam termos jurídicos comuns mas têm teses distintas).
