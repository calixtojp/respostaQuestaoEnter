# Gabarito — Questão 2 (extração de argumentos de sentenças)

Para cada sentença (docs 11–20), o sistema deve extrair os argumentos do juiz da
seção **Fundamentação**. Saída estruturada esperada por argumento:
`titulo`, `resumo`, `trecho_citado` (literal, presente no texto), `posicao`
(ordem na fundamentação), `tipo`, `confianca`.

Taxonomia de `tipo` usada no gabarito:
`probatorio` · `merito` (direito material) · `jurisprudencial` · `principiologico` ·
`processual` · `quantum`.

> ⚠️ Todo `trecho_citado` extraído deve existir **literalmente** no documento
> (verificável por busca de substring). Argumento sem âncora textual = alucinação.

---

## Doc 11 — Negativação indevida (Consumidor)
1. **Ausência de prova da contratação** · `probatorio` · ré não juntou contrato; ônus era dela.
2. **Responsabilidade objetiva / fortuito interno** · `jurisprudencial` · fraude de terceiro não exclui responsabilidade (Súmula 479 STJ).
3. **Dano moral in re ipsa e fixação do quantum** · `quantum` · inscrição indevida gera dano presumido; R$ 8.000,00.

## Doc 12 — Horas extras (Trabalho)
1. **Invalidade dos cartões de ponto britânicos** · `probatorio` · registros idênticos → Súmula 338 TST, inversão do ônus.
2. **Prova testemunhal confirma sobrejornada** · `probatorio` · 2h extras/dia com adicional de 50% e reflexos.
3. **Improcedência do adicional noturno** · `merito` · sem prova de labor após 22h.

## Doc 13 — Acidente de trânsito (Civil)
1. **Presunção de culpa na colisão traseira** · `merito` · presunção não elidida pelo réu.
2. **Verossimilhança pela prova documental** · `probatorio` · BO e fotos corroboram a versão do autor.
3. **Comprovação e mitigação do dano material** · `quantum` · três orçamentos; adota-se o menor.

## Doc 14 — Execução fiscal (Tributário)
1. **Prescrição do crédito tributário** · `processual` · mais de 5 anos sem interrupção (art. 174 CTN).
2. **Inaplicabilidade da Súmula 106 do STJ** · `jurisprudencial` · demora atribuível à Fazenda, não ao Judiciário.
3. **Prejudicialidade da nulidade da CDA** · `processual` · reconhecida a prescrição, fica prejudicada a análise.

## Doc 15 — Alimentos (Família)
1. **Binômio necessidade-possibilidade** · `merito` · equilíbrio entre necessidade da criança e capacidade do pai.
2. **Capacidade contributiva presumida** · `probatorio` · indícios de renda informal afastam valor irrisório.
3. **Fixação em 30% do salário mínimo** · `quantum` · compatível com necessidade e possibilidade.

## Doc 16 — Vício do produto (Consumidor)
1. **Vício não sanado em 30 dias (art. 18 CDC)** · `merito` · legítima a opção pela restituição.
2. **Prova do defeito reiterado** · `probatorio` · três ordens de serviço afastam alegação de mau uso.
3. **Ausência de dano moral** · `merito` · mero descumprimento contratual = aborrecimento.

## Doc 17 — Despejo (Locação)
1. **Mora incontroversa autoriza despejo** · `merito` · cinco meses de aluguel (Lei 8.245/91).
2. **Comprovantes não correspondem ao débito** · `probatorio` · pagamentos de período diverso.
3. **Não purgação da mora** · `processual` · réu intimado não purgou no prazo legal.

## Doc 18 — Aposentadoria por invalidez (Previdenciário)
1. **Laudo pericial prevalece sobre avaliação administrativa** · `probatorio` · incapacidade total e permanente.
2. **Qualidade de segurado e carência comprovadas** · `probatorio` · conforme CNIS.
3. **Inviabilidade de reabilitação** · `merito` · idade e escolaridade → aposentadoria, não auxílio.

## Doc 19 — Revisão bancária (Bancário)
1. **Juros não abusivos por si só** · `jurisprudencial` · não destoam da média (Súmula 382 STJ).
2. **Capitalização lícita quando pactuada** · `merito` · cláusula 7ª expressa e válida.
3. **Tarifa de cadastro renovada é abusiva** · `merito` · restituição simples (sem má-fé).

## Doc 20 — Furto (Penal)
1. **Princípio da insignificância** · `principiologico` · quatro vetores do STF presentes.
2. **Restituição integral e valor ínfimo** · `merito` · reforça atipicidade material.
3. **Primariedade como reforço** · `merito` · corrobora desnecessidade da intervenção penal.

---

## Critério de qualidade (Q2)
- **Cobertura**: todos os argumentos do gabarito devem ser recuperados (recall).
- **Fidelidade**: nenhum argumento extraído sem `trecho_citado` literal (anti-alucinação).
- **Tipo**: classificação de `tipo` comparada ao gabarito.
- **Granularidade**: não fundir dois argumentos distintos em um, nem fragmentar um em vários.
