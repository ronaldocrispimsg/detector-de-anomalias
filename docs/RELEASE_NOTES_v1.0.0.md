# NetSpot v1.0.0 — Versao Oficial de Defesa de TCC (NOC Lite)

Lancamento oficial da versao v1.0.0 do NetSpot, sistema de Network Operations Center (NOC Lite) desenvolvido como Trabalho de Conclusao de Curso (TCC) em Sistemas de Informacao no Instituto Federal do Norte de Minas Gerais (IFNMG) — Campus Januaria.

O NetSpot foi concebido para atender as demandas operacionais de pequenas e medias empresas (PMEs), instituicoes educacionais e salas de controle que necessitam de monitoramento proativo de ativos de rede, resiliencia com autocura (Self-Healing) e visualizacao ergonomica sem a sobrecarga computacional de ferramentas corporativas tradicionais.

---

## Principais Recursos e Modulos da Versao 1.0.0

### 1. Frontend SPA Moderno, Ergonomico e Acessivel (WCAG 2.1 AA)
* **Arquitetura de Flip Cards 3D (3 Faces por Dispositivo)**:
  * **Face 1 (Operacional)**: Conectividade em tempo real, pontuacao composta de saude (Health Score 0–100%), tendencia preditiva de latencia e diagnostico imediato de Causa Provavel.
  * **Face 2 (Qualidade de Rede)**: SLAs individuais por protocolo (Ping, TCP, HTTP), calculo estatistico de Jitter (RFC 3550) e inventario de portas abertas.
  * **Face 3 (Hardware e Telemetria)**: Metricas de processador (CPU %), memoria fisica (RAM %), utilizacao de disco e contadores de trafego de rede (Bps).
  * **Usabilidade e Previsibilidade**: Indicadores visuais de face (1/3, 2/3, 3/3) e tooltips descritivos nas setas de navegacao.
* **Acessibilidade Digital Inclusiva (WCAG 2.1 AA)**:
  * Taxa de contraste de texto de 5.6:1 sobre fundos claros (superando a exigencia minima de 4.5:1 do W3C);
  * Anel visual de foco inteligente (:focus-visible) para navegacao universal via teclado;
  * Mecanismo de Focus Trap (aprisionamento e restauracao de foco em modais via Tab e Escape);
  * Rotulos semanticos e atributos ARIA (aria-modal, aria-labelledby, role="dialog").
* **Operacao Offline-First**: Zero dependencia de conexoes externas ou CDNs de terceiros — fontes locais e Chart.js UMD embutidos para operacao continua em redes isoladas ou DMZs.

### 2. Resiliencia Operacional, Autocura e Desacoplamento Assincrono
* **Padrao Circuit Breaker**: Suspensao progressiva e backoff exponencial de sondagens contra nos inoperantes para eliminar tempestades de pacotes (storm effect).
* **Mensageria Desacoplada (RabbitMQ)**: Barramento assincrono com filas persistentes duraveis, canal de eventos e Dead Letter Queue (netspot.dlq) para retencao segura de alertas sem bloquear o ciclo do coletor.
* **Orquestracao e Notificacoes (n8n + Telegram)**: Despacho de alertas em menos de 5 segundos com supressao ativa contra oscilacoes repetitivas de estado (Anti-Flapping).
* **Recuperacao Automatica de Banco de Dados**: Pool dinamico do SQLAlchemy com pool_pre_ping=True e rotina de autocura com reconexao a frio.
* **Politica de Retencao Continua**: Expurgo automatico de metricas e historicos com mais de 7 dias (parametrizavel via .env).

### 3. Coleta Multi-Protocolo e Motor SNMP Multivendor
* **Sondagens Ativas**: ICMP Ping concorrente com protecao contra processos zumbis, checagem de sockets TCP, testes de codigo de status HTTP/HTTPS (200 OK) e resolucao DNS.
* **Agente SNMP Nativo Multiplataforma**:
  * Compatibilidade universal com Linux (UCD-SNMP), Windows (HOST-RESOURCES-MIB), switches e roteadores Cisco, Mikrotik, Huawei e Fortinet;
  * Normalizacao automatica de memoria fisica e selecao inteligente do volume de disco principal;
  * Salvaguarda estrita contra loops infinitos em caminhamento MIB (teto de 500 iteracoes);
  * Postura defensiva (Security by Default) com community padrao netspot e rejeicao da comunidade vulneravel public.

### 4. Heuristica Especialista de Causa Provavel (Fast-Path OSI)
* Motor deterministico baseado em regras auditaveis que correlaciona camadas do modelo OSI:
  * Identificacao de regras de firewall corporativo (ICMP descartado mas portas de aplicacao ativas);
  * Sobrecarga de hardware local (CPU > 90% ou saturacao de disco);
  * Degradacao por variacao de trafego (Jitter > 80 ms);
  * Falha na resolucao de nomes de dominio (DNS inoperante).

---

## Qualidade de Software e Evidencias Experimentais

* **100% de Aprovacao na Suite de Testes Automatizados**: 86 testes assincronos no Pytest cobrindo integridade de modelos, rotas autenticadas da API, autocura, metricas estatisticas, seguranca frontend/backend e politicas de retencao.
* **Validacao em Laboratorio Emulado (Kathara)**: Topologias academicas e corporativas de 40 a 126 nos heterogeneos, 4 sub-redes roteadas e injecao controlada de falhas de latencia e perda de pacotes.
* **Validacao em Rede Fisica Real**: Testado em ambiente de producao no campus do IFNMG Januaria.

---

## Como Executar a Versao 1.0.0

A execucao e 100% conteinerizada e padronizada via Docker Compose:

```bash
# 1. Clone o repositorio
git clone https://github.com/ronaldocrispimsg/netspot.git
cd netspot

# 2. Configure as variaveis de ambiente
cp .env.example .env

# 3. Inicialize os servicos em background
docker compose up -d --build
```

### Portas e Enderecos de Acesso:
* Dashboard do Operador (NOC): http://localhost:8080
* Documentacao Interativa da API (Swagger): http://localhost:8000/docs
* Diagnostico de Saude da Aplicacao: http://localhost:8000/healthz
* Painel RabbitMQ Management: http://localhost:15672
* Editor de Fluxos n8n: http://localhost:5678

---

## Licenciamento

O NetSpot e software livre distribuido sob os termos da licenca GNU General Public License v3.0 (GPL-3.0).
Consulte o arquivo LICENSE para mais detalhes.

---

Autor: Ronaldo Crispim  
Orientacao / Instituicao: Sistemas de Informacao — Instituto Federal do Norte de Minas Gerais (IFNMG)  
Ano: 2026
