# NetSpot - Sistema Inteligente de Monitoramento de Rede (NOC Lite) & Simulador Multi-Motor RAG

![NetSpot Architecture](https://img.shields.io/badge/Architecture-Clean%20Architecture-blue)
![Python](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.12-green)
![Docker](https://img.shields.io/badge/Container-Docker%20%26%20Docker%20Compose-blueviolet)
![Tests](https://img.shields.io/badge/Tests-35%2F35%20Passed%20(100%25)-brightgreen)
![License](https://img.shields.io/badge/License-MIT-orange)

**NetSpot** é um sistema completo e moderno de **Network Operations Center (NOC Lite)** desenvolvido para monitoramento em tempo real de infraestruturas de TI, servidores, ativos de rede, conectividade e **Simulação Visual de Anomalias orientada a Inteligência Artificial Híbrida**.

O sistema combina monitoramento passivo e ativo (**ICMP Ping, Portas TCP, HTTP/HTTPS, DNS e SNMP Multivendor**), além de um **Classificador Híbrido Multi-Motor de Anomalias** baseado em Heurísticas, Machine Learning (Isolation Forest / Random Forest) e **RAG (Retrieval-Augmented Generation)** com banco vetorial **ChromaDB**.

---

## 🏛️ Arquitetura do Sistema

O projeto foi construído seguindo os princípios de **Clean Architecture**, **SOLID**, **DRY**, **KISS** e **Isolamento de Serviços por Containers**.

```text
                                +-------------------+
                                |   Navegador Web   |
                                | (Dashboard HTML5) |
                                +---------+---------+
                                          | :8080
                                          v
+------------------+             +-------------------+             +------------------+
|   Base de Dados  |  SQLAlchemy  |  Backend FastAPI  |   PySNMP    | Agentes Nativos  |
|  PostgreSQL 15   |<----------->|   (Python 3.12)   |<----------->| (Windows / Linux)|
+------------------+  AsyncPG    +---------+---------+  UDP :161   +------------------+
                                          |           \
                                          | AMQP       \ ChromaDB RAG Vector Store
                                          v             v
                                 +-------------------+  +-------------------+
                                 |     RabbitMQ      |  | netspot_anomaly_  |
                                 +---------+---------+  |    dataset.csv    |
                                           | Webhook    +-------------------+
                                           v
                                 +-------------------+             +------------------+
                                 |  N8N Automation   |------------>| Alertas Telegram |
                                 +-------------------+             +------------------+
```

---

## ✨ Funcionalidades Principais

* **🎛️ Simulador & Classificador Visual de Anomalias (1 Clique)**:
  * **11 Cenários Integrados**: Operação Normal, DDoS Volumétrico, Varredura de Portas (Port Scan), Host Inacessível, Vazamento de Memória, Exfiltração de Dados, Esgotamento de Disco, Falha de Aplicação (503/500), Falha Múltipla Combinada, Congestionamento de Rede e Cenário Personalizado.
  * **Painel Interativo de Sliders**: Ajuste em tempo real de CPU, RAM, Disco, Latência, Loss, Jitter, Banda In/Out, Conexões TCP e HTTP status.
* **🧠 Classificação Híbrida Multi-Motor por Ensemble Ponderado**:
  * **Motor 1 — Heurística Regrada (Peso 0.40 / 40%)**: Validação determinística de SLAs e normas IETF.
  * **Motor 2 — Machine Learning (Peso 0.35 / 35%)**: Isolation Forest (Anomaly Score) + Random Forest Classifier.
  * **Motor 3 — GenAI Cognitiva + RAG ChromaDB (Peso 0.25 / 25%)**: Busca vetorial por similaridade no banco ChromaDB (baseado no dataset real `netspot_anomaly_dataset.csv`) e geração de Causa Raiz, Impacto NOC e Playbook de Mitigação.
* **🖥️ Monitoramento Multi-Protocolo**:
  * **ICMP Ping**: Latência em ms e taxa de perda de pacotes.
  * **TCP**: Checagem de portas abertas/fechadas.
  * **HTTP / HTTPS**: Verificação de código de status HTTP e tempo de resposta.
  * **DNS**: Validação de resolução de nomes de domínio.
* **📊 Agente SNMP Nativo Multivendor**:
  * Leitura em tempo real de CPU, Memória RAM, Disco e Tráfego de Rede (Download e Upload).
  * Mapeamento automático para MIBs **Linux (UCD-SNMP)** e **Windows (HOST-RESOURCES-MIB)**.
* **🧹 Política de Retenção de Dados Configurável**:
  * Limpeza automática configurável via `NETSPOT_RETENTION_DAYS`.
* **🔔 Gestão de Alertas e Incidentes**:
  * Notificações instantâneas via webhook integrado ao **N8N** e Telegram.

---

## 📁 Estrutura de Diretórios

```text
NetSpot/
├── Backend/                    # Container FastAPI (Python 3.12)
│   ├── core/                   # Banco de Dados, Segurança e Auth JWT
│   ├── models/                 # Modelos ORM SQLAlchemy
│   ├── schemas/                # Schemas Pydantic / DTOs
│   ├── services/               # Regras de Negócio, Métricas, Anomalias e Retenção
│   │   ├── anomaly_classifier.py # Classificador Híbrido (Heurística, ML, RAG ChromaDB)
│   │   └── anomaly_simulator.py  # Simulador Estocástico de Telemetria
│   ├── snmp/                   # Módulo SNMP Multivendor (Discovery, Cache, Resolvers)
│   ├── routes/                 # Endpoints RESTful da API (/anomalies, /hosts, etc.)
│   ├── tests/                  # Suíte de Testes Automatizados (Pytest - 35 Testes)
│   │   ├── test_anomalies.py   # Testes do Simulador e Classificador Ensemble RAG
│   │   ├── test_api_routes.py  # Testes de Integração das Rotas RESTful
│   │   ├── test_checker.py     # Testes de Ping, TCP, HTTP e DNS
│   │   ├── test_metrics.py     # Testes de Saúde, SLA, Jitter e Tendências
│   │   ├── test_models_schemas.py # Testes de Modelos e DTOs
│   │   ├── test_retention.py   # Testes da Política de Retenção de Dados
│   │   └── test_snmp.py        # Testes do Módulo SNMP e Conversores
│   ├── main.py                 # Ponto de Entrada da Aplicação (FastAPI + Static Files)
│   ├── scheduler.py            # Orquestrador de Polling e Coleta Assíncrona
│   └── snmp_engine.py          # Motor de Coleta SNMP de Alta Performance
├── Frontend/                   # Container Nginx / Servidor Estático SPA
│   ├── css/                    # Estilos CSS (Design System Glassmorphism)
│   │   └── simulator.css       # Estilos Visuais do Simulador de Anomalias
│   ├── js/                     # Lógica JavaScript (Dashboard e Simulador Visual)
│   │   └── simulator.js        # Lógica do Simulador e Integração REST/RAG
│   ├── simulator.html          # Painel do Simulador Visual de Anomalias
│   ├── dashboard.html          # Painel Principal do NOC
│   ├── incidents.html          # Histórico de Incidentes
│   └── nginx.conf              # Configuração Nginx
├── RAG/                        # Módulo RAG Playground (ChromaDB + LangChain)
│   ├── rag_pipeline.py         # Pipeline isolado RAG Python
│   └── index.html              # Playground Visual de 5 Etapas RAG
├── Database/                   # Volume Persistente PostgreSQL
├── N8N/                        # Workflows de Automação de Alertas
├── RabbitMQ/                   # Mensageria e Filas de Eventos
├── scripts/                    # Automação de Agentes SNMP (Windows/Linux)
├── netspot_anomaly_dataset.csv # Dataset Real de Anomalias de Rede
└── docker-compose.yml          # Orquestração de Containers
```

---

## 🚀 Como Executar o Projeto

### Pré-requisitos

* **Docker** (versão 20.10 ou superior)
* **Docker Compose** (versão 2.0 ou superior)

### 1. Iniciar todos os Containers

Na raiz do projeto, execute:

```bash
docker-compose up -d --build
```

O Docker Compose inicializará automaticamente os 5 serviços da infraestrutura:
1. `netspot-db` (PostgreSQL 15 em `localhost:5432`)
2. `netspot-backend` (FastAPI em `localhost:8000`)
3. `netspot-frontend` (Nginx em `localhost:8080`)
4. `netspot-rabbitmq` (RabbitMQ Management em `localhost:15672`)
5. `netspot-n8n` (N8N Automation em `localhost:5678`)

---

## 🧪 Suíte de Testes Automatizados (Pytest)

O NetSpot conta com **35 testes automatizados** com 100% de taxa de aprovação.

Para executar todos os testes automatizados, rode:

```bash
# Execução local via ambiente python:
python -m pytest Backend/tests -v

# Ou via container docker backend:
docker exec -e PYTHONPATH=. netspot-backend python -m pytest Backend/tests -v
```

---

## 🌐 Endereços de Acesso

| Serviço | URL de Acesso | Descrição |
| :--- | :--- | :--- |
| 🎛️ **Simulador Visual de Anomalias** | [http://localhost:8080/simulator.html](http://localhost:8080/simulator.html) | Simulador Visual 1 Clique com RAG ChromaDB |
| 🖥️ **NOC Dashboard** | [http://localhost:8080/dashboard.html](http://localhost:8080/dashboard.html) | Painel Principal de Monitoramento de Ativos |
| 📚 **RAG Playground** | [http://localhost:8085](http://localhost:8085) | Visualizador Interativo das 5 Etapas do RAG |
| 🔌 **Backend API Docs (Swagger)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Documentação de Endpoints RESTful |
| 🐇 **RabbitMQ Management** | [http://localhost:15672](http://localhost:15672) | Console de Gestão de Filas |
| ⚡ **N8N Automation** | [http://localhost:5678](http://localhost:5678) | Workflows de Alerta e Telegram |

---

## 🛠️ Tecnologias Utilizadas

* **Backend**: Python 3.12, FastAPI, SQLAlchemy, AsyncPG, PySNMP, Pydantic, Scikit-learn, ChromaDB, LangChain, Uvicorn.
* **Frontend**: HTML5, Vanilla CSS3 (Dark Glassmorphism UI), JavaScript ES6+, Chart.js, Nginx Alpine.
* **Banco Vetorial & RAG**: ChromaDB (Vetorização e embeddings), Ollama Local / GenAI Engine.
* **Banco de Dados**: PostgreSQL 15.
* **Mensageria & Automação**: RabbitMQ, N8N Workflows.
* **Infraestrutura**: Docker & Docker Compose.

---

## 📄 Licença

Este projeto é disponibilizado sob a licença **MIT**. Sinta-se livre para utilizar, modificar e contribuir!