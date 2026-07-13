# QA de Figuras — Watson

Data: 2026-07-13
Agente: Watson (tester / QA)
Escopo: QA completo das 5 figuras em `docs/revisao/figures/` conforme checklist de 7 itens da skill `qa-figuras-latex`.
Compilador: pdflatex (TinyTeX em `/Users/marcio/Library/TinyTeX/bin/universal-darwin`)
Render: `sips -s format png <fig>.pdf --out <fig>.png`
Inspeção: `vision_analyze` em cada PNG (incluindo varredura em alta resolução de 2400px para confirmar truncamentos).

## Resumo Executivo
Total figuras: 5 | CRÍTICOS: 0 | MAIORES: 4 | MENORES: 3

Contagem estrita por entrada numerada na seção "Issues":
- MAIOR (4): arquitetura_sistema [1]; pipeline_classificacao [2]; pipeline_classificacao [3]; ciclo_fechado_proposto [4].
- MENOR (3): ciclo_fechado_proposto [espaço pós-\\]; pipeline_classificacao [2 Underfull]; mapeamento_artigo_sistema [1 Underfull].

Todas as 5 figuras **compilam** com `exit=0`, **sem erros** e **sem Overfull** (0 em todos os logs). Nenhuma falha de compilação = nenhum CRÍTICO por build. Contudo, 3 figuras apresentam **texto truncado/cortado na borda de caixas** (confirmado em alta resolução) e/ou **palavras grudadas sem espaço** ("deMonitoramento", "Classificadorde") — classificados como **MAIOR** (quebram a leitura). Não há overlays de setas cruzando caixas nem texto-sobre-texto de conteúdo diverso. Legibilidade P&B e captions/`\ref` estão OK em todas.

| Figura | Compila | Overfull | Overlay texto | Seta cruza caixa | Texto estoura | Símbolos desal. | P&B | Caption/ref | Issues |
|---|---|---|---|---|---|---|---|---|---|
| fig_arquitetura_sistema | OK | 0 | não | não | SIM (MAIOR) | não | OK | OK | 1 MAIOR |
| fig_pipeline_classificacao | OK | 0 | não | não | SIM (MAIOR) | não | OK | OK | 2 MAIOR |
| fig_mapeamento_artigo_sistema | OK | 0 | não | n/a | não | não | OK | OK | 0 |
| fig_gaps | OK | 0 | não | não | não | não | OK | OK | 0 |
| fig_ciclo_fechado_proposto | OK | 0 | não | não | SIM (MAIOR) | não | OK | OK | 1 MAIOR + 2 MENOR |

## Issues

### [MAIOR] fig_arquitetura_sistema.tex — caixa "Front-end" e crowding de caixas
- Problema: (a) A caixa `Front-end (HTML/JS + http.server)` tem o texto **truncado na borda direita** — falta o parêntese de fechamento e a palavra parece cortada ("...http.server"). (b) As duas caixas da linha superior (`Front-end` e `API Backend`) estão muito próximas (separadas por apenas 0.6cm de centro, com larguras de 3.2cm e 3.6cm), gerando crowding onde o fim de uma palavra encosta no início da outra (leitura confusa "http.server ... API"). (c) Quebra de linha por `\\` em nós `box` com `text centered` + `minimum width` fixa está produzindo **palavras grudadas sem espaço**: "deMonitoramento" e "Classificadorde" (o `\\` separa linhas mas o espaço após a quebra some dentro do alinhamento centralizado).
- Evidência: `vision_analyze` em PNG padrão e em alta resolução (2400px) — ambos relatam truncamento de borda em `Front-end` e palavras coladas ("deMonitoramento", "Classificadorde"). Log: 0 Overfull, 0 `!`.
- Correção sugerida (patch exato para o Chris):
  - Aumentar `inner sep` / `minimum width` das caixas e separar os centros. Sugestão: `Front-end` em `minimum width=3.8cm` em x=2.2; `API Backend` em `minimum width=4.2cm` em x=7.0 (gap confortável).
  - Substituir o `\\` por `\\ ` (barra invertida + espaço) OU usar `align=center` explícito com `text width` para forçar o espaço após a quebra. Ex.:
    `\node[box, text width=3.4cm, align=center] (mon) at (1.8,5.6) {Motor de\\ Monitoramento\\ (asyncio)};` (note o espaço após `\\`).
  - Para `Front-end`, garantir `text width` suficiente para "http.server)" não cortar: `\node[box, text width=3.4cm, align=center] (fe) at (2.0,8.7) {Front-end\\ (HTML/JS + http.server)};`
- Responsável: chris (corrige o .tex)

### [MAIOR] fig_pipeline_classificacao.tex — caixas da fileira superior com texto truncado na borda
- Problema: As 5 caixas da fileira horizontal superior (`stage`/`cls`, `minimum width` 2.6–3.0cm) têm texto **cortado nas bordas verticais internas** (confirmado em alta resolução): "extract_features_from_db" perde o 'e' inicial, "tokenise_metrics" perde o 't' inicial, e a caixa de saída corta a borda esquerda. O texto longo não cabe na `minimum width` e, como não há `text width`, ele transborda/encosta na borda sem quebrar.
- Evidência: `vision_analyze` alta resolução: "as bordas esquerdas cortam as primeiras letras das palavras ('e' em extract e 't' em tokenise), deixando o texto visivelmente incompleto". Log: 0 Overfull (o TikZ não emite Overfull para nós sem `text width`), 0 `!`. Há 2 `Underfull \hbox` (badness 1472/3271) nas linhas de thresholds.
- Correção sugerida (patch exato para o Chris):
  - Dar `text width` + `align=center` (ou `align=left`) a cada nó da fileira e aumentar `minimum width`:
    `stage/.style={..., text width=2.4cm, align=center, minimum width=2.6cm}`
    `cls/.style={..., text width=2.6cm, align=center, minimum width=2.8cm}`
  - Reajustar as posições em x para acomodar caixas maiores (ex.: espaçar de 3.4 em 3.4 para ~3.8–4.0).
  - Os `Underfull` são inofensivos (math mode de thresholds), mas aliviam com `\raggedright` ou quebra explícita nas linhas longas.
- Responsável: chris (corrige o .tex)

### [MAIOR] fig_pipeline_classificacao.tex — "DDOS_ATTACK" na mesma linha da regra anterior
- Problema: Na caixa tracejada "Thresholds-chave", o item `DDOS_ATTACK` aparece **na mesma linha** que a condição `net_in > 50 Mbps & cpu > 75% =>`, sem quebra de linha própria (a seta de implicação `=>` puxa o resultado para a mesma linha). Lê-se como "net_in > 50 Mbps & cpu > 75% => DDOS_ATTACK" numa linha só, apertado e confuso.
- Evidência: `vision_analyze` alta resolução confirma "Está na MESMA LINHA ... não há quebra de linha antes dele".
- Correção sugerida (patch exato para o Chris): forçar quebra antes do resultado, ex.:
  `$\bullet$ net\_in \textgreater{} 50 Mbps \& cpu \textgreater{} 75\% $\Rightarrow$ \\ DDOS\_ATTACK\\`
  (a `\\` após `$\Rightarrow$` joga o "DDOS_ATTACK" para a linha seguinte, dentro da mesma célula). Repetir padrão para os demais itens se desejado.
- Responsável: chris (corrige o .tex)

### [MAIOR] fig_ciclo_fechado_proposto.tex — caixas da fileira superior com texto truncado na borda
- Problema: As caixas `Features + tokenise_metrics` e `Classificação LLM open-source (LoRA)` têm o texto **cortado nas bordas verticais internas** (a letra inicial 'F' e 'C' cortadas na esquerda; 's' final de "metrics" e ')' final de "(LoRA)" cortados na direita). `Mitigação / reconfig. SDN` está apenas encostada na borda (apertada, limítrofe). Causa: `minimum width=3.2cm` insuficiente + ausência de `text width`.
- Evidência: `vision_analyze` alta resolução: "a letra 'F' inicial está cortada pela borda esquerda ... a letra 's' final de 'metrics' está cortada pela borda direita"; idem para 'C'/(LoRA). Log: 0 Overfull, 0 `!`.
- Correção sugerida (patch exato para o Chris):
  - Adicionar `text width` + `align=center` e aumentar `minimum width` no estilo `box`/`prop`:
    `box/.style={..., text width=2.9cm, align=center, minimum width=3.2cm, inner sep=4pt}`
    `prop/.style={..., text width=2.9cm, align=center, minimum width=3.2cm, inner sep=4pt}`
  - Para `Mitigação / reconfig. SDN` ( texto longo em 2 linhas), considerar `text width=3.4cm`.
  - Reespaçar as posições em x (3.4 → ~3.9 de passo) para não colar as caixas.
- Responsável: chris (corrige o .tex)

### [MENOR] fig_ciclo_fechado_proposto.tex — ausência de espaço pós-`\\` (estilo)
- Problema: Mesmo padrão de "palavra grudada" observado em outras figuras (quebra `\\` sem espaço). Aqui menos crítico por não truncar, mas vale padronizar: usar `\\ ` ou `text width`+`align` para garantir espaço após quebras.
- Evidência: inspeção do `.tex`; nós com `text centered` e `\\`.
- Correção sugerida: aplicar `text width`+`align=center` aos nós (já coberto no patch MAIOR acima).
- Responsável: chris (corrige o .tex)

### [MENOR] fig_pipeline_classificacao.tex — 2 Underfull \hbox (thresholds)
- Problema: `Underfull \hbox (badness 1472 e 3271)` nas linhas 53 e 56 (regras de thresholds com `$\bullet$ ... $)`). Não quebra layout, mas indica espaçamento frouxo em math mode.
- Evidência: `grep -A2 Underfull fig_pipeline_classificacao.log`.
- Correção sugerida: adicionar quebra de linha explícita após cada regra ou usar `\raggedright` na caixa; ou ignorar (cosmético).
- Responsável: chris (corrige o .tex)

### [MENOR] fig_mapeamento_artigo_sistema.tex — 1 Underfull \hbox
- Problema: `Underfull \hbox (badness 10000)` na linha 27 ("Hosts IP genéricos"). Cosmético; a tabela compila e o texto cabe na célula.
- Evidência: `grep -A2 Underfull fig_mapeamento_artigo_sistema.log`.
- Correção sugerida: opcional — ajustar `text width` da coluna ou deixar como está (não afeta legibilidade).
- Responsável: chris (corrige o .tex)

## Checklist de 7 itens (por figura)

### fig_arquitetura_sistema
1. Compilação: PASS (exit=0, 0 erros). 2. Overlays de texto: PASS. 3. Setas cruzando caixa: PASS. 4. Texto estourando: **FALHA (MAIOR)** — truncamento em `Front-end` + palavras grudadas. 5. Símbolos desalinhados: PASS (sem símbolos). 6. Legibilidade P&B: PASS. 7. Caption/ref: PASS (`fig:arq` em artigo.tex:259; `\includegraphics` em :256).

### fig_pipeline_classificacao
1. Compilação: PASS. 2. Overlays: PASS. 3. Setas cruzando: PASS. 4. Texto estourando: **FALHA (MAIOR ×2)** — truncamento das 5 caixas + DDOS_ATTACK na mesma linha. 5. Símbolos: PASS. 6. P&B: PASS. 7. Caption/ref: PASS (`fig:pipe` :276; `\includegraphics` :272). Obs: 2 Underfull (MENOR).

### fig_mapeamento_artigo_sistema
1. Compilação: PASS. 2. Overlays: PASS. 3. Setas cruzando: n/a (tabela). 4. Texto estourando: PASS. 5. Símbolos desalinhados: PASS (✓/=/✗ centralizados). 6. P&B: PASS. 7. Caption/ref: PASS (`fig:mapa` :353; `\includegraphics` :350). Obs: 1 Underfull (MENOR, inofensivo).

### fig_gaps
1. Compilação: PASS. 2. Overlays: PASS. 3. Setas cruzando: PASS. 4. Texto estourando: PASS. 5. Símbolos: PASS. 6. P&B: PASS. 7. Caption/ref: PASS (`fig:gaps` :388; `\includegraphics` :385).

### fig_ciclo_fechado_proposto
1. Compilação: PASS. 2. Overlays: PASS. 3. Setas cruzando: PASS. 4. Texto estourando: **FALHA (MAIOR)** — truncamento das caixas superiores. 5. Símbolos: PASS. 6. P&B: PASS. 7. Caption/ref: PASS (`fig:ciclo` :471; `\includegraphics` :466). Obs: 2 MENOR (espaço pós-`\\`, estilo).

## Aprovação
- [x] 0 CRÍTICOS (nenhuma figura falha na compilação)
- [ ] 0 MAIORES de overlay/cruzamento — overlay NÃO é o problema; o problema são **MAIORES de truncamento de texto em borda** (3 figuras: arquitetura, pipeline, ciclo). Pendente correção do chris.
- [ ] Re-validar após correção do chris (recompilar + vision) e marcar aval verde.

## Contagem final de issues por severidade
- CRÍTICO: 0
- MAIOR: 4  (fig_arquitetura_sistema: 1; fig_pipeline_classificacao: 2; fig_ciclo_fechado_proposto: 1)
- MENOR: 3  (fig_ciclo_fechado_proposto: 1 espaço pós-\\; fig_pipeline_classificacao: 1 Underfull ×2; fig_mapeamento_artigo_sistema: 1 Underfull)

Total de issues: 7 (todas com responsável chris para correção no .tex).
