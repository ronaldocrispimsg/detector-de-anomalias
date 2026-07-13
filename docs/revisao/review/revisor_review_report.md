# Relatório de Revisão — ARTIGO FINAL (NOC Lite × Projeto de Pesquisa RODRIGUES, 2026)

Data: 2026-07-13
Revisor: Richard (guardião ABNT/IEEE, qualidade científica e textual)

## Sumário Executivo

- **Total de issues:** 18 (5 CRÍTICOS, 7 MAIORES, 6 MENORES)
- **Críticos:** 5 — todos na seção de Referências / afirmações de contagem
- **Maiores:** 7 — normativa ABNT (ordem, autor-data), órfãos/duplicados, figura, terminologia
- **Menores:** 6 — polimento (contagens, URLs, tags vazadas, seção de método)
- **Status Geral:** **REPROVADO**
- **Compilação:** pdflatex compila sem erro (saída `artigo.pdf`, 1 passada, 0 `Citation undefined` / 0 `Undefined reference`). Os defeitos são de **conteúdo/norma**, não de build.
- **Ponto forte:** Estrutura IMRaD adaptada (Introdução → Referencial → Sistema → Mapeamento/Gaps → Discussão → Diretrizes → Conclusão) está coerente; o mapeamento artigo×sistema e a taxonomia de gaps **condizem com** `arquitetura_sistema.md` (Dan) e `notas_coder.md` (John) — nenhuma contradição com o código foi detectada.

> Motivo da reprovação: a seção de Referências não está em conformidade ABNT em múltiplos eixos (ordem alfabética ausente, citação numérica em vez de autor-data, 92 entradas órfãs, 1 entrada duplicada do projeto norteador, nota editorial vazada no corpo de uma entrada, 1 entrada explicitamente "NÃO VERIFICADO" incluída numa lista dita "validada", e afirmação quantitativa "216 referências validadas" incompatível com a própria bibliografia). Há também desvio terminológico do projeto norteador ("degradação espectral") e legenda de figura incompleta.

---

## Issues

### [CRÍTICO] C1 — Referências órfãs (92 bibitems nunca citados)
- **Local:** `referencias.tex` (218 `\bibitem`; apenas 126 chaves são citadas em `artigo.tex` via `\cite`)
- **Descrição:** 92 entradas da bibliografia NÃO são referenciadas em nenhum ponto do texto. Exemplos: `rA328, rA326, rA38, rA340, rA329, rA330, rA24, rA233, rA228, rA434, rA331, rA410, rA236, rA216, rA436, rA13, rA322, rA535, rA524, rA530, rA523, rA536, rA518, rA519, rA626, rA625, rA619, rA622, rA613, rA620, rA120, rA525, rA223, rA18, rA234, rA211, rA429, rA111, rA413, rA118, rA112, rA433, rA113, rA437, rA48, rA46, rA47, rA339, rA220, rA215, rA117, rA17, rA428, rA529, rA55, rA513, rA538, rA515, rA58, rA56, rA528, rA514, rA57, rA510, rA516, rA59, rA527, rA526, rA67, rA68, rA621, rA611, rA612, rA624, rRODRIGUES2026, rA235, rA430, rA214, rA221, rA16, rA417, rA219, rA218, rA418, rA419, rA125, rA323, rA119, rA121, rA23, rA435, rA416` (lista completa no script `review/_check_refs.py`).
- **Sugestão de correção:** Remover todas as entradas não citadas, OU citá-las no texto onde pertinente. Para ABNT, referência não citada não deve constar da lista. Recomenda-se poda agressiva + recontagem.
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [CRÍTICO] C2 — Entrada duplicada/órfã do projeto norteador (RODRIGUES)
- **Local:** `referencias.tex` linha 2 (`\bibitem{rRODRIGUES}`, a efetivamente citada 5×) e linha 185 (`\bibitem{rRODRIGUES2026}`, **órfã e duplicada**)
- **Descrição:** O projeto norteador aparece DUAS vezes na bibliografia. A citada em todo o texto é `rRODRIGUES` (linha 2, forma resumida). A linha 185 cria uma segunda entrada `rRODRIGUES2026` (forma completa "João Pedro Santos Rodrigues … Januária, MG") que **nunca é citada** e repete o mesmo trabalho.
- **Sugestão de correção:** Eliminar `rRODRIGUES2026`; manter única e corrigir a forma para "RODRIGUES, João Pedro Santos" (conforme `goal.pdf`), mantendo `rRODRIGUES`.
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [CRÍTICO] C3 — Nota editorial vazada no corpo de uma referência
- **Local:** `referencias.tex` linha 8 (`\bibitem{rA340}`)
- **Descrição:** A entrada traz texto de marcação interna de revisão: *"Large Language Models Meet Next-Generation Networking Technologies: A Review" (vide [4]) também cobre segurança de LLM em redes. (Incluído por overlaps temáticos; contagem principal permanece em [4]).* Esse artefato (proveniente dos `areaNN_*.txt`) é inaceitável numa lista de referências — um leitor não tem "[4]" nem sabe o que é "contagem principal".
- **Sugestão de correção:** Substituir por entrada limpa: `LEIVADEAS, A.; FALKNER, M. A Survey on Intent-Based Networking. IEEE Communications Surveys & Tutorials, v. 25, n. 1, p. 625–655, 2023. DOI:10.1109/COMST.2022.3215919.` (ou a entrada rA133 já existente, que é a mesma — consolidar).
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [CRÍTICO] C4 — Referência explicitamente "NÃO VERIFICADO" incluída como validada
- **Local:** `referencias.tex` linha 90 (`\bibitem{rA27}`) e afirmação em `artigo.tex` linha 135
- **Descrição:** A entrada `rA27` contém literalmente *"[NÃO VERIFICADO — usar URL abaixo; artigo de 2026 ainda em indexação]"* dentro do campo de URL. Ora, o texto (linha 135) afirma ter feito "revisão de literatura com 216 referências **validadas**". Incluir uma fonte não verificada numa lista dita validada é quebra de integridade.
- **Sugestão de correção:** Ou remover `rA27` da bibliografia (pois não validada), ou efetivamente validá-la (acessar/confirmar o DOI/URL) e retirar a marcação "NÃO VERIFICADO" antes de publicar.
- **Responsável pela correção:** george (com verificação de pesquisador_estado_arte para confirmar a fonte FONDO-FERREIRO et al., 2026)
- **Status:** [PENDENTE]

### [CRÍTICO] C5 — Afirmação quantitativa incompatível com a própria bibliografia
- **Local:** `artigo.tex` linha 135 ("… revisão de literatura com **216 referências validadas**")
- **Descrição:** A bibliografia define 218 `\bibitem` e **cita apenas 126**; dentre as 218, 92 são órfãs (C1) e 1 é não verificada (C4). Logo a contagem "216 validadas" é insustentável: (a) não bate com as 126 efetivamente citadas; (b) inclui entradas não validadas.
- **Sugestão de correção:** Ajustar o número para a contagem real das referências efetivamente citadas e validadas APÓS a poda (C1) e validação (C4). Ex.: reescrever como "revisão de literatura estruturada em seis eixos, com N referências efetivamente citadas neste artigo".
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [MAIOR] M1 — Ordem da lista de referências não é ABNT (alfabética)
- **Local:** `referencias.tex` (todo o bloco `thebibliography`)
- **Descrição:** A ABNT NBR 6023 exige ordenação **alfabética por sobrenome do autor**. A lista está agrupada por eixo temático (area01→area06), iniciando em `rA328` e pulando para `rA335, rA326…` — ordem arbitrária.
- **Sugestão de correção:** Reordenar todas as 218 entradas (ou as 126 citadas, após poda) em ordem alfabética ABNT.
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [MAIOR] M2 — Citações numéricas [n] divergem da norma ABNT (autor-data)
- **Local:** `artigo.tex` (todo o texto usa `\cite{...}` → renderiza `[n]`); `referencias.tex` usa `thebibliography` numérico
- **Descrição:** A ABNT NBR 10520 prescreve citação **(AUTOR, ano)** no corpo do texto. O artigo usa numeração sequencial `[45]`, o que não é ABNT. O mecanismo autor-data existe (`citacoes.tex` com macros `\qAxx`) mas **nunca é carregado**: `artigo.tex` não contém `\input{citacoes}` e há **0** ocorrências de `\qAxx` no texto. O cabeçalho do próprio `artigo.tex` (linhas 33-39) afirma "(autor, ano)" — afirmação falsa na prática.
- **Sugestão de correção:** (a) Integrar `citacoes.tex` via `\input{citacoes}` e substituir `\cite{rAxx}` por `\qAxx` no texto (citação autor-data ABNT); OU (b) adotar a classe `abntex2`/`abntex2cite` com `biblatex-abnt`. Escolher UMA estratégia e aplicá-la de ponta a ponta.
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [MAIOR] M3 — `citacoes.tex` é código morto / inconsistente
- **Local:** `citacoes.tex` (221 linhas, 0 macros usados); `artigo.tex` (sem `\input{citacoes}`)
- **Descrição:** O arquivo define `\qRODRIGUES`, `\qA11`… mas nenhum é invocado. Há ainda macros com ano corrompido (ver N4). O arquivo sugere uma intenção autor-data abandonada, deixando o artigo em estado numérico não-ABNT.
- **Sugestão de correção:** Ou integra-lo conforme M2, ou removê-lo para evitar confusão de manutenção.
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [MAIOR] M4 — Nome de autor corrompido na entrada rA512
- **Local:** `referencias.tex` linha 75 (`\bibitem{rA512}`) — "Neupane, S.; Ables, M.; Chen, W.; **D blast**, M.; …"
- **Descrição:** "D blast" é uma corrupção de OCR/transferência (autor provável: inicial "D." + sobrenome). A mesma corrupção está na fonte `literature/area05_xai.txt` linha 178. A entrada citada em `artigo.tex` (linhas 404, 496 via `\cite{rA512}`) exibe o nome quebrado.
- **Sugestão de correção:** Confirmar a grafia correta do 4º autor com `pesquisador_estado_arte` (X-IDS survey, Neupane et al., IEEE Access 2022) e corrigir em `area05_xai.txt` + `referencias.tex`.
- **Responsável pela correção:** george (com pesquisador_estado_arte para a grafia exata)
- **Status:** [PENDENTE]

### [MAIOR] M5 — Legenda da Figura de Gaps incompleta (5 de 7 gaps)
- **Local:** `figures/fig_gaps_caption.txt` (legenda fornecida por Chris) vs `artigo.tex` linhas 356-406 (texto e Tabela `tab:gaps` descrevem 7 gaps: GAP-1…GAP-7)
- **Descrição:** A legenda sugerida para `fig_gaps` lista apenas **GAP-1 a GAP-5** (e omite GAP-6 e GAP-7). O artigo, porém, trata 7 gaps. Se a figura em PDF efetivamente mostrar só 5, há desalinhamento visual com o texto; se mostrar 7, a legenda fornecida está errada. Em ambos os casos a legenda deve espelhar os 7 gaps.
- **Sugestão de correção:** Chris revisar `fig_gaps.pdf` e sua legenda para contemplar GAP-1…GAP-7 (crítico/maior/menor), alinhando com a Tabela `tab:gaps`.
- **Responsável pela correção:** chris
- **Status:** [PENDENTE]

### [MAIOR] M6 — Terminologia do projeto norteador incorreta ("degradação espectral")
- **Local:** `artigo.tex` linha 378 ("congestionamento, falha de enlace, **degradação espectral**") e linha 404 (mesmo termo)
- **Descrição:** O `goal.pdf` (fonte norteadora, p. 1 e Resumo) descreve as anomalias-alvo como "congestionamento transiente, falhas de enlace e **degradação de desempenho**". O termo "espectral" **não aparece** no projeto em lugar algum. O erro foi, inclusive, propagado para `arquitetura_sistema.md` (Dan, linha 112), mas a autoridade é o `goal.pdf`.
- **Sugestão de correção:** Substituir "degradação espectral" por "degradação de desempenho" nas linhas 378 e 404 (e, se aplicável, alinhar `arquitetura_sistema.md`).
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [MAIOR] M7 — Duplicação de trabalhos sob chaves distintas infla a bibliografia
- **Local:** `referencias.tex`
- **Descrição:** Vários trabalhos aparecem 2× com chaves diferentes (mesmo paper, mesma URL):
  - LLaMA: `rA310` (TOUVRON et al. 2023, arXiv:2302.13971) e `rA418` (mesmo)
  - Llama 2: `rA311` (arXiv:2307.09288) e `rA419` (mesmo)
  - LoRA: `rA41` (HU et al. 2021, arXiv:2106.09685) e `rA318` (mesmo paper, ano duplicado)
  - Mistral 7B: `rA312`, `rA420`, `rA421` (três cópias de arXiv:2310.06825)
  - Chain-of-Thought: `rA321` e `rA423` (mesmo arXiv:2201.11903)
- **Sugestão de correção:** Consolidar cada par/trio em UMA entrada; ajustar as citações no texto para a chave única mantida.
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [MENOR] N1 — Contagem interna de gaps incoerente
- **Local:** `artigo.tex` linha 359 ("sete gaps, **cinco** de severidade crítica/maior")
- **Descrição:** A Tabela `tab:gaps` tem 6 entradas de severidade crítica/maior (GAP-1…GAP-4 = Crítico; GAP-5, GAP-6 = Maior) e 1 Menor (GAP-7). "Cinco" deveria ser "seis".
- **Sugestão de correção:** Corrigir para "seis de severidade crítica/maior".
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [MENOR] N2 — Espaços dentro de URLs em `\url{}`
- **Local:** `referencias.tex` (ex.: `rA332` "S1389128625006140", `rA128` "gs_NFV002v010101p.pdf", `rA129`, `rA116` "ntr201408fa4.html", `rA16`, `rA340`)
- **Descrição:** Espaços em branco dentro de URLs podem quebrar o hiperlink ao compilar com `hyperref`.
- **Sugestão de correção:** Remover os espaços internos nas URLs.
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [MENOR] N3 — Tags de classificação vazadas no corpo das entradas
- **Local:** `referencias.tex` (dezenas de entradas: `rA511, rA52, rA531, rA54, rA512, rA53, rA616, rA62, rA64, rA61, rA63, rA69, rA65, rA66, rA67, rA624, rA617, rA522, rA520, rA523, rA536, rA521, rA518, rA519, rA530, rA524, rA528, rA514, rA533, rA57, rA510, rA516, rA517, rA527, rA526, rA534, rA623, rA614, rA67, rA610, rA618, rA68, rA621, rA615, rA611, rA612, rA630`…)
- **Descrição:** Prefixos "ESSENCIAL ", "RECOMENDADO ", "COMPLEMENTAR " (e "—") foram transferidos dos `areaNN_*.txt` para o início do corpo das referências. Em ABNT não se usa essa marcação.
- **Sugestão de correção:** Remover os prefixos de classificação de todas as entradas.
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [MENOR] N4 — Ano inconsistent no macro morto (`citacoes.tex`)
- **Local:** `citacoes.tex` linha 149 (`\def\qA45}{(HOULSBY et al., 1902)}`) vs `referencias.tex` linha 106 (`rA45`: "ICML, 2019")
- **Descrição:** O ano "1902" está errado (deve ser 2019). Como `citacoes.tex` não é usado (M2/M3), não afeta a compilação, mas é dado corrompido em código versionado.
- **Sugestão de correção:** Corrigir para 2019 ou remover `citacoes.tex` (vide M3).
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

### [MENOR] N5 — Explicitar método de revisão (corpus de análise)
- **Local:** `artigo.tex` Seção 2 (Referencial Teórico), a partir da linha 131
- **Descrição:** Sendo "revisão integrativa e análise arquitetural", o artigo não declara o procedimento de seleção das 6 áreas nem como as referências foram validadas. Uma subseção breve "Método / Corpus de Análise" (origem: `areaNN_*.txt`, critérios de inclusão, nº de fontes) reforçaria a norma de revisão sistemática e evitaria a fragilidade exposta em C5.
- **Sugestão de correção:** Inserir parágrafo curto descrevendo o corpus e o método de revisão antes ou após a linha 135.
- **Responsável pela correção:** george
- **Status:** [PENDENTE]

---

## Pendências por Persona

- **george** (escrita acadêmica ABNT — correções textuais/normativas):
  - C1 (podar 92 órfãs), C2 (remover RODRIGUES duplicado), C3 (limpar nota editorial rA340), C4 (validar/remover rA27), C5 (recontar "216 validadas"), M1 (ordenar ABNT), M2 (autor-data ou abntex2), M3 (integrar/remover citacoes.tex), M6 ("degradação espectral"→"desempenho"), M7 (consolidar duplicados), N1 (seis gaps), N2 (URLs sem espaço), N3 (remover tags), N4 (ano HOULSBY), N5 (método de revisão).
- **pesquisador_estado_arte** (verificação de fontes):
  - C4 (confirmar/validar FONDO-FERREIRO et al., 2026 — rA27)
  - M4 (confirmar grafia exata do 4º autor de Neupane et al. 2022 — rA512)
- **chris** (figuras):
  - M5 (revisar `fig_gaps.pdf` + legenda para contemplar os 7 gaps GAP-1…GAP-7)
- **coder** (John):
  - Nenhuma pendência. O texto do artigo condiz com `arquitetura_sistema.md` e `notas_coder.md`; os limiares (50 Mb/s, 120 ms), as 6 classes, o `tokenise_metrics`, o `gemini-1.5-flash`, o loop aberto e os gaps estão fiéis ao código. Não há contradição metodologia×implementação.

---

## Aprovação

- [ ] Nenhum issue CRÍTICO pendente → **FALHOU** (5 CRÍTICOS pendentes: C1–C5)
- [ ] Nenhum issue MAIOR pendente que afete coesão/metodologia → **FALHOU** (M1–M7, incluindo norma ABNT de referências e terminologia do projeto)
- [ ] Referências verificadas → **FALHOU** (92 órfãs, 1 não verificada, 1 duplicada, nota editorial vazada)
- [ ] Normativa ABNT ok → **FALHOU** (ordem alfabética ausente; citação numérica em vez de autor-data; tags vazadas; URLs com espaço)

**Status Geral: REPROVADO.**

Caminho para aprovação: george deve executar a poda/ordenação/consolidação da bibliografia (C1, C2, C3, M1, M7, N2, N3), decidir e aplicar a estratégia autor-data (M2/M3), corrigir terminologia (M6) e contagens (C5, N1); pesquisador_estado_arte valida rA27 (C4) e a grafia de rA512 (M4); chris ajusta a legenda de `fig_gaps` (M5). Após correções, Richard re-avalia apenas os itens [PENDENTE] e atualiza este relatório.
