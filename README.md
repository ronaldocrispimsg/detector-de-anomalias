# NetSpot: monitoração de rede com classificação de anomalias

![Backend](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.11-green)
![Container](https://img.shields.io/badge/Container-Docker%20Compose-blueviolet)
![Release](https://img.shields.io/badge/Release-v1.1.1-blue)
![Testes](https://img.shields.io/badge/Testes-Passando-brightgreen)
![Licença](https://img.shields.io/badge/Licen%C3%A7a-MIT-orange)

NetSpot é um NOC Lite, isto é, um centro de operações de rede de escopo reduzido para laboratórios e infraestruturas pequenas. Ele monitora hosts e ativos por ICMP, TCP, HTTP/HTTPS, DNS e SNMP, mostra o estado em painéis web, mantém o histórico de incidentes e envia alertas. Esta versão incorpora as otimizações do NetSpot Core v1.1.1 (autocura de banco, Graceful Shutdown, circuit breaker e sanitização de segurança).

O repositório também contém o trabalho experimental em torno do classificador de anomalias do sistema: simulador de falhas, conjuntos de dados sem vazamento, baselines clássicos, agente de linguagem com saída estruturada, memória de perfis históricos, calibração de confiança, explicabilidade e mitigação em laboratório. Os experimentos são reprodutíveis e os resultados ficam registrados em `Backend/harness/results/`.

## Arquitetura

```text
Navegador
  ├── HTTP :8080  Frontend (Nginx): painel, simulador e histórico de incidentes
  └── HTTP :8000  Backend (FastAPI): API REST e documentação Swagger

Backend (FastAPI)
  ├── PostgreSQL 15: hosts, métricas, incidentes e usuários
  ├── ICMP, TCP, HTTP/HTTPS e DNS: hosts monitorados
  ├── SNMP (UDP :161): agentes nativos em Windows e Linux
  └── RabbitMQ (AMQP): filas internas; alertas por Telegram e webhook para o N8N
```

## Monitoração

- ICMP: latência em milissegundos e perda de pacotes.
- TCP: verificação de porta aberta ou fechada.
- HTTP/HTTPS: código de status e tempo de resposta.
- DNS: validação da resolução de nomes.
- SNMP multivendor: CPU, memória, disco e tráfego de entrada e saída, com mapeamento automático para Linux (UCD-SNMP) e Windows (HOST-RESOURCES-MIB).
- Saúde dos ativos e SLA: pontuação de saúde por host, jitter e tendências.
- Alertas por Telegram, com antispam, e webhook para automações no N8N.
- Retenção do histórico configurável em `NETSPOT_RETENTION_DAYS`, com padrão de 30 dias. O valor 0 desliga a limpeza.

## Simulador e classificação de anomalias

O simulador gera telemetria para 11 cenários: operação normal, ataque DDoS volumétrico, varredura de portas, host inacessível, vazamento de memória, exfiltração de dados, esgotamento de disco, falha de aplicação, falha combinada, congestionamento de rede e modo personalizado. No painel do simulador, os valores de CPU, RAM, disco, latência, perda, jitter, banda, conexões e código HTTP são ajustados com controle deslizante.

O classificador combina três motores:

1. Regras heurísticas de NOC, com limiares por métrica.
2. Aprendizado de máquina, com Isolation Forest para detecção de anomalia e Random Forest para classificação.
3. Geração de texto local com Ollama, usando recuperação de casos no dataset `netspot_anomaly_dataset.csv` via ChromaDB.

A resposta final traz o cenário provável, a severidade, as evidências, a causa provável, o impacto e um playbook de mitigação.

## Artigo: detecção e mitigação de anomalias de rede com LLMs open source

O NOC Lite monitora hosts por ICMP, TCP, HTTP/DNS e SNMP e classifica uma amostra de telemetria em um dos dez cenários, com justificativa e plano de mitigação. O protótipo original media a si mesmo: treino e teste saíam do mesmo simulador, o motor generativo lia o rótulo e o índice de recuperação guardava o nome do cenário. O trabalho reconstrói a avaliação para medir generalização sobre dados não vistos. A camada de pesquisa fica em `Backend/harness/` e `Backend/services/agent/`.

### Objetivos

Quatro perguntas guiam o trabalho:

1. Um modelo de linguagem open source é competitivo com métodos clássicos em dados que ele não viu no treino?
2. O ajuste fino com LoRA e QLoRA melhora sobre a versão sem treino, e em quanto?
3. A memória de casos agrega robustez sem vazar o rótulo do cenário?
4. As saídas são calibradas, auditáveis e as justificativas fiéis à telemetria?

### Metodologia

**Dados e divisões.** O simulador gera telemetria para os dez cenários com faixas de severidade separadas entre treino, validação e teste, de modo que os conjuntos não compartilhem a faixa do gerador. O treino usa anomalias claras e o teste usa anomalias sutis, o que mede generalização em vez de memorização. O CSV real entra por divisão temporal. UNSW-NB15 e CSE-CIC-IDS2018 entram como holdout externo, e os cenários do Kathará servem de laboratório emulado. Um teste automático falha se o rótulo aparecer na entrada, na consulta de recuperação ou no índice.

**Motores comparados.** No mesmo conjunto rodam heurísticas, Isolation Forest + Random Forest, XGBoost se instalado, o modelo de linguagem pré-treinado com poucos exemplos, o modelo ajustado com LoRA/QLoRA e a versão com memória de casos históricos.

**Métricas e calibração.** F1 macro, tempo de inferência, taxa de alucinação de métricas, calibração via Expected Calibration Error (ECE) e Brier score, e concordância com a mitigação no laboratório emulado.

**Ciclo fechado.** O simulador roda uma anomalia na rede emulada, a telemetria vai para o agente e a mitigação é aplicada no container alvo por um comando permitido, como ajustar iptables ou reiniciar o serviço. O teste mede se a mitigação restabeleceu o tráfego sem intervenção manual.

### Estrutura dos experimentos

```text
Backend/harness/
├── datasets.py             # Divisões sintéticas e CSV real, sem vazamento
├── datasets_external.py    # Holdout UNSW-NB15 e CSE-CIC-IDS2018
├── baselines.py            # Heurística, Isolation Forest, Random Forest e XGBoost
├── engines/
│   ├── llm_agent.py        # Modelo de linguagem com saída estruturada
│   └── rag_retriever.py    # Memória de perfis históricos sem rótulo
├── metrics.py              # F1, tempo, alucinação, ECE e Brier
├── kathara/                # Injeção, runner e ciclo fechado na rede emulada
└── results/                # Resultados brutos, manifesto e figuras do artigo

Backend/services/agent/
├── representation.py       # Entrada semântica para o modelo
├── structured.py           # Esquema Pydantic e validação da saída
├── grounding.py            # Verificação de evidências contra a telemetria
├── decision.py             # Calibração e limiar de abstenção
├── tools.py                # Ações de mitigação permitidas
├── loop.py                 # Ciclo fechado: telemetria -> decisão -> mitigação -> verificação
└── memory.py               # Perfis históricos para recuperação

docs/revisao/               # Artigo em LaTeX, bibliografia e figuras
```

### Resultados principais

Os números abaixo saem de `Backend/harness/results/baselines.jsonl` e `decision_calibration.json`, gerados por `make repro`:

| Motor | F1 macro | Tempo de inferência |
|:--|:--|:--|
| Heurística | 0,78 | < 1 ms |
| Isolation + Random Forest | 0,89 | 2 ms |
| Modelo base (sem treino) | 0,61 | 820 ms |
| LoRA/QLoRA ajustado | 0,84 | 850 ms |
| LoRA/QLoRA + memória | 0,91 | 890 ms |

A memória de perfis históricos reduz o erro em cenários com pouca telemetria. A taxa de alucinação do motor generativo fica abaixo de 3% com a validação de evidências, e a calibração com limiar de abstenção evita ação automática quando a confiança é menor que 0,70.

## Estrutura do projeto

```text
.
├── Backend/                        # Código-fonte do backend
│   ├── core/                       # Configurações gerais
│   ├── harness/                    # Camada de pesquisa, dados e baselines
│   ├── routes/                     # Endpoints da API (hosts, incidentes, anomalies)
│   ├── services/                   # Motores de anomalia e agente
│   │   ├── agent/                  # Agente de decisão, mitigação e ciclo fechado
│   │   ├── anomaly_classifier.py   # Classificador de anomalias
│   │   └── anomaly_simulator.py    # Simulador de telemetria
│   ├── snmp/                       # MIBs, OIDs e cliente SNMP
│   ├── tests/                      # Testes unitários e de integração
│   ├── Dockerfile                  # Imagem do backend
│   └── main.py                     # Inicialização da aplicação FastAPI
├── Frontend/                       # Interface web servida por Nginx
│   ├── css/                        # Folhas de estilo (style.css, simulator.css)
│   ├── js/                         # Lógica da interface (app.js, simulator.js)
│   ├── dashboard.html              # Painel principal de hosts
│   ├── simulator.html              # Simulador e classificador de anomalias
│   └── incidents.html              # Histórico de incidentes
├── Database/                       # Diretório de dados do PostgreSQL (ignorado no Git)
├── RabbitMQ/                       # Diretório de dados do RabbitMQ (ignorado no Git)
├── N8N/                            # Workflows de automação
├── RAG/                            # Interface web e pipeline do classificador e do RAG
├── Makefile                        # Comandos de teste e reprodução
└── docker-compose.yml              # Orquestração dos cinco serviços
```

## Como executar

Pré-requisitos: Docker e Docker Compose v2.

```bash
cp .env.example .env
docker compose up -d --build
```

Cinco serviços sobem: PostgreSQL, backend, frontend, RabbitMQ e N8N. Antes de subir, configure o `.env`. `NETSPOT_SECRET_KEY` assina os tokens de sessão e `NETSPOT_DEFAULT_ADMIN_PASSWORD` define a senha do usuário `admin` criado na primeira subida. O primeiro login exige a troca de senha.

`docker compose ps` mostra o estado dos containers, `docker compose logs -f backend` acompanha os logs e `docker compose down` derruba tudo. As tabelas do banco são criadas na primeira subida com autocura automatizada.

## Endereços de acesso

| Serviço | Endereço |
|:--|:--|
| Painel e login | http://localhost:8080 |
| Simulador de anomalias | http://localhost:8080/simulator.html |
| Histórico de incidentes | http://localhost:8080/incidents.html |
| API e Swagger | http://localhost:8000/docs |
| RabbitMQ Management | http://localhost:15672 |
| N8N | http://localhost:5678 |
| RAG Playground | http://localhost:8085 |

O RAG Playground pode ser servido fora do Docker com `python3 -m http.server 8085 --directory RAG`.

## Demonstração

1. Suba o sistema com `docker compose up -d --build` e confirme que os serviços estão saudáveis (`docker compose ps`).
2. Abra http://localhost:8080. A página inicial redireciona para o login. Entre com `admin` e a senha definida; o primeiro acesso exige a troca de senha.
3. Abra o simulador em http://localhost:8080/simulator.html. Clique em um dos dez cenários para gerar a amostra de métricas e ver o diagnóstico dos três motores: heurística, Machine Learning e IA generativa com RAG. O botão Benchmark roda os cenários e compara a acurácia de cada motor.
4. No painel principal, cadastre um host com Nome, Endereço/IP, URL HTTP ou portas TCP. O histórico de métricas, saúde do ativo, SLA e alertas aparecem no painel. A "Descoberta de Rede" varre a sub-rede CIDR.
5. Em http://localhost:8080/incidents.html está o histórico completo de incidentes, com filtros por período, host e tipo.
6. A documentação interativa da API está em http://localhost:8000/docs.

### Ollama (opcional)

O terceiro motor do classificador usa um modelo local. Instale o Ollama no host e baixe um dos modelos aceitos:

```bash
ollama pull qwen2.5:7b
```

O backend acessa o Ollama do host em `host.docker.internal:11434`, e a disponibilidade aparece em `/anomalies/genai/status`.

## Licença

Distribuído sob a licença MIT.
