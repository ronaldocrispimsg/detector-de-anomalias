# Notas da Análise do Subsistema de Classificação de Anomalias (NOC Lite)

---

## 0. Visão Geral Arquitetural

O sistema implementa **três classificadores paralelos** para o mesmo vetor de features,
definidos em `Backend/anomaly_classifier.py`:

1. **Heurístico** (`classify_heuristic`, linha 133) — regras de threshold estáticas. Baselines de
   referência 1.
2. **Machine Learning** (`classify_ml`, linha 256) — `DecisionTreeClassifier` do scikit-learn,
   treinado com dados **sintéticos** gerados pelo simulador. Baselines 2.
3. **IA Generativa** (`classify_generative_ai`, linha 313) — Google Gemini (`gemini-1.5-flash`),
   recebe um snapshot de telemetria tokenizado e responde em JSON.

As seis classes possíveis estão em `CLASSES` (`anomaly_classifier.py:13-20`):
`NORMAL`, `DDOS_ATTACK`, `PORT_SCAN`, `HOST_DOWN`, `DATA_EXFILTRATION`, `NETWORK_CONGESTION`.

O endpoint `GET /api/anomalies/classify` (`routes/anomalies.py:127-191`) executa os três em
sequência e devolve a comparação lado a lado, incluindo latência de cada classificador
em ms. O endpoint `POST /api/anomalies/train` (`routes/anomalies.py:193-204`) dispara o treino
da árvore de decisão.

---

## 1. Como cada classificador decide

### 1.1 Classificador Heurístico (thresholds exatos)

Função: `classify_heuristic(features)` — `anomaly_classifier.py:133-182`.
Recebe o dicionário de features produzido por `extract_features_from_db` (Seção 2). A ordem
das regras importa (primeira correspondência vence). Os limiares numéricos reais:

| Ordem | Classe | Condição (AND implícito entre cláusulas) | Confidence | Linha |
|-------|--------|-------------------------------------------|-----------|-------|
| 1 | `HOST_DOWN` | `ping_success_rate == 0.0` **E** `tcp_success_rate == 0.0` | 1.0 | 138-143 |
| 2 | `DDOS_ATTACK` | `network_in_bps > 50_000_000.0` (50 Mbps) **E** `cpu_usage > 75.0` | 0.9 | 146-151 |
| 3 | `DATA_EXFILTRATION` | `network_out_bps > 50_000_000.0` (50 Mbps) | 0.85 | 154-159 |
| 4 | `PORT_SCAN` | `num_failed_tcp_ports >= 3` | 0.8 | 162-167 |
| 5 | `NETWORK_CONGESTION` | `ping_latency > 120.0` **OU** (`ping_success_rate < 0.9` **E** `ping_success_rate > 0.0`) | 0.75 | 170-175 |
| 6 | `NORMAL` | fallback (nenhuma das anteriores) | 0.95 | 178-182 |

Observações técnicas relevantes:

- **Ordem importa e pode mascarar classes.** Um `DDOS_ATTACK` que também apresente
  `network_out_bps > 50 Mbps` (upload massivo sob ataque) cairia primeiro no critério de
  `DDOS_ATTACK` (linha 146) antes de `DATA_EXFILTRATION` (linha 154). É um comportamento
  defensável (prioriza a ameaça mais destrutiva), mas não é uma decisão por "votação" — é
  first-match.
- O `HOST_DOWN` exige **ping E tcp** zerados. Se apenas o ping cair mas a porta TCP responder
  (firewall bloqueando ICMP, comum em produção), o host NÃO é classificado como `HOST_DOWN` pela
  heurística — ele cairia em `NETWORK_CONGESTION` pela regra de perda parcial de pacotes.
- `NETWORK_CONGESTION` tem dois gatilhos: latência isolada > 120 ms **ou** perda parcial
  (`success_rate` entre 0 e 0.9). Ou seja, qualquer queda parcial de ICMP já vira congestionamento,
  o que é agressivo demais para redes Wi-Fi/long-haul reais.
- Os limiares de 50 Mbps para in/out são **fixos e universais** — não há baseline por host/link.
  Um enlace de 1 Gbps e um de 100 Mbps usam o mesmo número.

### 1.2 Classificador Machine Learning (Decision Tree + dados sintéticos)

Funções envolvidas:
- `train_decision_tree_baseline()` — `anomaly_classifier.py:205-254`
- `load_ml_model()` — `anomaly_classifier.py:187-203`
- `classify_ml(features)` — `anomaly_classifier.py:256-308`

**Treinamento (linha 205-254):**
- Importa `DecisionTreeClassifier` do sklearn e `numpy` (linha 211-212). Se sklearn não
  estiver instalado, retorna erro e o sistema ignora o ML.
- Gera dataset sintético consumindo `generate_simulated_metrics(scenario)` do simulador
  (`anomaly_simulator.py`), **200 amostras por classe** (`for _ in range(200)`, linha 224),
  totalizando 1.200 amostras (6 classes × 200).
- O vetor de features tem **10 dimensões**, na ordem exata (linha 228-239):

  ```
  [ cpu, ram, network_in_bps, network_out_bps, ping_latency,
    ping_success(1.0/0.0), tcp_success(1.0/0.0), http_success(1.0/0.0),
    http_latency, len(extra_tcp_checks) ]
  ```

- Modelo: `DecisionTreeClassifier(max_depth=5, random_state=42)` (linha 244). `max_depth=5`
  limita a capacidade (pode underfitar relações não-lineares).
- Persistência: `pickle.dump` em `decision_tree_model.pkl` (linha 250, caminho em `MODEL_PATH`,
  linha 23). Carregado em memória via `_ML_MODEL` global (lazy load em `load_ml_model`, linha 187).

**Inferência (linha 256-308):**
- Reconstrói o mesmo vetor de 10 features a partir do dicionário `features` (linha 272-283).
- Se não houver modelo salvo, tenta treinar on-the-fly (linha 263) e, se falhar, cai no
  fallback heurístico (linha 267-269).
- `clf.predict([feat_vector])` → classe; `clf.predict_proba(...)` → confiança
  (linha 286-289). A confiança é a probabilidade da folha (não calibrada).
- Explicação é um texto fixo por classe (dicionário `explanations`, linha 292-299), ou seja,
  **a árvore não explica a regra real usada** — é apenas um rótulo genérico.
- Qualquer exceção na inferência cai no heurístico (linha 306-308).

**Ponto crítico de viés:** o ML é treinado 100% com dados do próprio simulador
(`generate_simulated_metrics`). Como o simulador e o classificador heurístico compartilham os
mesmos limiares (ex.: 50 Mbps, 120 ms), a árvore de decisão aprende essencialmente a "copiar" a
heurística em forma de árvore. Não há exposição a ruído, drift ou dados reais — o modelo terá
alta acurácia no sintético e provável colapso em produção.

### 1.3 Classificador IA Generativa (Gemini + prompt estruturado + parsing JSON + fallback)

Função: `classify_generative_ai(features, tokenized_text)` — `anomaly_classifier.py:313-387`.

**Fluxo:**
1. Lê `GEMINI_API_KEY` do ambiente (linha 318). Se ausente → fallback heurístico com prefixo
   `"[IA Fallback (API Key Ausente)]"` (linha 319-323).
2. Tenta importar `google.generativeai` (linha 326). Se a lib não existir → fallback heurístico
   (linha 328-331).
3. Configura cliente e instancia `gemini-1.5-flash` (linha 335-338).
4. Monta prompt em português (linha 340-359) descrevendo as 6 classes e exigindo resposta
   **estritamente JSON** no formato:
   ```json
   { "classification": "...", "confidence": 0.99, "explanation": "..." }
   ```
5. `model.generate_content(prompt)` (linha 360).
6. **Parsing defensivo do JSON** (linha 362-370): strip de cercas ```json / ``` e espaços.
7. `json.loads` (linha 370). Se `classification` estiver em `CLASSES` (linha 373), devolve o
   resultado; a confiança é `float(data.get("confidence", 0.8))` — **autorreportada pelo modelo**,
   não calibrada.
8. Fallbacks (linha 379-387):
   - Classe inválida retornada → heurística.
   - Qualquer exceção (rede, quota, JSON inválido) → heurística com prefixo
     `"[IA Fallback (Erro API: ...)]"`.

**Limitações constatadas no código:**
- Dependência de **API externa paga** (Gemini) e de rede — introduce latência variável e
  indisponibilidade (mitigada pelo fallback, mas o fallback é o próprio heurístico, então a IA
  só "enfeita" a explicação quando funciona).
- **Sem few-shot, sem RAG, sem tool-use, sem memória.** O modelo recebe apenas o snapshot atual.
- A confiança é declarada pelo LLM, não derivada de probabilidade — não é comparável à do ML.
- Sem validação de schema robusta (apenas checagem de presença da chave `classification`).

---

## 2. Features extraídas do banco e tokenização para o LLM

### 2.1 `extract_features_from_db(host_id, db, window_minutes=5)` — `anomaly_classifier.py:29-108`

Coleta, na janela de `window_minutes` (padrão 5 min, linha 37-38), de duas tabelas:
- `CheckResult` filtrado por `host_id` e `timestamp >= since` (linha 41-44).
- `SNMPMetric` na mesma janela (linha 47-50).

Cálculo das features (médias/somas sobre a janela):

| Feature (chave do dict) | Origem / Cálculo | Linha |
|--------------------------|------------------|-------|
| `ping_success_rate` | acertos de ping / total de pings (default 1.0) | 53-54 |
| `ping_latency` | média das latências de ping com sucesso | 55-56 |
| `tcp_success_rate` | acertos TCP na porta principal (`host.port` ou 80) / total | 58-59 |
| `num_failed_tcp_ports` | **contagem de portas TCP distintas** que falharam e **não** são a porta principal | 62-66 |
| `http_success_rate` | acertos HTTP / total | 68-69 |
| `http_latency` | média das latências HTTP com sucesso | 70-71 |
| `cpu_usage` | média de `cpu` em `SNMPMetric` | 74 |
| `ram_usage` | média de `ram` | 75 |
| `network_in_bps` | média de `network_in_bps` | 76 |
| `network_out_bps` | média de `network_out_bps` | 77 |

**Ajustes de fallbacks** (linha 79-95): se não houver `SNMPMetric` e o host não estiver `DOWN`,
usa os valores "ao vivo" de `host.cpu_usage`, `host.ram_usage`, `host.network_in_bps`, etc.
(linha 80-84). Idem para latências de ping/http (linha 86-89). Se o host está `DOWN` e não há
checks nem SNMP, força `ping/tcp/http_success_rate = 0.0` (linha 92-95) — o que alimenta
diretamente a regra `HOST_DOWN` da heurística.

Retorno: dicionário com as 10 chaves acima (linha 97-108), consumido tanto pela heurística,
quanto pelo ML, quanto pela tokenização.

### 2.2 `tokenise_metrics(features, host_name)` — `anomaly_classifier.py:110-128`

Converte o dicionário num **texto estruturado** para o LLM, no formato pedido
(`[NETWORK_HOST_SNAPSHOT]...`). Cada feature vira um token `Chave: valor`, unidos por ` | `
(linha 128). Template exato:

```
[NETWORK_HOST_SNAPSHOT] Name: {host_name} | PingSuccessRate: {:.2f} |
AvgPingLatency: {:.1f} ms | TCPAvailability: {:.2f} |
HTTPAvailability: {:.2f} | AvgHTTPLatency: {:.1f} ms |
CPUUsage: {:.1f}% | RAMUsage: {:.1f}% |
TrafficInbound: {:/1_000_000.0:.2f} Mbps | TrafficOutbound: {:/1_000_000.0:.2f} Mbps |
FailedScanPorts: {}
```

Detalhes de formatação (linha 115-127):
- `TrafficInbound`/`TrafficOutbound` convertem bps → Mbps dividindo por `1_000_000.0`
  (linha 124-125) — é essa a ponte que faz o LLM "ler" 50 Mbps nos limiares.
- Taxas de sucesso com 2 casas (`.2f`), latências com 1 casa em ms, CPU/RAM com 1 casa em %.
- `FailedScanPorts` é o inteiro `num_failed_tcp_ports` (linha 126).

Esse texto é o `tokenized_text` passado a `classify_generative_ai` (linha 313) e também é
retornado pela API em `tokenized_text` (`routes/anomalies.py:146, 170`) para inspeção.

---

## 3. Como o `anomaly_simulator` gera os 6 cenários e popula o DB

### 3.1 `generate_simulated_metrics(anomaly_type, timestamp=None)` — `anomaly_simulator.py:63-182`

Função pura que devolve um dicionário de métricas "brutas" para um instante. Define primeiro
valores **NORMAL** (linha 77-92) e depois sobrescreve conforme o `anomaly_type`:

**NORMAL (baseline, linha 77-92):**
- ping/tcp/http success = True; ping 3–10 ms, tcp 4–12 ms, http 10–25 ms; cpu 5–25%, ram 30–45%,
  disk 50–55%; net_in 0,5–2 Mbps; net_out 0,2–1 Mbps.

**DDOS_ATTACK (linha 94-104):**
- cpu 85–99%, ram 65–80%; **net_in 80–120 Mbps**; net_out 1,5–4 Mbps; latências sob carga
  (ping 15–45, tcp 30–80, http 80–250 ms).

**PORT_SCAN (linha 106-123):**
- cpu 15–30%; net_in 0,1–0,5 Mbps; net_out 0,05–0,25 Mbps; ping 4–12 ms; **tcp_success = False**,
  tcp_latency = None; `extra_tcp_checks` = 5 portas [21, 22, 23, 25, 443] todas com
  `success=False`, `error="Connection refused"` (linha 117-123).

**HOST_DOWN (linha 125-139):**
- Tudo cai: ping/tcp/http success = False, latências = None, status HTTP = None; cpu/ram/disk/
  net_in/net_out = **None** (telemetria SNMP indisponível).

**DATA_EXFILTRATION (linha 141-149):**
- cpu 15–35%; **net_out 85–115 Mbps**; net_in 0,5–1,5 Mbps; latências normais-baixas
  (ping 5–15, tcp 8–20, http 20–45 ms) — ou seja, CPU normal + upload massivo.

**NETWORK_CONGESTION (linha 151-165):**
- **75% de chance de sucesso** em ping/tcp/http (`random.random() > 0.25`, linha 153/156/159),
  latências altas quando há sucesso (ping 150–350, tcp 200–450, http 300–650 ms); cpu 10–20%;
  net_in 25–40 Mbps; net_out 10–20 Mbps (link saturando, mas abaixo do limiar de DDoS).

> Conexão com a heurística: os geradores foram calibrados para **bater** nos thresholds da
> Seção 1.1. Ex.: PORT_SCAN gera exatamente 5 portas falhas → `num_failed_tcp_ports=5 >= 3`
> (linha 162). NETWORK_CONGESTION gera success_rate ~0.75 (< 0.9) → dispara a regra de perda
> parcial (linha 170). DDOS gera net_in 80–120 Mbps (> 50) + cpu 85–99 (> 75) → linha 146.
> DATA_EXFILTRATION gera net_out 85–115 Mbps (> 50) → linha 154.

### 3.2 `run_simulated_check_cycle(host_id, anomaly_type, db)` — `anomaly_simulator.py:184-333`

Executa **um ciclo completo** de monitoramento injetando o snapshot coerente no banco e
recalculando toda a telemetria clássica do NOC Lite:

1. Busca o host (linha 189); se não existir, retorna.
2. `m = generate_simulated_metrics(anomaly_type)` (linha 193).
3. Atualiza `host.last_check`, IP fictício `192.168.100.99` se vazio (linha 197-199).
4. Insere `CheckResult` de **ping** (linha 202-210), **tcp** na porta principal (linha 213-222),
   **tcp extras** de varredura (linha 225-235) e **http** se `host.http_enabled` (linha 238-248).
5. Atualiza campos do host: `latency_ping/tcp`, `http_latency`, e — se `cpu is not None`
   (ou seja, exceto HOST_DOWN) — `cpu_usage/ram_usage/disk_usage/network_in_bps/network_out_bps`
   e insere `SNMPMetric` (linha 259-277). Para HOST_DOWN, zera os campos SNMP do host (linha 280-284).
6. **Recálculo da telemetria NOC Lite** via `metrics.py` (linha 287-304):
   SLA rolling (ping/tcp/http), jitter (ping/tcp/http), tendência de latência (slope/trend).
7. `compute_health(...)` → `health_score` e `severity` (linha 311-313).
8. Define `host.status` em UP / DEGRADED / DOWN pela combinação de sucesso de ping/tcp/http
   (linha 316-327): DOWN se ping e tcp falharem (e http, se houver); DEGRADED se algum falhar;
   UP caso contrário. Atualiza `fail_streak`/`success_streak`.
9. `db.commit()` (linha 332).

> Este ciclo é o que o scheduler intercepta em produção: em `_host_check_blocking`
> (`scheduler.py:253-258`), se houver simulação ativa (`get_active_simulation`), ele chama
> `run_simulated_check_cycle` **em vez de** executar os checks reais (ping/tcp/http/snmp). Ou seja,
> o simulador "engana" o pipeline inteiro de monitoramento de forma transparente.

### 3.3 `generate_historical_data(host_id, anomaly_type, records=150)` — `anomaly_simulator.py:335-425`

Gera histórico **retroativo** para treino/visualização:

1. Abre `SessionLocal()` própria (linha 340).
2. `base_time = utcnow()`; para `i` de `records` até 1 (linha 351), calcula
   `time_offset = base_time - timedelta(seconds=i*20)` — ou seja, **um registro a cada 20 s**
   no passado (linha 352).
3. Para cada offset: `generate_simulated_metrics(anomaly_type, timestamp=time_offset)` e insere
   `CheckResult` (ping/tcp/extras/http) + `SNMPMetric` (linha 357-415).
4. Ao final, `db.commit()` (linha 418) e executa **um** `run_simulated_check_cycle` para deixar o
   estado atual do host coerente com o cenário (linha 419).
5. Rollback em caso de erro (linha 421-423); `db.close()` no `finally` (linha 425).

> Invocado via API em `POST /api/anomalies/simulator/generate-history`
> (`routes/anomalies.py:94-125`) numa thread em background (linha 117-120), para não bloquear o
> HTTP. `records` padrão = 150 → ~50 min de histórico a 20 s/amostra.

---

## 4. Sugestões pontuais para aproximar o sistema do artigo

> Importante: as sugestões abaixo são **textuais/arquiteturais**. Não foram aplicadas ao código
> (conforme restrição da tarefa). Cada item aponta o gap atual e a direção concreta.

### 4.1 Trocar Gemini por LLM open-source local (Ollama + Llama/Mistral)

**Gap atual:** `classify_generative_ai` (`anomaly_classifier.py:313-387`) é hardcoded para
`google.generativeai` + `gemini-1.5-flash`. Custa API externa, exige rede e vaza telemetria de
rede para terceiros.

**Sugestão específica:**
- Introduzir uma **interface de LLM abstrata** (`LLMBackend` com `generate(prompt)->dict`) e duas
  implementações: `GeminiBackend` (atual) e `OllamaBackend`. O Ollama expõe API
  OpenAI-compatível em `http://localhost:11434/v1`, bastando `base_url` + `api_key="ollama"`.
- Modelo recomendado para inferência local em hardware modesto: `llama3.1:8b-instruct-q4_K_M`
  ou `mistral:7b-instruct-q4`. Para latência de "edge", `phi3:mini` ou `gemma2:2b`.
- Manter o mesmo prompt estruturado (linha 340-359) e o mesmo parser JSON defensivo
  (linha 362-370). O prompt já instrui "responda EXATAMENTE o JSON" — funciona com modelos
  instrucionáveis locais, mas recomenda-se adicionar `response_format={"type":"json_object"}`
  quando suportado.
- Benefício duplo: zero custo de API, telemetria permanece on-premise (adesão a artigos que
  enfatizam privacidade/edge), e viabiliza rodar o classificador em downstream do pipeline
  SNMP real sem dependência de nuvem.

### 4.2 Fine-tuning LoRA / QLoRA do LLM (ou adaptador tabular)

**Gap atual:** o LLM nunca é especializado; o ML é uma `DecisionTree` de profundidade 5 treinada
em dados 100% sintéticos (Seção 1.2) — ou seja, o componente "IA" não aprende nada de real.

**Sugestão específica (LLM):**
- Usar PEFT/QLoRA para aplicar LoRA (rank ~16–32, alpha ~32, dropout ~0.05) sobre um base
  local (ex.: `llama-3.1-8b` ou `mistral-7b`) em um dataset de pares
  `(snapshot_tokenizado, {classification,confidence,explanation})`.
- O `tokenise_metrics` (Seção 2.2) já produz o texto de entrada ideal para fine-tuning —
  basta empacotar cada exemplo como mensagem de sistema (o prompt de linha 340) + mensagem de
  usuário (o snapshot) → completion = JSON.
- Congelar a base e treinar só os adapters (QLoRA em 4-bit) reduz VRAM a ~6–8 GB, viável em
  GPU de workstation ou até em CPU com quantização.

**Sugestão alternativa (tabular):** substituir a `DecisionTree` por um modelo mais expressivo
(MLP ou `HistGradientBoostingClassifier` do sklearn, ou um pequeno transformer tabular tipo
`FT-Transformer`) e fazer fine-tuning incremental com dados reais rotulados — mantendo o
`pickle` (linha 250) mas trocando o estimator e o `max_depth`.

### 4.3 Módulo de mitigação / reconfiguração automática (o elo ausente)

**Gap atual:** o sistema **só detecta e alerta**. A ação humana/automática é limitada a
notificações Telegram (`scheduler.py` importa `send_telegram_alert`, linha 29-37) e abertura de
`Incident` (linha 319-339). Não há execução de contramedida.

**Sugestão específica — criar um `mitigation_engine`:**
- Ao confirmar `DDOS_ATTACK` (ex.: 2 ciclos consecutivos, ver `ALERT_FAIL_THRESHOLD` em
  `scheduler.py:56`), disparar playbook:
  - **Blackhole / null-route** no gateway via chamada a controlador (ex.: `curl` para API do
    firewall ou `iptables -I INPUT -s <src> -j DROP` no host monitorado).
  - **Rate-limiting** por origem (token bucket / `tc`).
- Para `PORT_SCAN`: fechar/ocultar portas expostas ou ativar fail2ban-like (banir IP de origem
  das conexões recusadas em `extra_tcp_checks`).
- Para `DATA_EXFILTRATION`: SNMP **SET** para derrubar a interface (`ifAdminStatus=down` em
  `1.3.6.1.2.1.2.2.1.7.ifIndex`, já há infra de SNMP em `snmp_engine.py`), ou quarantena via
  VLAN.
- Para `HOST_DOWN`/`NETWORK_CONGESTION`: acionar failover / reroute (se houver).
- O módulo deve ser **auditável**: registrar cada ação em `Alert`/`Incident` e exigir
  confirmação (human-in-the-loop) para ações destrutivas, com timeout de auto-reversão. Isso
  alinha o NOC Lite a arquiteturas SOAR descritas em artigos de IA para redes.

### 4.4 Usar datasets públicos reais (UNSW-NB15, CICIDS2017, NSL-KDD)

**Gap atual:** todo treino (ML) e todo few-shot (LLM) repousa em `generate_simulated_metrics`.
O modelo aprende o simulador, não a realidade.

**Sugestões específicas:**
- **UNSW-NB15** (mais aderente): 9 famílias de ataque + normal, features de fluxo (proto,
  dur, spkts, sbytes, etc.). Mapear para as 6 classes do NOC Lite (ex.: `Fuzzers`/`Exploits`
  → PORT_SCAN/DDoS; `Exfiltration` → DATA_EXFILTRATION; `DoS` → DDOS_ATTACK). Usar como
  augmentação do treino da árvore/MLP e como corpus de fine-tuning do LLM (converter cada
  registro em texto estilo `tokenise_metrics`).
- **CICIDS2017 / CSE-CIC-IDS2018**: rico em DDoS, PortScan, exfiltration (BOTNET), mas pesado
  (~3 TB). Usar amostras ou o subset já pré-processado.
- **NSL-KDD**: clássico, leve, bom para validação rápida do classificador tabular.
- **Ponto de atenção (gap de domínio):** esses datasets são **flow-centric** (NetFlow/sFlow),
  enquanto as features do NOC Lite são **host-centric** (ICMP/TCP/HTTP/SNMP por host,
  `extract_features_from_db`, Seção 2.1). Para aproveitá-los de fato, é preciso (a) coletar
  fluxos reais (ex.: exportar NetFlow do router para um coletor e alimentar a mesma janela de
  5 min), ou (b) fazer engenharia reversa de features equivalentes. Recomenda-se adicionar uma
  fonte de fluxo (ex.: `scapy`/`ntopng`) ao pipeline para fechar a lacuna entre o simulador
  sintético e os datasets públicos.

### 4.5 Outras melhorias pontuais (textuais)

- **Baselines dinâmicos por host:** substituir os 50 Mbps fixos (linha 146/154) e 120 ms
  (linha 170) por limiares aprendidos por host/link (média+múltiplos do desvio, ou EWMA),
  evitando falsos positivos em enlaces de capacidades distintas — prática padrão em papers de
  anomaly detection.
- **Ensemble/votação:** o endpoint já roda os 3 (`routes/anomalies.py:148-161`) mas devolve os
  resultados isolados. Adicionar um meta-classificador (voto majoritário ponderado por
  confiança calibrada) fecharia o pipeline "IA híbrida" (heurística + ML + LLM) que o artigo
  provavelmente defende.
- **Calibração de confiança:** a confiança do Gemini é autorreportada (linha 376) e a do ML é
  probabilidade de folha não calibrada (linha 289). Aplicar `CalibratedClassifierCV` (sklearn)
  no ML e ignorar/normalizar a do LLM tornaria a comparação (latency_ms + confidence) coerente.
- **Robustez do parser:** validar schema com `pydantic` (exigir tipos numéricos, clamp de
  confidence em [0,1]) em vez de apenas checar a chave `classification` (linha 373).
- **Viés de treino circular:** como o simulador e a heurística compartilham limiares, o ML é uma
  "árvore-cópia" da heurística. Misturar ruído gaussiano controlado e os datasets reais
  (4.4) quebra esse viés antes do fine-tuning.

---

## 5. Resumo da Cadeia de Dados (ponta a ponta)

```
[anomaly_simulator.generate_simulated_metrics]  (cenário sintético)
        │  (inject)
        ▼
[run_simulated_check_cycle / scheduler._host_check_blocking]  → CheckResult + SNMPMetric (DB)
        │
        ▼
[anomaly_classifier.extract_features_from_db]  → dict de 10 features (janela 5 min)
        ├─► classify_heuristic()              → regras de threshold (1.1)
        ├─► classify_ml()                     → DecisionTree treinada sintética (1.2)
        └─► tokenise_metrics() ─► classify_generative_ai()  → Gemini JSON (1.3)
        │
        ▼
[routes/anomalies.py /api/anomalies/classify]  → comparação dos 3 + latência
```

Em produção (sem simulador), a mesma cadeia é alimentada por `scheduler.py` + `checker.py`
(ping/tcp/http/dns reais) + `snmp_engine.py` (CPU/RAM/disco/rede reais via SNMPv2c), provando
que o classificador é agnóstico à origem dos dados — só consome o dicionário de features.

---

## 6. Conclusão do Coder

O subsistema de classificação está **bem estruturado e modular** (três abordagens isoladas,
fallbacks consistentes para heurística, API de comparação clara). Os limiares estão explícitos e
rastreáveis (Seção 1.1). O ponto fraco central é o **viés de dados sintéticos** (Seção 1.2 e 4.4):
tanto o ML quanto o LLM aprendem/argumentam sobre o próprio simulador, nunca sobre tráfego real.
As sugestões 4.1–4.4 (LLM local, LoRA, mitigação, datasets públicos + coleta de fluxo) são os
passos concretos para aproximar o sistema do estado-da-arte descrito no artigo, sem quebrar a
arquitetura atual.
