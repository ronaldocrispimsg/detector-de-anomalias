# QA LaTeX ABNT — artigo_final.tex
Data: 2026-07-13
Compilador: /Users/marcio/Library/TinyTeX/bin/universal-darwin/pdflatex
Gates: Estrutura / Overflow / ABNT / Figuras
Evidence source: artigo_final.log; qa-latex-abnt script v1; PDf Gerado: artigo_final.pdf

## Resumo
- CRÍTICOS: 3
- MAIORES: 37
- MENORES: 8
- Verdicto atual: FAIL — não apto para entrega/revisão sem correção.

---

## Críticos

### [CRÍTICO] Título duplicado com `! Too many }'s` / `Missing \begin{document}`
- Local: `artigo_final.tex` linha 38-40.
- Problema: conteúdo colado após `\title{...\}}`, que quebra a lexia before `\begin{document}`.
- Evidência log: `! Too many }'s. l.40 ...uisa e o Sistema Implementado (NOC Lite)}}`; `! LaTeX Error: Missing \begin{document}.`
- Severidade atual: CRÍTICO
- Correção sugerida: manter só um título dentro de `\title{...}` e remover o sufixo extra.

### [CRÍTICO] `\tableofcontents` ausente
- Local: `artigo_final.tex` checagem estrutural.
- Evidência: script `latex_abnt_qa.py` reportou `has_toc: false`.
- Severidade atual: CRÍTICO
- Correção sugerida: inserir `\tableofcontents` após `\maketitle` e antes das seções.

### [CRÍTICO] `Rerun` pendente
- Local: `artigo_final.log`.
- Evidência: `sample_rerun_or_undefined: ["Rerun"]`.
- Severidade atual: CRÍTICO
- Correção sugerida: rodar pdflatex -> bibtex -> pdflatex -> pdflatex; confirmar estabilidade.

---

## Maiores

### [MAIOR] Overfull/Underfull massivo
- Total coletado: 25 overfull; 21 underfull hbox; 1 rerun/undefined matching line.
- Impacto: tabelas longas e parágrafos estouram margens, afetando impressão/leitura.
- Evidência: `overfull_hbox_count`, `underfull_hbox_count` do script.
- Correção sugerida:
  - `longtable`: usar `p{1.8cm}` com `>{\raggedright\arraybackslash}`; revisar 5 colunas fixas vs `\textwidth`.
  - Títulos longos: evitar `\section{...}` com `|`; preferir quebras controladas e `\linebreak`.
  - Underfull de texto: reformular parágrafo ou habilitar `\sloppy`/`\emergencystretch` se tolerado.
- Responsável: George/Chris ajusta `.tex`; Chris valida figuras; George recompila.

---

## Menores

### [MENOR] Underfull tolerável pode virar MAIOR se worst-case crescer
- Exemplos: badness 6445 em linha 521; badness 3000 em linha 522.
- Ação: documentar como aceito, com patch textual opcional.

---

## Check ABNT/referências
- Tags editoriais: `editorial_tags_in_citea: []` / `editorial_tags_in_bibitems: []`.
- Conclusão antes de bib: `bibliography_after_conclusion: true`.

## Check figuras/tabelas
- Referências `\ref`: figuras/tabelas com label e caption estão presentes no `.tex`.
- `duplicate_ignored`: 0.
- `missing`: 0.

---

## Próximos passos recomendados
1. Corrigir título linha 38-40 e inserir `\tableofcontents`.
2. Recompilar ciclo pdflatex+bibtex+2x pdflatex até `Rerun` sumir.
3. Ajustar `longtable` de linhas 503-527 e 546-566 com largura fixa por célula.
4. Re-executar `latex_abnt_qa.py` e esperar CRÍTICOS=0, MAIORES=0, MENORES<=aprovados.
