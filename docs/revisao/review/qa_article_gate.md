# QA LaTeX ABNT — artigo_final.tex
Data: 2026-07-13
Compilador: TinyTeX `~/Library/TinyTeX/bin/universal-darwin/pdflatex`
Gates: Overflow / Estrutura / ABNT / Figuras

## Resumo
- CRÍTICOS: 1
- MAIORES: 6
- MENORES: 3

## Evidência
- Build logs: `/tmp/qa_artigo_final_build1.log`, `/tmp/qa_artigo_final_build3.log`
- Figura QA: `docs/revisao/review/qa_figuras_report.md`

## Issues

### [CRÍTICO] artigo_final.tex — título duplicado impede compilação canônica
- Local: linha 39–45
- Descrição: `\title{... (NOC Lite)}}` duplica o fechamento do título, gerando `! Too many }'s.` e `Missing \begin{document}`. O PDF gera por resiliência do TeX, mas a compilação canônica com `bibtex` quebra porque `.aux` é instável.
- Evidência: `qa_artigo_final_build1.log`, `!` fatal, linha 40.
- Patch sugerido: remover a repetição final; garantir exatamente um `}` no `\title`.

### [MAIOR] artigo_final.tex — Overfull em abstract/palavras-chave
- Local: linhas 173–198, 200–203
- Descrição: 2 hboxes estouram por ~1.5–3.5pt no abstract e palavras-chave.
- Evidência: `Overfull \hbox (1.3467pt ...)` e `(3.52426pt ...)`.
- Patch sugerido: reescrita leve do abstract; não há `\tableofcontents` neste arquivo, então adicioná-lo também ajuda na estrutura.

### [MAIOR] artigo_final.tex — Overfull massivo em seção Pipeline (~74pt–103pt)
- Local: linhas 441–460 e 481–489
- Descrição: bloco com nomes de classes, `DecisionTreeClassifier(max_depth=5)` e `anomaly_simulator.py` estouram em até 103pt.
- Evidência: `Overfull \hbox (74.92397pt ...)`, `(88.39566pt ...)`, `(103.40869pt ...)`.
- Patch sugerido: quebras explícitas antes dos tokens longos; trocar para `\raggedright` no parágrafo ou `sloppy` local se necessário.

### [MAIOR] artigo_final.tex — Underfull badness 10000 generalizado em longtable
- Local: linhas 514–525, 557–563
- Descrição: múltiplas células ficam Underfull em `longtable` do mapeamento/gaps.
- Evidência: `Underfull \hbox (badness 10000)` recorrendo em 12+ linhas.
- Patch sugerido: aumentar larguras das `p{...}` com pelo menos 1.8cm; usar `>{\raggedright}`; evitar coluna muito estreita.

### [MAIOR] artigo_final.tex — longtable com aviso “Column widths have changed / Table widths have changed”
- Local: linha 527 e 565
- Descrição: tabelas mudam de largura entre passadas; `build3.log` ainda emite rerun, indicando problema estrutural nas colunas.
- Evidência: `Package longtable Warning: Column widths have changed`, `Package longtable Warning: Table widths have changed. Rerun LaTeX.`
- Patch sugerido: unificar larguras via `>{\raggedright\arraybackslash}p{Xcm}` e `\setlength{\tabcolsep}{...}`; remover `minipage`/`parbox` conflitantes.

### [MAIOR] artigo_final.tex — Referências indefinidas / Rerun pendente
- Local: geral
- Descrição: `fig:pipe`, `tab:mapa`, `fig:mapa`, `tab:gaps`, `fig:gaps`, `fig:ciclo` aparecem como `undefined` no build3; aviso `Label(s) may have changed. Rerun`.
- Evidência: `LaTeX Warning: Reference 'fig:pipe' ... undefined`, `LaTeX Warning: Label(s) may have changed. Rerun to get cross-references right.`
- Patch sugerido: garantir `\label` em TODOS os floats; recompilar até que `Reference undefined` seja 0; não entregar enquanto existir.

### [MAIOR] artigo_final.tex — 0 sumário
- Local: estrutura
- Descrição: `grep -c '\\tableofcontents' artigo_final.tex` retorna 0.
- Evidência: `===TOC=== 0`.
- Patch sugerido: inserir `\tableofcontents` após `\maketitle` e antes de `\section{Introdução}`.

### [MENOR] artigo_final.tex — hyperref Warning: token não permitido em PDF string
- Local: abstract e seções com `\times`
- Descrição: warnings `math shift` e `\times` removidos de strings do PDF.
- Evidência: `Package hyperref Warning: Token not allowed in a PDF string (Unicode)` x3.
- Patch sugerido: evitar `$\times$` em `\section{}`/`\caption{}`/`\title{}` e usar `\texorpdfstring{$\times$}{\texttimes}` quando necessário.

### [MENOR] artigo_final.tex — títulos/subtítulos com quebras por hifenização excessiva
- Local: linha 363
- Descrição: `Overfull \hbox (24.52936pt ...)` em título de `\subsection{Fine-Tuning ...}`.
- Evidência: mesma linha do build3.
- Patch sugerido: reescrever título mais curto ou obrigar quebra com `\\` explícito.

### [MENOR] artigo_final.tex — bibtex erro “I found no \bibdata command”
- Local: `.aux`
- Descrição: `bibtex artigo_final` falha porque o arquivo não declara `\bibliography`/`\bibdata` — usa `\begin{thebibliography}` manual.
- Evidência: `Warning--I didn't find a database entry for "abnt-url-package=url"` + `There was 1 error message`.
- Patch sugerido: declarar caminho no `.aux` via `\bibliography{referencias_autor_data}` ou remover a etapa `bibtex` do script de compilação canônica deste arquivo.

## Contagem final
- CRÍTICO: 1
- MAIOR: 6
- MENOR: 3
Total: 10
