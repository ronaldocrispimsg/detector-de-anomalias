# Análise de Projeto Orientado ao Objetivo (APOO)
## Sistema NOC Lite × Artigo Norteador: Detecção e Mitigação de Anomalias em SDN com LLMs Open-Source

**Autor da análise:** Dan — Arquiteto de Software
**Data:** 13/07/2026
**Escopo:** Análise arquitetural do sistema implementado em `~/Projetos/rodrigo` (`NOC Lite`), correlacionado ao artigo `docs/goal.pdf` (Edital nº 26/2026 — João Pedro Santos Rodrigues).
**Repositório analisado:** Backend (FastAPI) + Frontend (HTML/JS estático) + SQLite.

---

## 1. Visão Geral da Arquitetura Atual

O sistema **NOC Lite** é um monitoramento de disponibilidade e performance de *hosts* genéricos (endereços IP/DNS), estruturado como um monolito modular em FastAPI com persistência em SQLite e um front-end estático. A proposta norteadora (artigo) descreve um sistema autônomo baseado em **LLMs open-source com fine-tuning PEFT (LoRA/QLoRA)** para **detecção e mitigação** de anomalias de *performance* em **SDN**, em **ciclo fechado** (coleta → classificação → reconfiguração via controlador SDN).

A distância entre os dois universos é estrutural. A arquitetura abaixo é descrita nos três níveis C4.

### 1.1 C4 — Nível de Contexto

**Atores e sistemas externos:**
- **Operador NOC** (usuário autenticado): interage com o front-end via navegador.
- **Front-end (NOC Lite)**: páginas estáticas servidas por `http.server` na porta 3000 (`run.py:22-25`).
- **Backend (API FastAPI)**: serviço `uvicorn` na porta 8000 (`run.py:16-21`), orquestrado pelo `lifespan` em `Backend/main.py:17-24`.
- **Hosts monitorados**: dispositivos IPv4/IPv6 genéricos, alvos de sondas ICMP/TCP/HTTP/DNS e (opcionalmente) SNMP (`Backend/models.py:7-68`).
- **Telegram Bot API**: canal de notificação de alertas/incidentes (`Backend/notifications.py:267-288`).
- **Google Gemini API** (`gemini-1.5-flash`): modelo de linguagem fechado usado como "pipeline de IA generativa" (`Backend/anomaly_classifier.py:338`).
- **SQLite** (`noclite.db`): persistência relacional (`Backend/database.py:13`).

> Divergência de contexto: o artigo posiciona como atores centrais um **controlador SDN** (ex.: Ryu/OpenDaylight), **Mininet/Open vSwitch** e um **módulo de mitigação** que reconfigura a topologia. Nenhum desses elementos existe no contexto do NOC Lite.

### 1.2 C4 — Nível de Contêiner

| Contêiner | Tecnologia | Responsabilidade | Evidência |
|---|---|---|---|
| Front-end | HTML5/JS + `http.server` | UI de login, dashboard, incidentes, anomalias; consome a API | `Frontend/*.html`, `Frontend/*.js` |
| API Backend | FastAPI + Uvicorn | Rotas de hosts, anomalias, autenticação JWT | `Backend/main.py`, `Backend/routes/*` |
| Motor de Monitoramento | asyncio + loop agendado | Varredura periódica de hosts, cálculo de métricas, abertura de incidentes | `Backend/monitor_engine.py`, `Backend/scheduler.py` |
| Classificador de Anomalias | Módulo em memória | Heurística / Árvore de Decisão / Gemini (on-demand) | `Backend/anomaly_classifier.py` |
| Simulador | Módulo em memória | Geração de métricas e histórico sintéticos | `Backend/anomaly_simulator.py` |
| Notificador | Cliente HTTP | Envio de mensagens Telegram com anti-spam | `Backend/notifications.py` |
| Banco de Dados | SQLite | Hosts, checks, alertas, incidentes, SNMP, usuários | `Backend/database.py`, `Backend/models.py` |

**Fluxo de dados (ciclo de monitoramento):**
1. `MonitorEngine._run_loop` dispara `monitor_cycle` a cada `NOC_MONITOR_INTERVAL_SECONDS` (padrão 20s — `Backend/scheduler.py:65`).
2. `get_active_host_ids` (`scheduler.py:758`) lista hosts ativos; cada host é processado em paralelo via `asyncio.Semaphore` (concorrência padrão 20 — `monitor_engine.py:26-29`).
3. `process_host_check` → `_host_check_blocking` (`scheduler.py:241-755`): resolve DNS, executa `ping_host`/`tcp_check`/`http_check` (`checker.py`), coleta SNMP (`snmp_engine.py:378`), calcula SLA/jitter/tendência/health-score (`metrics.py`) e severidade (`refine_severity`, `metrics.py:245`).
4. Com base em falhas consecutivas, abre/fecha **Incidentes** e dispara **Alertas** Telegram (`scheduler.py:509-748`).
5. O classificador de anomalias (heurístico/ML/Gemini) **não participa deste ciclo** — é acionado apenas sob demanda via `GET /api/anomalies/classify` (`Backend/routes/anomalies.py:127-191`), orquestrado pelo front-end `anomalies.js:182`.

### 1.3 C4 — Nível de Componente (Backend)

```
MonitorEngine (monitor_engine.py)
   └─> Scheduler.process_host_check (scheduler.py)
         ├─> Checker (checker.py): ping / tcp / http / dns
         ├─> SnmpEngine.update_host_snmp (snmp_engine.py)
         ├─> Metrics (metrics.py): SLA, Jitter, Tendência, Health, Severity
         ├─> Utils (utils.py): open/close Incident, streaks
         └─> Notifications.send_telegram_alert (notifications.py)

AnomalyClassifier (anomaly_classifier.py)  [FORA do loop]
   ├─> classify_heuristic()   (baseline 1, regras estáticas)
   ├─> classify_ml()          (baseline 2, DecisionTree sklearn)
   └─> classify_generative_ai() (Gemini 1.5 Flash, closed)

AnomalySimulator (anomaly_simulator.py)
   └─> injeta métricas sintéticas no banco (run_simulated_check_cycle)

Database (database.py / models.py / SQLite)
```

**Padrões arquiteturais identificados:**
- **Monolito modular em camadas** (rotas → serviço → modelo → DB).
- **Strategy** para classificadores, com *fallback* em cascata para a heurística (`anomaly_classifier.py:267, 322, 381, 386`).
- **Scheduler orientado a evento/loop** com semáforo de concorrência (`monitor_engine.py:29`).
- **Snapshot tokenizado** para entrada de LLM (`tokenise_metrics`, `anomaly_classifier.py:110-128`) — este ponto, especificamente, está alinhado com o artigo.
- **Cadeia de alerta observadora** (severidade → incidente → Telegram).

---

## 2. Comportamento dos Subsistemas

### 2.1 Motor de Monitoramento
O `MonitorEngine` (`monitor_engine.py:17-143`) encapsula o laço assíncrono. O método `_run_loop` (`monitor_engine.py:64-92`) respeita o intervalo configurável e executa rotina de limpeza (`cleanup_old_data`) a cada `NOC_CLEANUP_INTERVAL_SECONDS` (padrão 3600s — `scheduler.py:66`). Cada host é checado por `check_host` (`monitor_engine.py:124-131`) sob controle de semáforo, invocando `process_host_check` em thread bloqueante (`asyncio.to_thread`, `monitor_engine.py:127`).

O bloco `_host_check_blocking` (`scheduler.py:241-755`) é o coração operacional: resolve DNS (com cache, `checker.py:28`), executa as sondas, recalcula métricas derivadas (`scheduler.py:594-625`), aplica lógica preventiva (`apply_preventive_logic`, `metrics.py:436`) e gerencia incidentes com *streaks* de falha (`scheduler.py:652-702`).

### 2.2 Classificadores
O módulo `anomaly_classifier.py` expõe três estratégias sobre um conjunto fechado de classes (`CLASSES`, `anomaly_classifier.py:13-20`):

1. **Heurístico (baseline 1)** — `classify_heuristic` (`anomaly_classifier.py:133-182`): regras de limiar estático. Ex.: `network_in_bps > 50_000_000` **e** `cpu_usage > 75` → `DDOS_ATTACK` (linha 146-151); `ping_latency > 120ms` → `NETWORK_CONGESTION` (linha 170). Produz `confidence` fixa e `explanation` textual.
2. **Machine Learning (baseline 2)** — `classify_ml` (`anomaly_classifier.py:256-308`): `DecisionTreeClassifier(max_depth=5)` do scikit-learn (`anomaly_classifier.py:244`), treinado **exclusivamente com dados sintéticos** (`train_decision_tree_baseline` consome `generate_simulated_metrics` — `anomaly_classifier.py:217-225`). Sem PEFT, sem LLM. Fallback para heurística em caso de erro (linha 308).
3. **IA Generativa (Gemini)** — `classify_generative_ai` (`anomaly_classifier.py:313-387`): monta prompt estruturado com o snapshot tokenizado (`tokenise_metrics`) e envia ao **`gemini-1.5-flash`** (linha 338), modelo **fechado** da Google. Retorna JSON com `classification`, `confidence` e `explanation`. Possui *fallback* para heurística quando a API key está ausente (linha 322), a biblioteca não está instalada (linha 330) ou ocorre erro (linha 386).

**Ponto crítico de arquitetura:** os três classificadores são consumidos **apenas** pelo endpoint `/api/anomalies/classify` (`anomalies.py:127`), nunca pelo `MonitorEngine`. Ou seja, a "detecção por IA" do artigo **não está integrada ao pipeline de detecção do sistema** — é uma ferramenta de diagnóstico sob demanda no front-end (`Frontend/anomalies.js:182-237`).

### 2.3 Simulador
`anomaly_simulator.py` gera cenários anômalos sintéticos: `generate_simulated_metrics` (`anomaly_simulator.py:63-182`) produz vetores por tipo (`DDOS_ATTACK`, `PORT_SCAN`, `HOST_DOWN`, `DATA_EXFILTRATION`, `NETWORK_CONGESTION`, `NORMAL`) via `random.uniform`. `run_simulated_check_cycle` (`anomaly_simulator.py:184-333`) injeta esses dados diretamente no banco, e `generate_historical_data` (`anomaly_simulator.py:335-425`) popular histórico retroativo. O agendamento em tempo real usa `ACTIVE_SIMULATIONS` em memória (`anomaly_simulator.py:25`).

### 2.4 Notificação
`notifications.py` constrói mensagens formatadas (`build_*_message`) e envia via `send_telegram_alert` (`notifications.py:267`) usando `requests.post` para a API do Telegram. Há deduplicação anti-spam por *fingerprint* SHA-1 (`_is_suppressed_by_antispam`, `notifications.py:245-265`). Os gatilhos ocorrem no `scheduler.py` (falha confirmada, recuperação, health crítico, preventivo, DNS).

---

## 3. Mapeamento Artigo × Sistema

| # | Objetivo / Componente do Artigo | O que o NOC Lite entrega | Status de Alinhamento |
|---|---|---|---|
| 1 | LLM **open-source** (Llama/Falcon) com fine-tuning | Usa **Gemini 1.5 Flash** (fechado); Árvore de Decisão como ML | ❌ Divergente |
| 2 | **Fine-tuning PEFT (LoRA/QLoRA)** | Inexistente; ML é DecisionTree treinada de zero em dados sintéticos | ❌ Ausente |
| 3 | Ambiente **SDN virtualizado** (Mininet/Open vSwitch) | Hosts IP genéricos; sondas ICMP/TCP/HTTP/DNS/SNMP | ❌ Ausente |
| 4 | **Mitigação** via reconfiguração de VNT/roteamento (ciclo fechado) | Apenas detecção + alerta Telegram; nenhum módulo de ação corretiva | ❌ Ausente |
| 5 | Detecção de **anomalias de performance** (congestionamento, falha de enlace, degradação espectral) | Mistura anomalias de **segurança/operacionais** (DDoS, port scan, exfiltração, host down) com congestionamento genérico | ⚠️ Parcial |
| 6 | **Datasets públicos** (UNSW-NB15, CSE-CIC-IDS2018, Synthetic SDN) | **Dados 100% sintéticos** (`random.uniform`) e histórico simulado | ❌ Divergente |
| 7 | **Baselines** de comparação (heurística / ML tradicional) | Heurística (`classify_heuristic`) + DecisionTree (`classify_ml`) | ✅ Convergente |
| 8 | **Tokenização** de métricas em representação textual estruturada | `tokenise_metrics` (`anomaly_classifier.py:110`) | ✅ Convergente |
| 9 | **Justificativa textual** (interpretabilidade / XAI) | `explanation` retornado por heurística, ML e Gemini | ✅ Convergente (com modelo fechado) |
| 10 | **Avaliação de tempo de resposta** por classificador | `latency_ms` medido por classificador em `/api/anomalies/classify` (`anomalies.py:149-161`) | ✅ Convergente |
| 11 | Métricas resumidas (throughput, latência, jitter, perda) | SLA/jitter/tendência/health-score (`metrics.py`) + SNMP (CPU/RAM/rede) | ✅ Convergente (escopo host) |
| 12 | **Ciclo fechado** coleta→classificação→mitigação | Loop aberto: coleta→severidade→alerta; classificação fora do loop | ❌ Aberto |

---

## 4. Gaps / Desalinhamentos (com evidência de código)

### GAP-1 — SDN vs. Hosts Genéricos  ·  **Severidade: CRÍTICO**
O artigo fundamenta toda a proposta no paradigma SDN (plano de controle desacoplado, controlador programável, Mininet, Open vSwitch, reconfiguração de VNT). O NOC Lite monitora **hosts IP/DNS arbitrários** (`Backend/models.py:7-13`, `Host.address`). Busca por `sdn|mininet|openvswitch|vnt|controller` no backend retorna **zero ocorrências**. Não há controlador, topologia virtualizada, nem plano de dados/contrôle separados.

### GAP-2 — Gemini Fechado vs. LLM Open-Source  ·  **Severidade: CRÍTICO**
O artigo define explicitamente (goal.pdf, Referencial Teórico): *"Closed-source LLMs, often referred to as commercial LLMs such as ChatGPT, **Gemini** and Claude"*. O objetivo geral exige **LLMs open-source (Llama/Falcon)**. O sistema, porém, usa `model = genai.GenerativeModel("gemini-1.5-flash")` (`Backend/anomaly_classifier.py:338`). Além de fechado, depende de infraestrutura paga de terceiro (`GEMINI_API_KEY`, `anomaly_classifier.py:318`), contrariando a viabilidade "open-source / sem licenças" do artigo.

### GAP-3 — Ausência de Fine-Tuning LoRA/QLoRA  ·  **Severidade: CRÍTICO**
O artigo dedica toda a seção de PEFT (LoRA/QLoRA) e a Etapa 8 do cronograma ("RAG com LoRA/QLoRA"). Busca por `lora|qlora|peft|fine.?tun` no backend retorna **zero ocorrências**. O único modelo treinável é uma `DecisionTreeClassifier` (`anomaly_classifier.py:244`) treinada do zero — sem fine-tuning, sem adaptação de pesos pré-treinados, sem redução de rank.

### GAP-4 — Ausência de Mitigação / Loop Aberto  ·  **Severidade: CRÍTICO**
O objetivo geral exige "mitigar via reconfiguração proativa de VNT e roteamento" em ciclo fechado. No NOC Lite, a única ação pós-detecção é **notificar** (Telegram) e **registrar incidente**. Não existe módulo de decisão/mitigação. Adicionalmente, a classificação por IA **não está no loop**: `scheduler.py` não referencia nenhum `classify_*` (`search_files` em `scheduler.py` para `classify_heuristic|classify_ml|classify_generative_ai` → 0 matches). A inferência ocorre só em `/api/anomalies/classify` (`anomalies.py:127`), acionado manualmente pelo operador. O ciclo é, portanto, **aberto** (observar→alertar), sem atuação autônoma.

### GAP-5 — Dados Sintéticos vs. Datasets Públicos  ·  **Severidade: MAIOR**
O artigo exige validação com UNSW-NB15, CSE-CIC-IDS2018 e Synthetic SDN (Tabela 1). O NOC Lite gera 100% de seus dados com `random.uniform` (`anomaly_simulator.py:79-165`) e treina a árvore de decisão com esse sintético (`anomaly_classifier.py:217-225`). Busca por `unsw|cic-ids|mendeley` → 0 ocorrências. Isso inviabiliza a "comparação com trabalhos relacionados" e a avaliação de generalização pretendida pelo artigo.

### GAP-6 — Anomalias de Performance vs. Segurança/Operacionais  ·  **Severidade: MAIOR**
O artigo foca em **performance** (congestionamento transiente, falhas de enlace, degradação espectral). O NOC Lite define classes majoritariamente de **segurança/operacionais** (`anomaly_classifier.py:13-20`): `DDOS_ATTACK`, `PORT_SCAN`, `DATA_EXFILTRATION`, `HOST_DOWN`, mais `NETWORK_CONGESTION`. A detecção de "congestionamento" é por limiar genérico de latência de ping (`ping_latency > 120.0`, linha 170), sem noção de enlace SDN, throughput de fluxo ou espectro óptico. Além disso, o monitor primário produz severidade por *health-score* de disponibilidade (`metrics.py:4-62`), não por classificação de fenômeno anômalo de performance.

### GAP-7 — Interpretabilidade com Modelo Fechado  ·  **Severidade: MENOR (mas conceitualmente relevante)**
O artigo vincula interpretabilidade/XAI à transparência de LLMs open-source (HuntGPT etc.). O NOC Lite entrega `explanation` textual (`anomaly_classifier.py:354`), mas ela provém do Gemini fechado, sem rastreabilidade de pesos nem reprodutibilidade local — o que fragiliza a promessa de XAI do artigo.

---

## 5. Pontos de Convergência

Apesar dos desalinhamentos estruturais, o NOC Lite apresenta pontos onde a intenção do artigo é parcialmente honrada:

1. **Baselines de comparação (Obj. Específico 5).** O artigo exige "métodos de classificação de referência (baselines), como regras heurísticas ou modelos tradicionais de aprendizado de máquina". O sistema implementa exatamente os dois: `classify_heuristic` (`anomaly_classifier.py:133`) e `classify_ml` (DecisionTree, `anomaly_classifier.py:256`). O endpoint `/api/anomalies/classify` retorna os três classificadores lado a lado (`anomalies.py:163-190`), permitindo comparação direta.

2. **Tokenização de métricas (Obj. Específico 2 — "propriedades de aprendizado e organização de tokens").** `tokenise_metrics` (`anomaly_classifier.py:110-128`) converte o vetor numérico em "representação semiestruturada" (ex.: `PingSuccessRate: 0.95 | AvgPingLatency: 12.3 ms | CPUUsage: 34.1%`), espelhando a recomendação do artigo (Etapa 3/4): *"conversão de atributos numéricos em representações textuais estruturadas"*. O comentário da própria função cita "Identifica as propriedades de aprendizado e organiza em tokens" (linha 111-113).

3. **Justificativa textual / Interpretabilidade (Obj. Específico 7).** Todos os classificadores retornam `explanation` (`anomaly_classifier.py:142, 166, 174, 304, 377`). O Gemini devolve justificativa em linguagem natural (`anomaly_classifier.py:354`), alinhado ao objetivo qualitativo de "interpretabilidade das decisões".

4. **Métricas de tempo de resposta por classificador (Obj. Específico 6 — "tempo de resposta").** O endpoint mede `latency_ms` de cada classificador com `time.perf_counter()` (`anomalies.py:149-161`), entregando a métrica de desempenho exigida pelo artigo (acurácia/consistência/tempo).

5. **Métricas resumidas de rede.** SLA rolling, jitter, tendência de latência e health-score (`metrics.py`) capturam latência/perda/jitter — conceitos coincidentes com as métricas de performance do artigo (throughput, latência, jitter, perda), ainda que no escopo de host e não de fluxo SDN.

---

## 6. Sugestões de Arquitetura para Alinhamento

As sugestões abaixo visa reduzir a distância entre o NOC Lite e o artigo, respeitando viabilidade incremental. Não alteram código existente; propõem evolução.

### 6.1 Substituição do modelo fechado por LLM open-source (fecha GAP-2, GAP-3)
- Introduzir um contêiner de inferência local (ex.: `vLLM`/`llama.cpp`/`text-generation-webui`) servindo **Llama 3 (7–13B)** ou **Falcon**, via endpoint OpenAI-compatible.
- Substituir `genai.GenerativeModel("gemini-1.5-flash")` (`anomaly_classifier.py:338`) por cliente HTTP para o modelo local. Manter o *fallback* heurístico.
- Aplicar **LoRA/QLoRA** (ex.: biblioteca `peft` + `transformers`) sobre o modelo base, usando os mesmos *prompts* estruturados de `tokenise_metrics`. Isso atende à Etapa 8 do cronograma e elimina dependência de API paga.

### 6.2 Pipeline de dados com datasets públicos (fecha GAP-5)
- Criar um módulo `data_ingest` que baixa/normaliza UNSW-NB15, CSE-CIC-IDS2018 e Synthetic SDN para o schema de features de `extract_features_from_db` (`anomaly_classifier.py:29`).
- Reutilizar `tokenise_metrics` para converter flows em texto. Treinar LoRA e a Árvore de Decisão com esses dados reais, preservando o `anomaly_simulator` apenas para demonstração/rotina.

### 6.3 Ambiente SDN e fechamento do ciclo (fecha GAP-1, GAP-4)
- Adicionar um contêiner **Mininet + controlador (Ryu)** que emule a topologia e exponha métricas de enlace/flow (throughput, perda, jitter por fluxo).
- Generalizar `Host`/`CheckResult` para também aceitar telemetria de fluxo SDN (não apenas ICMP/TCP/HTTP).
- Criar um **módulo de mitigação** (`mitigation_engine`) que mapeia `classification` → ação corretiva (re-rota, qos, drop de fluxo) executada via NorthBound API do controlador.
- Integrar o classificador **dentro** do `MonitorEngine`/`scheduler` (hoje desacoplado — GAP-4), de modo que a saída da classificação alimente diretamente o `mitigation_engine`, fechando o ciclo coleta→classificação→mitigação.

### 6.4 Realinhamento do catálogo de anomalias (fecha GAP-6)
- Separar claramente duas famílias: (a) **performance SDN** (congestionamento de enlace, falha de enlace, degradação de throughput/jitter por fluxo) e (b) **segurança/operacional** (DDoS, port scan, exfiltração, host down). O artigo foca em (a); o NOC Lite hoje privilegia (b). Recomenda-se priorizar (a) para aderência ao objetivo geral, mantendo (b) como extensão.

### 6.5 Preservação dos pontos fortes
- Manter `tokenise_metrics`, o par `baseline heurístico + ML`, a medição de `latency_ms` e o formato de `explanation` — estes já cumprem objetivos específicos do artigo e devem ser a base do novo pipeline.

### 6.6 Roadmap de alinhamento sugerido (espelhando o cronograma do artigo)
1. Container de LLM open-source local + `tokenise_metrics` (já existe) → zero-shot.
2. Ingestão dos 3 datasets públicos + treino LoRA/QLoRA.
3. Mininet + controlador + telemetria de fluxo.
4. `mitigation_engine` + integração da classificação no `MonitorEngine`.
5. Fechamento do ciclo e avaliação comparativa (heurística vs. ML vs. LLM open-source com/sem LoRA), reutilizando `latency_ms` e acrescentando acurácia/consistência.

---

## Anexo — Índice de Evidências (arquivo:linha)

| Evidência | Arquivo:Linha |
|---|---|
| Modelo Gemini fechado | `Backend/anomaly_classifier.py:338` |
| API key Gemini (dependência externa) | `Backend/anomaly_classifier.py:318` |
| Fallback heurístico do Gemini | `Backend/anomaly_classifier.py:322, 330, 381, 386` |
| Classes de anomalia (segurança/operacionais + congestionamento) | `Backend/anomaly_classifier.py:13-20` |
| Heurística de limiares | `Backend/anomaly_classifier.py:146-175` |
| Árvore de Decisão sklearn (sem PEFT) | `Backend/anomaly_classifier.py:244` |
| Treino ML com dados sintéticos | `Backend/anomaly_classifier.py:217-225` |
| Tokenização de métricas | `Backend/anomaly_classifier.py:110-128` |
| Classificação fora do loop (só on-demand) | `Backend/routes/anomalies.py:127` |
| Medição de latência por classificador | `Backend/routes/anomalies.py:149-161` |
| Loop de monitoramento (sem classificador) | `Backend/monitor_engine.py:64-92`; `Backend/scheduler.py:241-755` |
| Intervalo de monitoramento | `Backend/scheduler.py:65` |
| Hosts genéricos (sem SDN) | `Backend/models.py:7-13` |
| Dados sintéticos do simulador | `Backend/anomaly_simulator.py:79-165` |
| Notificação Telegram (sem mitigação) | `Backend/notifications.py:267-288` |
| Cálculo de métricas derivadas (SLA/jitter/tendência) | `Backend/metrics.py:64-433` |
| Severidade por health-score | `Backend/metrics.py:4-62` |
| Ausência de SDN/LoRA/datasets (busca) | `grep` em `Backend/**/*.py` → 0 matches |

**Conclusão da APOO:** O NOC Lite é um sistema de monitoramento de disponibilidade/hosts bem estruturado e funcional, com baselines e tokenização coerentes com a *intenção* do artigo. Contudo, nos eixos centrais da proposta — **LLM open-source + LoRA/QLoRA**, **ambiente SDN**, **mitigação em ciclo fechado** e **datasets públicos** — há desalinhamentos de **severidade CRÍTICA** (GAP-1 a GAP-4). O alinhamento exige evolução arquitetural substantiva, não apenas ajustes pontuais.
