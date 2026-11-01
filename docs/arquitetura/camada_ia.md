# Arquitetura da Camada de Inteligência Artificial e Mitigação de Anomalias

Este documento detalha a organização modular da camada de Inteligência Artificial, Aprendizado de Máquina e Agentes Autônomos integrada ao NetSpot.

---

## 1. Visão Geral da Arquitetura Híbrida

O sistema adota uma abordagem híbrida de múltiplos motores para detecção, diagnóstico e mitigação de anomalias em tempo real:

```text
                  +-----------------------------------+
                  |      Telemetria de Rede (SNMP,    |
                  |     ICMP, TCP, HTTP/HTTPS, DNS)   |
                  +-----------------+-----------------+
                                    |
                                    v
                     +--------------+--------------+
                     |    Motor de Classificação   |
                     |  (Backend/services/         |
                     |   anomaly_classifier.py)    |
                     +--------------+--------------+
                                    |
       +----------------------------+----------------------------+
       |                            |                            |
       v                            v                            v
[1. Heurísticas NOC]      [2. Machine Learning]       [3. GenAI com RAG]
  - Regras determinísticas  - Isolation Forest          - LLM Local (Ollama)
  - Limiares de métricas    - Random Forest             - ChromaDB / Embeddings
  - Latência < 1ms          - F1 Macro ~0.89            - Recuperação sem vazamento
       |                            |                            |
       +----------------------------+----------------------------+
                                    |
                                    v
                     +--------------+--------------+
                     |      Ensemble Ponderado     |
                     |     com Calibração ECE      |
                     +--------------+--------------+
                                    |
                                    v
                     +--------------+--------------+
                     |  Agente Autônomo de Ciclo   |
                     |   Fechado (services/agent)  |
                     +--------------+--------------+
                                    |
       +----------------------------+----------------------------+
       |                            |                            |
       v                            v                            v
[Grounding & Audit]       [Tool Guardrails]            [Mitigação Kathará]
 - Validação de evidência  - Whitelist de comandos      - Ajuste iptables/rotas
 - Verificação factual     - Limiar de abstenção        - Reinício de serviços
 - Anti-alucinação (<3%)   - Auditoria e rollback       - Validação pós-ação
```

---

## 2. Módulos e Responsabilidades

### 2.1. Simulação e Classificação em Tempo Real (`Backend/services/`)
- `anomaly_simulator.py`:
  - Gerador determinístico de telemetria sintética para 11 cenários: `NORMAL`, `DDOS`, `PORT_SCAN`, `HOST_UNREACHABLE`, `MEMORY_LEAK`, `DATA_EXFILTRATION`, `DISK_EXHAUSTION`, `APP_CRASH`, `COMBINED_FAULT`, `NETWORK_CONGESTION` e `CUSTOM`.
  - Controle granular de métricas: CPU, Memória RAM, Disco, Latência ICMP, Perda de Pacotes, Jitter (RFC 3550), Conexões Ativas, Banda de Entrada/Saída e Código HTTP.
- `anomaly_classifier.py`:
  - Orquestrador do ensemble tríplice (Heurística + ML + GenAI).
  - Normalização e vetorização de telemetria.
  - Formatação da resposta estruturada com severidade, evidências, causa provável e plano de ação.

### 2.2. Agente Autônomo de Ciclo Fechado (`Backend/services/agent/`)
- `loop.py`: Ciclo fechado autônomo (Telemetria -> Decisão -> Verificação -> Ação -> Confirmação).
- `decision.py`: Lógica de decisão calibrada com suporte a Expected Calibration Error (ECE) e limiar de abstenção (abstention threshold de 0.70).
- `grounding.py` & `verifier.py`: Auditoria de evidências contra a telemetria bruta para impedir alucinações de LLM.
- `guardrails.py` & `tool_guard.py`: Filtros de segurança e lista estrita de comandos de mitigação autorizados.
- `tools.py`: Ações de remediação executáveis em containers (ex: redefinir rotas, aplicar regras de firewall, matar processos de alto consumo).
- `xai.py`: Explicabilidade das decisões tomadas via importâncias e justificativas textuais auditáveis.
- `memory.py`: Memória de trabalho e histórico de perfis para recuperação contextual.

### 2.3. Pipeline de Pesquisa e Benchmarks (`Backend/harness/`)
- `baselines.py`: Execução e comparação de modelos clássicos (Heurística, Isolation Forest, Random Forest, XGBoost).
- `datasets.py` & `splits.py`: Geração de splits de treino/teste por severidade disjunta e divisão temporal sem vazamento de dados (*data leakage*).
- `datasets_external.py`: Avaliação de generalização em datasets externos conhecidos (UNSW-NB15 e CSE-CIC-IDS2018).
- `metrics.py`: Cálculo rigoroso de F1 Macro, tempo de inferência, ECE (calibração) e Brier score.
- `kathara/`: Runner de testes de injeção de falhas e mitigação em laboratório virtual emulado com Docker e Kathará.
- `report.py` & `repro.py`: Automação de geração de manifestos científicos, gráficos comparativos e relatórios HTML.

### 2.4. Recuperação Aumentada por Vetores (`RAG/`)
- `rag_pipeline.py`: Vetorização dos incidentes em ChromaDB com cálculo de similaridade de cosseno.
- `src/dataset.csv`: Base de conhecimento histórica de causas e procedimentos operacionais padronizados (SOPs).
- `index.html`: Interface visual interativa para experimentação e busca vetorial de soluções de rede.

---

## 3. Reprodutibilidade e Testes

Para executar os testes e reproduzir os benchmarks:
```bash
# Executar a suíte de testes de IA e contratos de agente
pytest Backend/services/agent/tests -v

# Executar a suíte de detecção de anomalias
pytest Backend/tests/test_anomalies.py -v

# Reproduzir baselines e gerar gráficos para o artigo
python scripts/eval_benchmarks.py
```
