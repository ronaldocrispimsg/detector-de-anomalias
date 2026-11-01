# NetSpot v1.1.0 — Versão Estável Consolidada e Hardening Completo (NOC Lite)

Lançamento oficial da versão **v1.1.0** do **NetSpot**, sistema de Network Operations Center (NOC Lite) desenvolvido como Trabalho de Conclusão de Curso (TCC) em Sistemas de Informação no Instituto Federal do Norte de Minas Gerais (IFNMG) — Campus Januária pelo desenvolvedor Ronaldo Crispim.

A versão **v1.1.0** consolida o ciclo de auditoria profunda, hardening defensivo (OWASP), acessibilidade digital (WCAG 2.1 AA), escalabilidade para alta densidade (126 hosts simultâneos) e estabilidade operacional do repositório, garantindo conformidade rigorosa entre o código-fonte, a infraestrutura conteinerizada e a documentação acadêmica.

---

## 📊 Comparativo Síntese: v1.0.0 vs v1.1.0

| Dimensão / Módulo | NetSpot v1.0.0 (Release Inicial) | NetSpot v1.1.0 (Versão Estável Consolidada) |
| :--- | :--- | :--- |
| **Cobertura de Testes** | 61 testes automatizados | **86 testes automatizados no Pytest (100% aprovados em ~7.2s)** |
| **Cenários de Laboratório** | 40 hosts Kathará | **Dois ambientes: 40 hosts e 126 hosts (alta densidade)** |
| **Resolução DNS Kathará** | Registros básicos em zona direta | **Zonas BIND9 diretas e reversas completas (`db.10.0.1..3`)** |
| **Agentes SNMP em Roteadores** | Inativos no boot dos roteadores | **Ativos no boot em `router_core` e `router_lab1..3`** |
| **Segurança Bcrypt** | Padrão da biblioteca sem trava prévia | **Validação defensiva estrita do limite de 72 bytes UTF-8** |
| **Políticas de Acesso (RBAC)** | Validação genérica de token | **Bloqueio em primeiro acesso (`must_change_password`) e RBAC admin** |
| **Proteção Força Bruta** | Bloqueio permanente em falhas de senha | **Bloqueio temporal dinâmico (`locked_until = now + 1 min`)** |
| **Isolamento de Banco** | RLS básico planejado | **Ativação formal de `FORCE ROW LEVEL SECURITY` em todas as tabelas** |
| **Sondagens Manuais** | Sequenciais no endpoint de checagem | **Paralelismo intra-host via `asyncio.gather` (Ping, TCP e Web)** |
| **Inferência Causa Provável** | Consultava banco para todos os nós | **Fast-path imediato para nós recém-importados/UNKNOWN** |
| **Health Score Sub-milissegundo** | Penalizava latências `0.0 ms` | **Tratamento exato com `is not None` (zero penalidade indevida)** |
| **Supressão Anti-Flapping** | Chave por host (podia suprimir recovery) | **Chave composta `host:event` (isolamento de recuperação)** |
| **Cálculo de SLA** | Soma simples de períodos | **Algoritmo de União de Intervalos (*Interval Merging*)** |
| **Descoberta Nmap na LAN** | Temporização fixa por porta | **Calibração dinâmica por CIDR (*CIDR-Aware Timing* /24 e /20)** |
| **Blindagem Frontend** | TextContent padrão | **Sanitização estrita contra XSS em atributos inline (`escapeJsSingleQuotedAttr`)** |
| **Telemetria SNMP no DOM** | Exigia F5 na 1ª leitura de telemetria | **Transição cirúrgica em voo da Face 3 (`updateHostCardInPlace`)** |
| **Polling do Dashboard** | Padrão N+1 em `loadLastResult` | **Sintetização local direta sem requisições HTTP adicionais** |
| **Fontes & Tipografia** | Dependência mista de CDNs externas | **100% Offline-First (WOFF2 locais `Open Sans` e `Roboto`)** |
| **Compatibilidade Mobile** | Focado primariamente em desktop | **Responsividade avançada para smartphones e telas 4K/Ultrawide** |
| **Infraestrutura & Docker** | Porta 8080 fixa, sem healthchecks | **`${NETSPOT_PORT:-8080}:80`, healthchecks em RabbitMQ e n8n** |
| **Notificações Telegram** | Interpolação crua no HTML do n8n | **Sanitização estrita de `<`, `>`, `&` via `esc(v)` no nó n8n** |

---

## 🛠️ Detalhamento Completo das Modificações desde a v1.0.0

### 1. Segurança Defensiva e Proteção de Autenticação (OWASP)
* **Validação do Teto de 72 Bytes no Bcrypt** ([`Backend/security.py`](file:///home/crispim/Documentos/netspot/Backend/security.py)):
  Implementada checagem defensiva de comprimento UTF-8 em `hash_password` e `verify_password`. Payloads superiores a 72 bytes disparam `HTTP 400 Bad Request` antes de atingir a biblioteca de hashing, prevenindo exceções internas ou ataques DoS de sobrecarga computacional.
* **Enforcement de Primeiro Acesso Obrigatório** ([`Backend/dependencies.py`](file:///home/crispim/Documentos/netspot/Backend/dependencies.py)):
  A dependência de autenticação `get_current_user` agora intercepta todas as rotas operacionais da API (`/hosts/*`, `/network/*`, `/metrics/*`). Se o operador possuir `must_change_password=True`, o acesso é bloqueado com `HTTP 403 Forbidden` (`detail: "É obrigatório alterar a senha inicial no primeiro acesso."`), liberando exclusivamente a rota `/auth/change-password`.
* **Proteção contra Força Bruta Resiliente**:
  Corrigida a lógica de bloqueio na alteração de credenciais. Em vez de uma trava permanente dependente de intervenção manual no banco, o sistema aplica um bloqueio temporal dinâmico (`locked_until = now_utc + 1 min`) após a 5ª tentativa incorreta consecutiva, desbloqueando automaticamente expirado o prazo.
* **Controle de Acesso Baseado em Funções (RBAC)**:
  Operações críticas de destruição e expurgo de dados (`DELETE /host/delete/{host_name}` e exclusão definitiva da lixeira) foram protegidas pela dependência estrita `get_current_admin`, impedindo que operadores convencionais removam ativos do inventário.
* **Resolução Reversa DNS Segura e Thread-Safe** ([`Backend/utils.py`](file:///home/crispim/Documentos/netspot/Backend/utils.py)):
  Eliminada a mutação global concorrente de `socket.setdefaulttimeout(0.8)`. A resolução reversa assíncrona foi migrada para instâncias isoladas de `dns.resolver.Resolver()` com timeout explícito de 0.8s, eliminando condições de corrida entre threads coletoras.
* **Isolamento de Banco via Row Level Security (RLS)** ([`Backend/security_rls_template.sql`](file:///home/crispim/Documentos/netspot/Backend/security_rls_template.sql)):
  Criação e aplicação de script de políticas com `FORCE ROW LEVEL SECURITY` cobrindo todas as tabelas centrais do sistema (`hosts`, `checks`, `alerts`, `incidents`, `snmp_metrics`).

---

### 2. Otimização de Performance, Concorrência e Métricas
* **Sondagens Manuais Concorrentes Intra-Host**:
  A rota de checagem imediata `POST /host/check/{host_name}` em [`Backend/routes/hosts.py`](file:///home/crispim/Documentos/netspot/Backend/routes/hosts.py) agora dispara a sondagem ICMP Ping, a verificação de todas as portas TCP cadastradas e o teste Web HTTP em paralelo via `asyncio.gather`, reduzindo o tempo de resposta percebido pelo operador de vários segundos para menos de 400ms.
* **Fast-Path para Hosts Recém-Importados (`infer_probable_cause`)**:
  Adicionada detecção antecipada para nós com status `UNKNOWN` ou pendentes de coleta inicial (`baseline_pending`). O motor de diagnóstico retorna imediatamente o status de provisionamento sem disparar 504 consultas SQL repetitivas à tabela de histórico, eliminando sobrecarga no banco após importações em massa.
* **Tratamento Preciso de Latência Sub-milissegundo (`0.0 ms`)** ([`Backend/metrics.py`](file:///home/crispim/Documentos/netspot/Backend/metrics.py)):
  Substituída a verificação de verdade booleana `if latency:` por `if latency is not None:`. Em redes locais Gigabit de alta performance onde a latência ICMP é reportada como `0.0 ms`, o cálculo de Health Score não mais aplica a penalidade indevida de -15 pontos de RTT.
* **Histerese Anti-Flapping com Supressão por Evento Composto** ([`Backend/notifications.py`](file:///home/crispim/Documentos/netspot/Backend/notifications.py)):
  A chave do supressor de rajadas foi reestruturada de `{host_name}` para `{host_name}:{event_type}`. Isso assegura que tempestades de alertas de queda (`down`) não suprimam a notificação crucial de restabelecimento do serviço (`recovery`).
* **Algoritmo de União de Intervalos de Tempo (*Interval Merging*) para SLA**:
  Refatorado o cálculo de disponibilidade histórica em [`Backend/metrics.py`](file:///home/crispim/Documentos/netspot/Backend/metrics.py), fundindo janelas temporais de incidentes concorrentes sobrepostos para garantir precisão matemática estrita na métrica de SLA.
* **Calibração Dinâmica de Varredura Nmap (*CIDR-Aware Timing*)**:
  Em [`Backend/routes/hosts.py`](file:///home/crispim/Documentos/netspot/Backend/routes/hosts.py), o motor de descoberta automática calibra dinamicamente as flags do Nmap (`--min-rtt-timeout`, `--max-rtt-timeout`, `--max-retries`, `--min-rate`) de acordo com a máscara de rede (/24 vs /20), mitigando a perda de pacotes por ARP a frio (*Cold ARP Cache*) e prevenindo o estouro da fila `unres_qlen` do kernel Linux.
* **Dimensionamento do Pool Assíncrono do SQLAlchemy**:
  Em [`Backend/database.py`](file:///home/crispim/Documentos/netspot/Backend/database.py), o pool de conexões foi ajustado com `pool_size=35`, `max_overflow=30` e `pool_timeout=30`, suportando a carga simultânea de 126 hosts emulados sem exaustão de conexões.

---

### 3. Frontend SPA, Design System, UI/UX e Acessibilidade (WCAG 2.1 AA)
* **Blindagem contra Cross-Site Scripting (XSS) em Atributos Inline** ([`Frontend/js/app.js`](file:///home/crispim/Documentos/netspot/Frontend/js/app.js)):
  Implementada a função auxiliar `escapeJsSingleQuotedAttr` para sanitizar aspas simples, barras invertidas e caracteres de quebra de linha em handlers `onclick` montados dinamicamente no DOM, prevenindo injeções arbitrárias de script em nomes de hosts manipulados.
* **Transição Dinâmica da Face 3 SNMP no DOM em Tempo Real**:
  Implementado o método cirúrgico `updateHostCardInPlace`. Quando um host recebe sua primeira coleta bem-sucedida de telemetria SNMP, a face 3 do card é injetada no DOM em tempo de execução com seus gauges de CPU, RAM, Disco e RX/TX, eliminando a exigência de recarregar a página (F5) para visualizar as métricas de hardware.
* **Eliminação de Requisições N+1 no Polling do Dashboard**:
  A rotina `loadLastResult` foi otimizada para sintetizar o estado das portas TCP e HTTP diretamente do payload já entregue por `/hosts/list`, extinguindo centenas de chamadas HTTP redundantes a cada intervalo de 10 segundos.
* **Filtragem Inteligente de Protocolos nos Gráficos de Qualidade**:
  Os gráficos de SLA e histórico de latência filtram curvas de protocolos não monitorados (por exemplo, suprimem a legenda e linha HTTP se o host monitora apenas ICMP/TCP), despoluindo a visualização para o operador.
* **Responsividade Avançada para Mobile e Telas 4K / Ultrawide** ([`Frontend/css/style.css`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css)):
  Inclusão de media queries especializadas e ajustes de tipografia fluida para navegação fluida em telas de celulares (iOS Safari com salvaguarda na Notification API) e painéis de parede NOC de alta resolução (4K / 3840px).
* **Consistência Geométrica de Botões e Affordance Visual**:
  Padronização de hierarquia visual e estados de botões (`.btn-primary`, `.btn-secondary`, `.btn-danger`), inclusão de alternador dinâmico de ícones no botão "Selecionar Todos" da Lixeira e preservação de ícones vetoriais SVG durante estados de carregamento (*spinners*).
* **Operação 100% Offline-First e Autossuficiente**:
  Removidas todas as dependências de fontes remotas do Google Fonts (`fonts.googleapis.com` / `fonts.gstatic.com`). O sistema opera integralmente em redes isoladas (DMZs/air-gapped) utilizando tipografia WOFF2 local (`Open Sans` e `Roboto`).

---

### 4. Infraestrutura Conteinerizada, Docker Compose e Automação n8n
* **Parametrização da Porta Externa do Frontend**:
  Mapeamento da porta do Nginx em [`docker-compose.yml`](file:///home/crispim/Documentos/netspot/docker-compose.yml) flexibilizado para `"${NETSPOT_PORT:-8080}:80"`, permitindo alterar a porta de publicação do painel diretamente no arquivo `.env`.
* **Healthchecks Nativos em Microsserviços**:
  Adicionadas sondagens de integridade nos containers `rabbitmq` (`rabbitmq-diagnostics -q ping`) e `n8n` (`/healthz`), com política `depends_on: condition: service_healthy` para garantir que o backend inicie somente após o broker de mensagens estar plenamente pronto.
* **Sanitização de Mensagens HTML no Fluxo n8n / Telegram** ([`N8N/workflows/netspot_notifications_workflow.json`](file:///home/crispim/Documentos/netspot/N8N/workflows/netspot_notifications_workflow.json)):
  Implementada a função `function esc(v)` no nó `"Format HTML Message"` para sanitizar caracteres especiais (`<`, `>`, `&`) em todos os campos dinâmicos interpolados, extinguindo falhas de entrega na API do Telegram (`parse_mode: "HTML"`).
* **Sincronização Dinâmica do Histórico de Diálogo**:
  O script [`scripts/backup_chat.py`](file:///home/crispim/Documentos/netspot/scripts/backup_chat.py) foi refatorado para localizar dinamicamente a sessão interativa principal mais recente do agente de IA, mantendo o histórico de engenharia seguro e protegido localmente dentro de `.agents/historico_chat/` (ignorado no versionamento público).
* **Ajuste de Timeouts do Nginx**:
  Em [`Frontend/nginx.conf`](file:///home/crispim/Documentos/netspot/Frontend/nginx.conf), os parâmetros `proxy_read_timeout` e `proxy_send_timeout` foram estendidos de `60s` para `130s`, acomodando com folga o teto de `120s` das varreduras de sub-redes `/20`.

---

### 5. Laboratórios de Emulação Kathará
* **Laboratório de Alta Densidade (126 Hosts Emulados)**:
  Inclusão do cenário experimental completo em [`Teste - Kathará/Lab-126hosts`](file:///home/crispim/Documentos/netspot/Teste%20-%20Kathar%C3%A1/Lab-126hosts) composto por 126 containers Linux reais conectados via interfaces `veth` a 4 roteadores de borda, 3 servidores BIND9 com failover e centenas de serviços de aplicação, banco e proxy.
* **Ativação Automática de Agentes SNMP em Roteadores**:
  Em [`Teste - Kathará/lab.conf`](file:///home/crispim/Documentos/netspot/Teste%20-%20Kathar%C3%A1/lab.conf), os roteadores `router_core`, `router_lab1`, `router_lab2` e `router_lab3` agora executam automaticamente `./setup_snmp_linux.sh` no boot, viabilizando a coleta de tráfego de interfaces e métricas de sistema das portas de gateway.
* **Zonas BIND9 Diretas e Reversas Completas**:
  Configuração e validação de todas as zonas diretas (`db.lab.local`) e zonas reversas (`db.10.0.1`, `db.10.0.2`, `db.10.0.3`) em `dns_server1` e `dns_server2`, permitindo 100% de sucesso na resolução direta e reversa (PTR) de todos os endereços do laboratório.
* **Inicialização Rápida de Daemons SNMP**:
  Scripts de provisionamento SNMP atualizados para verificar a presença de binários pré-instalados (`command -v snmpd`), iniciando os serviços em menos de 0.1s e eliminando tentativas de download apt-get em ambientes sem internet.

---

### 6. Qualidade de Software e Evidências Experimentais
* **86 Testes Automatizados no Pytest (100% de Aprovação em ~7.2s)**:
  - `Backend/tests/test_audit_regressions.py` (42 testes assíncronos cobrindo todas as fases da auditoria, segurança, concorrência e integridade documental);
  - `Backend/tests/test_alert_logic.py` (7 cenários críticos de incidentes, histerese e recuperação);
  - `Backend/tests/test_metrics.py` (cálculo de SLA com união de intervalos, Jitter RFC 3550, regressão linear OLS e Health Score sub-milissegundo);
  - `Backend/tests/test_self_healing.py` (máquina de estados do Circuit Breaker e reconexão a frio);
  - `Backend/tests/test_checker.py`, `test_snmp.py`, `test_retention.py`, `test_models_schemas.py` e `test_api_routes.py`.
* **Smoke Test Standalone de Incidentes**:
  Script [`Backend/tests/alert_logic_checklist.py`](file:///home/crispim/Documentos/netspot/Backend/tests/alert_logic_checklist.py) com 7/7 validações bem-sucedidas.
* **Validação Estática Frontend**:
  Sintaxe validada com `node --check` em `app.js`, `incidents.js` e `chart-theme.js`, além de teste automatizado de alternância de paletas de cor (`scripts/test_chart_theme.js`).

---

## 📜 Histórico de Commits Integrados na Versão 1.1.0

A tabela a seguir rastreia os commits que compõem as melhorias incorporadas a partir da release `v1.0.0`:

| Hash | Escopo / Módulo | Mensagem do Commit |
| :--- | :--- | :--- |
| `895cb00` | `chore` | remove arquivos de agente do versionamento |
| `acd76a8` | `feat` | otimiza monitoramento para 126 hosts, adiciona Lab-126hosts e organiza docs |
| `8efaf6a` | `fix(core)` | correcoes de auditoria de seguranca, resiliencia e metricas de monitoramento |
| `383bcfc` | `fix(frontend)` | auditar componentes e otimizar descrições de formulários |
| `6be4d74` | `fix(ui)` | restaurar icone classico de ocultar senha e resumir descricoes no dashboard |
| `42a6dbb` | `feat(ui)` | diferenciar botoes de Conta e Incidentes na barra superior e sincronizar estados do icone de senha |
| `e411f85` | `style(ui)` | padronizar hierarquia e geometria de botoes no frontend |
| `3c69c6a` | `fix(ui)` | restaurar icones em botoes de acao, corrigir proporcao de portas tcp e reforcar affordance visual |
| `ad65b4c` | `style(ui)` | remover callouts descritivos redundantes do modal da lixeira |
| `a6cbfbc` | `fix(ui)` | padronizar botao selecionar todos na aba de lixeira com icones dinamicos e estilo secundario |
| `b4a222d` | `feat(ui)` | otimizar responsividade avancada para telas de celulares e telas enormes 4k ultrawide |
| `b4b77e9` | `fix(ui)` | filtrar protocolos nao monitorados em graficos e manter botoes sequenciais no desktop |
| `c4abc57` | `feat(discovery)`| calibrar temporizacao dinamica do nmap por sub-rede contra perdas por arp a frio |
| `2a3f7f6` | `fix(backend)` | corrigir bloqueio de senha, bcrypt 72b, must_change_password, health 0ms e anti-flapping (Fase 1 Auditoria) |
| `cb536d5` | `fix(frontend)`| corrige XSS inline, SNMP dinamico, N+1 em loadLastResult, CSS dark e timeout Nginx (Fase 2 Auditoria) |
| `16fec26` | `fix(infra)` | align compose healthchecks, sanitize n8n html, dynamic chat backup and kathara dns/snmp (Fase 3 Auditoria) |
| `29c9d09` | `docs` | align README, funcionalidades, kathara and regression suite with 86 tests (Fase 4 Auditoria) |
| `7d07183` | `docs` | adicionar release notes v1.1.0 e v1.0.0 e atualizar README |

---

## 🚀 Como Executar e Validar a Versão 1.1.0

```bash
# 1. Clonar o repositório ou obter a versão estável
git clone https://github.com/ronaldocrispimsg/netspot.git
cd netspot

# 2. Configurar as variáveis de ambiente a partir do exemplo seguro
cp .env.example .env

# 3. Inicializar os containers integrados em segundo plano
docker compose up -d --build
```

### Endereços Operacionais:
* **Dashboard do Operador (NOC)**: [http://localhost:8080](http://localhost:8080)
* **Documentação Interativa da API (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **Diagnóstico de Integridade da Aplicação**: [http://localhost:8000/healthz](http://localhost:8000/healthz)
* **Painel RabbitMQ Management**: [http://localhost:15672](http://localhost:15672)
* **Editor de Fluxos n8n**: [http://localhost:5678](http://localhost:5678)

---

## ⚖️ Licenciamento

O **NetSpot** é software livre distribuído sob os termos da licença **GNU General Public License v3.0 (GPL-3.0)**. Consulte o arquivo [`LICENSE`](file:///home/crispim/Documentos/netspot/LICENSE) para mais detalhes.

---

**Autor**: Ronaldo Crispim  
**Orientação / Instituição**: Sistemas de Informação — Instituto Federal do Norte de Minas Gerais (IFNMG — Campus Januária)  
**Ano**: 2026
