# Guia Definitivo de Defesa e Perguntas da Banca Examinadora — NetSpot

Este documento foi estruturado para apoiar Ronaldo Crispim na preparação minuciosa para a defesa pública do Trabalho de Conclusão de Curso (TCC) em Sistemas de Informação no IFNMG — Campus Januária.

O objetivo deste guia não é fornecer respostas decoradas, mas sim fundamentar e articular cada decisão técnica e arquitetural tomada no projeto, mapeando rigorosamente:
1. **Onde está a base teórica no texto da monografia** ([`Escrita_TCC/Escrita_latex/TCC - NetSpot.tex`](file:///home/crispim/Documentos/netspot/Escrita_TCC/Escrita_latex/TCC%20-%20NetSpot.tex));
2. **Onde estão as evidências comprovadas no código-fonte do repositório**;
3. **Quais argumentos de engenharia de software, redes e sistemas você deve articular diante dos examinadores**.

---

## Sumário das Perguntas por Categoria

- [Categoria 1: Interface, UI/UX, Acessibilidade e Escolhas do Frontend](#categoria-1-interface-uiux-acessibilidade-e-escolhas-do-frontend)
  - [1.1: Escolha de Vanilla HTML/CSS/JS vs Frameworks (React, Vue, Next.js)](#pergunta-11-por-que-você-optou-por-html5-css-vanilla-e-javascript-puro-no-frontend-em-vez-de-frameworks-consolidados-de-mercado-como-react-vue-ou-nextjs)
  - [1.2: Conformidade com Acessibilidade Digital (WCAG 2.1 AA) na Prática](#pergunta-12-como-o-netspot-atende-aos-requisitos-de-acessibilidade-digital-wcag-o-que-foi-implementado-na-prática)
  - [1.3: Arquitetura de Flip Cards 3D (3 Faces) vs Densidade e Escala](#pergunta-13-por-que-você-utilizou-a-arquitetura-de-cards-3d-com-3-faces-como-isso-impacta-a-usabilidade-quando-há-dezenas-de-hosts-na-tela)
  - [1.4: Operação Offline-First em Redes Isoladas e DMZs](#pergunta-14-o-frontend-do-netspot-funciona-em-redes-100-isoladas-offline-first-sem-acesso-à-internet)
  - [1.5: Presença de Bootstrap/AdminLTE no Repositório vs CSS Customizado](#pergunta-15-por-que-existem-arquivos-do-bootstrap-e-adminlte-na-pasta-vendor-mas-o-sistema-utiliza-um-css-próprio)
  - [1.6: Gerenciamento de Estado Reativo na SPA sem Redux/Zustand](#pergunta-16-como-o-frontend-gerencia-o-estado-e-atualiza-a-interface-sem-uma-biblioteca-de-gerenciamento-de-estado)
  - [1.7: Sobrecarga Visual com 126 Hosts e Tabela de Operação NOC](#pergunta-17-como-o-sistema-lida-com-a-sobrecarga-visual-information-overload-ao-monitorar-126-hosts-simultâneos-no-frontend-o-que-é-o-modo-tabela-noc-e-a-navegação-por-pílulas-segmentadas)
  - [1.8: Alternância de Visibilidade de Senha (Toggle), Especificidade CSS e Acessibilidade](#pergunta-18-como-foi-implementada-a-funcionalidade-de-alternância-de-visibilidade-de-senha-password-visibility-toggle-e-quais-cuidados-de-especificidade-css-e-acessibilidade-foram-tomados)
  - [1.9: Prevenção de Layout Shift (CLS), Skeletons Realistas e Modais com Rodapé Aderente](#pergunta-19-como-o-netspot-previne-o-layout-shift-cls-durante-o-carregamento-assíncrono-dos-hosts-e-como-foi-tratada-a-ergonomia-de-modais-extensos)
  - [1.10: Acessibilidade em Gráficos de Telemetria (Canvas/WAI-ARIA) e Ergonomia Touch (44x44px)](#pergunta-110-como-o-netspot-atende-à-acessibilidade-em-gráficos-dinâmicos-de-telemetria-canvas-e-à-ergonomia-de-alvos-de-toque-em-telas-móveistouch-sem-poluir-a-interface-de-monitoramento-noc)
  - [1.11: Separação de Módulos (login.js vs app.js), Consistência de Tokens e Zero Estilos Inline](#pergunta-111-por-que-você-isolou-a-lógica-de-autenticação-em-um-módulo-leve-loginjs-e-eliminou-estilos-inline-em-favor-de-tokens-semânticos-e-reserva-de-espaço-aspect-ratio)
- [Categoria 2: Arquitetura, Engenharia de Software e Padrões de Projeto](#categoria-2-arquitetura-engenharia-de-software-e-padrões-de-projeto)
  - [2.1: Aplicação dos Princípios da Clean Architecture](#pergunta-21-o-netspot-segue-a-clean-architecture-arquitetura-limpa-onde-estão-representadas-as-camadas-no-código)
  - [2.2: Desacoplamento Assíncrono com RabbitMQ e n8n vs Notificação Direta](#pergunta-22-qual-é-o-papel-do-rabbitmq-e-do-n8n-na-arquitetura-por-que-o-backend-não-envia-a-notificação-do-telegram-diretamente)
  - [2.3: Autocura (Self-Healing), Circuit Breaker e Retenção](#pergunta-23-como-funciona-o-mecanismo-de-autocura-self-healing-e-o-circuit-breaker-do-netspot)
  - [2.4: Escolha do FastAPI, AsyncIO e Event Loop Concorrente](#pergunta-24-por-que-você-escolheu-o-fastapi-em-vez-de-frameworks-tradicionais-como-django-ou-flask)
  - [2.5: Banco Relacional PostgreSQL vs Bancos de Séries Temporais (TSDB)](#pergunta-25-por-que-utilizar-o-postgresql-em-vez-de-um-banco-de-séries-temporais-tsdb-como-influxdb-ou-prometheus)
  - [2.6: Postura de Segurança, Gestão de Segredos e Autenticação JWT](#pergunta-26-qual-é-a-política-de-segurança-e-gestão-de-credenciais-adotada-no-sistema)
  - [2.7: Escalabilidade para 126 Hosts, Paralelismo em Duas Camadas e Concorrência In-Flight](#pergunta-27-como-o-sistema-escala-e-garante-o-ciclo-de-10-segundos-ao-monitorar-126-hosts-simultâneos-como-você-evitou-checagens-concorrentes-duplicadas)
  - [2.8: Dimensionamento do Pool do PostgreSQL e Dead Letter Queue (DLQ) no RabbitMQ](#pergunta-28-como-foi-dimensionado-o-pool-de-conexões-do-postgresql-e-como-o-sistema-trata-mensagens-corrompidas-no-rabbitmq-dead-letter-queue)
  - [2.9: Gestão de Sessão, Expiração do JWT e Desconexão Automática no Frontend](#pergunta-29-como-é-gerenciado-o-ciclo-de-vida-da-sessão-do-operador-no-frontend-e-backend-o-usuário-é-desconectado-automaticamente-após-determinado-tempo-por-que-essa-abordagem-foi-escolhida)
- [Categoria 3: Métricas de Rede, Causa Provável e Motor SNMP](#categoria-3-métricas-de-rede-causa-provável-e-motor-snmp)
  - [3.1: Formulação Matemática do Score de Saúde e SLA Contínuo](#pergunta-31-como-é-calculado-o-score-de-saúde-health-score-e-a-disponibilidade-de-um-host-qual-é-a-fórmula-matemática)
  - [3.2: Motor de Inferência de Causa Provável: Heurística Determinística vs IA](#pergunta-32-como-o-algoritmo-de-causa-provável-probable-cause-funciona-ele-usa-inteligência-artificial-ou-lógica-heurística-determinística)
  - [3.3: Segurança Operacional SNMP: Community Customizada vs 'public'](#pergunta-33-por-que-você-implementou-a-community-snmp-padrão-como-netspot-em-vez-de-usar-public-quais-são-os-cuidados-de-segurança)
  - [3.4: Relevância do Jitter e Latência em Monitoramento NOC](#pergunta-34-como-é-calculado-o-jitter-e-por-que-essa-métrica-é-tão-relevante-em-um-ambiente-de-noc)
  - [3.5: Algoritmo de Descoberta de Rede (Network Discovery) e Mitigação de Tempestades](#pergunta-35-como-funciona-a-descoberta-automática-de-rede-network-discovery-e-como-evitar-sobrecarga)
  - [3.6: Algoritmo de União de Intervalos de Tempo (Interval Merging) para SLA](#pergunta-36-como-o-algoritmo-de-sla-calcula-a-disponibilidade-sem-duplicar-o-tempo-de-parada-quando-há-múltiplos-incidentes-sobrepostos)
  - [3.7: Prevenção de Falsos Positivos de Firewall via Heurística 'service_up_without_icmp'](#pergunta-37-se-uma-empresa-bloquear-o-tráfego-icmp-ping-em-seus-firewalls-como-o-netspot-evita-falsos-alarmes-de-host-offline)
  - [3.8: Rastreamento de DHCP Dinâmico e Cache DNS na Camada 7 vs Limitações do ARP](#pergunta-38-como-o-netspot-rastreia-alterações-de-ip-dinâmico-por-dhcp-sem-utilizar-arp-broadcast-e-sem-perder-o-histórico)
  - [3.9: Análise Preditiva de Degradação via Regressão Linear Simples (OLS)](#pergunta-39-como-o-netspot-prevê-que-um-host-está-para-cair-antes-da-queda-acontecer-qual-a-fundamentação-matemática)
- [Categoria 4: Validação, Testes, Limitações e Trabalhos Futuros](#categoria-4-validação-testes-limitações-e-trabalhos-futuros)
  - [4.1: Validação Empírica: Laboratório Kathará vs Ambiente Real no Campus](#pergunta-41-como-você-validou-que-o-netspot-realmente-funciona-o-que-foi-testado-em-ambiente-simulado-vs-físico)
  - [4.2: Limitações Conhecidas do Projeto e Autocrítica Técnica](#pergunta-42-quais-são-as-principais-limitações-conhecidas-do-netspot-e-o-que-você-faria-de-diferente-hoje)
  - [4.3: Metodologia da Suíte de Testes Automatizados (86 Testes Backend)](#pergunta-43-qual-é-a-cobertura-da-suíte-de-testes-e-por-que-não-foram-criados-testes-e2e-no-frontend)
  - [4.4: Roteiro de Demonstração Ao Vivo (Live Demo) para a Banca](#pergunta-44-se-a-banca-pedir-uma-demonstração-ao-vivo-qual-é-o-passo-a-passo-para-executar)
  - [4.5: Emulação Fiel Kathará (Veth/Containers) vs Packet Tracer e Máquinas Virtuais](#pergunta-45-por-que-você-escolheu-o-kathará-para-a-validação-empírica-do-tcc-em-vez-de-simuladores-como-o-packet-tracer-ou-vms-pesadas)
  - [4.6: Práticas de Segurança Defensiva OWASP, Lockout de Força Bruta e Loopback Hardening](#pergunta-46-quais-práticas-de-segurança-defensiva-owasp-e-proteção-de-endpoints-foram-aplicadas-no-backend-e-nos-containers)
  - [4.7: Classificação Metodológica da Pesquisa e Paradigma DSR (Design Science Research)](#pergunta-47-como-a-pesquisa-é-classificada-formalmente-em-termos-metodológicos-e-como-o-método-de-wazlawick-2011-e-o-design-science-research-dsr-estruturam-o-desenvolvimento-do-netspot)
  - [4.8: Estratégia Híbrida de Experimentação e Mitigação de Riscos Pedagógicos no IFNMG](#pergunta-48-por-que-adotar-uma-estratégia-de-validação-híbrida-kathará-40126-nós-vs-computadores-físicos-do-ifnmg-januária-e-como-ela-mitiga-riscos-operacionais-na-instituição)
  - [4.9: Rigor e Higienização Bibliográfica: Normas IETF/W3C vs Fontes da Web](#pergunta-49-qual-foi-o-critério-para-a-seleção-e-substituição-de-fontes-bibliográficas-na-monografia-eliminação-de-postsblogs-e-priorização-de-normas-ietfw3c-e-literatura-clássica)
- [Diretrizes de Postura e Articulação Durante a Arguição](#diretrizes-de-postura-e-articulação-durante-a-arguição)

---

## Categoria 1: Interface, UI/UX, Acessibilidade e Escolhas do Frontend

---

### Pergunta 1.1: "Por que você optou por HTML5, CSS Vanilla e JavaScript puro no frontend, em vez de frameworks consolidados de mercado como React, Vue ou Next.js?"

* **Intenção da Banca:** Avaliar se a escolha tecnológica foi consciente e orientada aos requisitos do problema, ou se decorreu de mero improviso.
* **Onde encontrar a base no texto do TCC:**
  - Seção 1.3: *Justificativa* (linhas 300–312).
  - Seção 3.10: *Interface do Usuário (Frontend SPA) e Experiência do Usuário (UX/UI)* (linhas 806–818).
  - Seção 4.4: *Consumo de Recursos e Desempenho* (linhas 998–1030).
* **Evidências no Repositório / Código:**
  - [`Frontend/css/style.css`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css): Folha de estilo centralizada com Design System nativo (`:root`, `.dark-theme`), dispensando compilação (zero dependência de Node, Webpack ou Vite em runtime).
  - [`Frontend/js/app.js`](file:///home/crispim/Documentos/netspot/Frontend/js/app.js): Lógica orientada a eventos assíncronos (`fetch`, manipulação direta do DOM, Chart.js UMD).
  - [`Frontend/Dockerfile`](file:///home/crispim/Documentos/netspot/Frontend/Dockerfile): Imagem Nginx Alpine estática levíssima (< 25 MB).
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Propósito do Sistema:** O NetSpot foi projetado para salas de controle operacional (NOC) e servidores de infraestrutura local, muitas vezes executados em hardware modesto (mini PCs, placas ARM ou Raspberry Pi) e exibidos em monitores dedicados 24/7.
  2. **Sobrecarga de Memória e Ciclo de Vida:** SPAs baseadas em React/Next.js exigem dezenas de megabytes de bundle JavaScript, criam milhares de nós em Virtual DOM e têm risco de vazamento de memória (*memory leak*) em execuções ininterruptas de longa duração.
  3. **Manutenibilidade e Independência de Toolchain:** A abordagem Vanilla garante que o frontend execute em qualquer navegador moderno sem necessidade de etapas de transpilação, vulnerabilidades em pacotes npm transitivos ou quebra por atualizações de dependências.
  4. **Princípios de Engenharia:** Aplicação direta da navalha de Occam e do princípio *YAGNI (You Aren't Gonna Need It)*: a complexidade de um framework reativo completo não traria ganho funcional para o escopo delimitado da ferramenta.

---

### Pergunta 1.2: "Como o NetSpot atende aos requisitos de Acessibilidade Digital (WCAG)? O que foi implementado na prática?"

* **Intenção da Banca:** Verificar se a interface foi pensada para inclusão e conformidade técnica (critérios formais do W3C / WCAG 2.1 AA) ou se é apenas esteticamente agradável.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.10: *Design System Dual e Ergonomia Visual* (linhas 809–818).
  - [`docs/RELATORIO-UIUX.md`](file:///home/crispim/Documentos/netspot/docs/RELATORIO-UIUX.md): Mapeamento completo de conformidade e auditoria por gravidade.
* **Evidências no Repositório / Código:**
  - [`Frontend/css/style.css`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css#L16-L95):
    - Cores de texto secundário (`--text-soft: #475569`, `--text-muted: #59616e`) com taxa de contraste de **5.6:1** sobre fundos claros (ultrapassando o mínimo WCAG AA de 4.5:1);
    - Anel de foco visível inteligente `:focus-visible` com offset de 2px para navegação universal por teclado;
    - Classe `.visually-hidden` para descrição de elementos exclusivamente por leitores de tela;
    - Alvos de toque ampliados para no mínimo 44x44px (`.modal-close-btn`).
  - [`Frontend/js/app.js`](file:///home/crispim/Documentos/netspot/Frontend/js/app.js#L1516-L1538, #L3090-L3125):
    - Funções `openAppModal()` e `closeAppModal()` com foco inicial automático no primeiro campo;
    - **Focus Trap:** aprisionamento de foco via tecla <kbd>Tab</kbd> e <kbd>Shift + Tab</kbd> enquanto o modal está ativo, impedindo navegação cega por trás da tela;
    - Restauração de foco para o botão de origem ao fechar (<kbd>Esc</kbd> ou botão de fechar).
  - [`Frontend/dashboard.html`](file:///home/crispim/Documentos/netspot/Frontend/dashboard.html#L52, #L159-L260):
    - Marco semântico `<main role="main">` e cabeçalho `<h1>`;
    - Atributos ARIA nos diálogos: `role="dialog"`, `aria-modal="true"`, `aria-labelledby`;
    - Tags `<label>` explícitas vinculadas por `for` e `id` em todos os campos de formulário.
* **Roteiro e Argumentos-Chave para a Resposta:**
  - A acessibilidade foi tratada como **requisito não funcional prioritário**, e não como remendo cosmético.
  - O sistema pode ser operado **exclusivamente via teclado** (<kbd>Tab</kbd>, <kbd>Shift + Tab</kbd>, <kbd>Enter</kbd>, <kbd>Escape</kbd>) e com tecnologias assistivas (leitores de tela como NVDA e Orca).

---

### Pergunta 1.3: "Por que você utilizou a arquitetura de Cards 3D com 3 Faces? Como isso impacta a usabilidade quando há dezenas de hosts na tela?"

* **Intenção da Banca:** Explorar a ergonomia da visualização dos hosts, densidade de informação e capacidade de escala visual.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.10.6: *Arquitetura de Flip Cards 3D (3 Faces por Card de Host)* (linhas 855–880).
  - Seção 5: *Considerações Finais e Trabalhos Futuros* (linhas 1031–1060).
* **Evidências no Repositório / Código:**
  - [`Frontend/js/app.js`](file:///home/crispim/Documentos/netspot/Frontend/js/app.js):
    - Face 1: Resumo, saúde, tendência de latência HTTP e causa provável;
    - Face 2: SLA individual por protocolo (Ping, TCP, HTTP), jitter e portas ativas;
    - Face 3: Telemetria SNMP de hardware (CPU, RAM, Disco, Tráfego);
    - Navegação por **Pílulas Segmentadas** (`.face-segmented-control` com `.face-pill` e atributos `role="tab"`), substituindo a antiga navegação sequencial por setas e permitindo salto direto em 1 clique para qualquer face.
  - [`Frontend/css/style.css`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css): Transição suave via transformações CSS 3D (`transform: rotateY()`), com controle de contraste e anel de foco.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Solução para o Desafio da Densidade:** Em sistemas tradicionais (Zabbix, Nagios), telas de detalhes exigem abrir uma nova página ou modais pesados. As 3 faces permitem ao operador inspecionar métricas profundas (SLA, jitter, hardware) sem sair do fluxo operacional principal.
  2. **Acesso Direto em 1 Clique (Pílulas Segmentadas):** Inicialmente utilizavam-se setas sequenciais `<` e `>`, o que exigia dois cliques para ir da Face 1 à Face 3. A evolução para pílulas segmentadas (`[ Resumo ] [ Rede ] [ SNMP ]`) eliminou cliques desnecessários, adicionou semântica de tabs e garantiu visibilidade imediata de qual contexto métrico está em exibição.
  3. **Solução Completa com Modo Dual (Cards vs Tabela NOC):** Para redes pequenas/médias (até 30 hosts), os cards 3D entregam riqueza visual e interativa superior. Para grandes ambientes com 126 hosts (como no teste de estresse do Kathará), foi implementado o modo alternativo **Tabela NOC**, permitindo varredura de alta densidade sem rolagem excessiva.

---

### Pergunta 1.4: "O frontend do NetSpot funciona em redes 100% isoladas (offline-first), sem acesso à internet?"

* **Intenção da Banca:** Averiguar a viabilidade do sistema em redes corporativas fechadas, DMZs restritas ou laboratórios acadêmicos sem rota externa.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.10.1: *Design System Dual e Ergonomia Visual* (linha 817).
  - Seção 4.1: *Laboratório de Simulação Kathará* (linhas 910–935).
* **Evidências no Repositório / Código:**
  - [`Frontend/fonts/open-sans-latin-wght-normal.woff2`](file:///home/crispim/Documentos/netspot/Frontend/fonts/open-sans-latin-wght-normal.woff2): Arquivo binário de fonte local embutido no repositório.
  - [`Frontend/css/style.css:4-10`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css#L4-L10): Declaração `@font-face` local com `font-display: swap`.
  - Scripts vendor em [`Frontend/js/vendor/chart.umd.min.js`](file:///home/crispim/Documentos/netspot/Frontend/js/vendor/chart.umd.min.js): Chart.js distribuído localmente, sem dependência de CDNs externos (Cloudflare, cdnjs).
* **Roteiro e Argumentos-Chave para a Resposta:**
  - O NetSpot foi desenhado para **ambientes isolados**: todas as dependências de runtime (gráficos Chart.js, folha de estilo e fonte tipográfica) residem no próprio container Nginx.
  - Mesmo em cenários sem DNS público ou sem conexão externa (como no laboratório Kathará), a aplicação carrega instantaneamente, eliminando falhas de timeout ou bloqueios de renderização (*FOUT/FOIT*).

---

### Pergunta 1.5: "Por que existem arquivos do Bootstrap e AdminLTE na pasta vendor, mas o sistema utiliza um CSS próprio?"

* **Intenção da Banca:** Avaliar se houve abandono de código, dívida técnica não documentada ou refatoração consciente.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.10: *Interface do Usuário (Frontend SPA)* (linhas 806–815).
* **Evidências no Repositório / Código:**
  - [`Frontend/css/adminlte.min.css`](file:///home/crispim/Documentos/netspot/Frontend/css/adminlte.min.css) e [`Frontend/js/vendor/bootstrap.bundle.min.js`](file:///home/crispim/Documentos/netspot/Frontend/js/vendor/bootstrap.bundle.min.js).
  - [`Frontend/dashboard.html:15-18`](file:///home/crispim/Documentos/netspot/Frontend/dashboard.html#L15-L18): Inclusão apenas de `css/style.css` na tag `<head>`.
* **Roteiro e Argumentos-Chave para a Resposta:**
  - No início da prototipação, considerou-se o uso do AdminLTE v4 com Bootstrap 5.3.3. No entanto, o AdminLTE adicionava mais de 200 KB de estilos genéricos não utilizados e gerava conflitos de layout com as transformações 3D dos cartões de host.
  - Optou-se por construir uma folha de estilo sob medida ([`Frontend/css/style.css`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css)), enxuta e focada na experiência do NOC. Os artefatos na pasta `vendor/` foram mantidos como referência de componentes utilitários (modais/ícones), mas a aplicação final opera de forma 100% independente, resultando em menor tempo de carregamento e controle total sobre o design system.

---

### Pergunta 1.6: "Como o frontend gerencia o estado e atualiza a interface sem uma biblioteca de gerenciamento de estado?"

* **Intenção da Banca:** Entender a arquitetura de dados no lado do cliente e conferir se não há recarregamento excessivo da página inteira.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.10.3: *Comportamento SPA e Atualizações Assíncronas* (linhas 825–840).
* **Evidências no Repositório / Código:**
  - [`Frontend/js/app.js`](file:///home/crispim/Documentos/netspot/Frontend/js/app.js): Objeto global de estado em memória (`hostsData`, `incidentsData`, `metricsCache`), gerenciado por eventos de ciclo de vida.
  - Polling periódico via `setInterval` com chamadas `fetch('/api/hosts')` a cada 10 segundos.
  - Atualização cirúrgica do DOM: apenas os badges, textos e barras de progresso alterados são recalculados, preservando o estado de navegação (se o usuário estava com um modal aberto ou com um card na Face 2, ele não perde a seleção).
* **Roteiro e Argumentos-Chave para a Resposta:**
  - Para o modelo do NetSpot, uma arquitetura baseada em variáveis reativas nativas e manipulação direcionada do DOM oferece excelente desempenho com consumo de CPU/RAM desprezível no cliente.
  - A cada ciclo de telemetria, o backend entrega dados consolidados, e o frontend faz a renderização diferencial dos cards, garantindo fluidez sem oscilações visuais (*screen flicker*).

---

### Pergunta 1.7: "Como o sistema lida com a sobrecarga visual (information overload) ao monitorar 126 hosts simultâneos no Frontend? O que é o modo 'Tabela NOC' e a navegação por pílulas segmentadas?"

* **Intenção da Banca:** Avaliar se o candidato compreende ergonomia visual, escalabilidade de interface e o impacto de monitorar centenas de dispositivos em tempo real sem fadiga do operador.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.10: *Interface do Usuário (Frontend SPA) e Experiência do Usuário (UX/UI)* (linhas 806–880).
  - Seção 4.1: *Laboratório de Simulação Kathará com 126 Hosts* (linhas 910–935).
* **Evidências no Repositório / Código:**
  - [`Frontend/dashboard.html`](file:///home/crispim/Documentos/netspot/Frontend/dashboard.html): Alternador de visão `.view-mode-toggle` (`#viewCardsBtn` vs `#viewTableBtn`), badge de contagem dinâmica `#hostsCountBadge` e contêiner `#hostsTableView` com estrutura semântica `table.noc-table`.
  - [`Frontend/js/app.js`](file:///home/crispim/Documentos/netspot/Frontend/js/app.js):
    - `setViewMode(mode)`: Alternância instantânea entre Cards 3D e Tabela de Operação NOC com persistência em `localStorage`;
    - `buildNocTableRowHTML(h)` e `renderNocTable(hosts)`: Renderização de alta densidade reunindo Status (dot + label), Dispositivo (com botão de cópia de IP), Barra de Saúde, SLA contínuo, Ping, Check Web, Portas TCP e Causa Provável;
    - `focusHostCard(hostName)`: Ação que permite ao operador clicar em qualquer linha da tabela e ser transportado diretamente para o Card 3D correspondente, com scroll suave centralizado e efeito de pulso luminoso (`card-highlight-pulse`);
    - `filterHosts()`: Filtragem unificada e simultânea de cards e linhas de tabela, com atualização do badge (`"Exibindo X de Y hosts"`).
  - [`Frontend/css/style.css`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css): Listra vertical de estado na borda esquerda da linha (verde/amarelo/vermelho), cabeçalho fixo (*sticky header*) na rolagem e contraste balanceado em modo claro e escuro.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **O Paradigma Dual View (Grade vs Tabela):** Cards 3D são ideais para análise analítica de poucos nós e apresentações em telões executivos; contudo, para uma sala de NOC monitorando 126 computadores simultâneos, a rolagem de dezenas de cards causa cansaço visual (*scroll fatigue*). A Tabela de Operação NOC resolve isso condensando informações vitais em linhas compactas com tipografia monoespaçada.
  2. **Interconexão Fluida:** O operador não precisa escolher permanentemente um modo. Ele pode utilizar a Tabela NOC para triagem rápida e, ao avistar um nó degradado, acionar "Focar no Card 3D" para abrir todas as telemetrias e gráficos detalhados do dispositivo.
  3. **Zero Dependência:** Toda essa interatividade de alta densidade foi concebida com CSS Grid, Flexbox e manipulação Vanilla do DOM, sem exigir bibliotecas de tabelas pesadas (como DataTables ou TanStack Table).

---

### Pergunta 1.8: "Como foi implementada a funcionalidade de alternância de visibilidade de senha (Password Visibility Toggle) e quais cuidados de especificidade CSS e acessibilidade foram tomados?"

* **Intenção da Banca:** Testar boas práticas em formulários de segurança, usabilidade em autenticação e domínio de especificidade em CSS moderno.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.10.1: *Design System Dual e Ergonomia Visual*.
  - Seção 3.10.2: *Fluxos de Autenticação e Primeiro Acesso*.
* **Evidências no Repositório / Código:**
  - [`Frontend/login.html`](file:///home/crispim/Documentos/netspot/Frontend/login.html) e [`Frontend/dashboard.html`](file:///home/crispim/Documentos/netspot/Frontend/dashboard.html): Wrappers flexíveis `.password-input-wrap` com botões `.password-toggle-btn` e ícones SVG inline (`eye-open` e `eye-closed`).
  - [`Frontend/js/incidents.js`](file:///home/crispim/Documentos/netspot/Frontend/js/incidents.js): Função `togglePasswordVisibility(inputId, btn)` que alterna dinamicamente o atributo `type` entre `"password"` e `"text"`, atualiza os ícones SVG e altera o `title` e `aria-label` entre `"Mostrar senha"` e `"Ocultar senha"`.
  - [`Frontend/css/style.css`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css): Regras de posicionamento absoluto (`right: 8px; top: 50%; transform: translateY(-50%)`) com proteção de especificidade via seletores direcionados (`.login-box button[type="submit"]`).
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Redução de Erros em Senhas Fortes:** No primeiro acesso ou alteração de credenciais corporativas, senhas complexas sofrem alta taxa de erro de digitação. Permitir a inspeção visual temporária reduz o bloqueio de contas por força bruta acidental.
  2. **Isolamento de Especificidade CSS:** Formulários com botões estilizados globalmente (ex.: `.login-box button`) podem acidentalmente forçar estilos de bloco (`width: 100%`, `background: blue`) sobre botões utilitários inline. A solução técnica consistiu em especificar `.login-box button[type="submit"]` e isolar o botão de toggle com dimensões fixas (32x32px), fundo transparente e remoção de margens parasitas.
  3. **Acessibilidade Assistiva:** O botão possui `aria-label` dinâmico e suporte completo a acionamento por teclado (<kbd>Enter</kbd> e <kbd>Espaço</kbd>), garantindo que usuários com leitores de tela compreendam o estado da revelação.

---

### Pergunta 1.9: "Como o NetSpot previne o 'Layout Shift' (CLS) durante o carregamento assíncrono dos hosts e como foi tratada a ergonomia de modais extensos?"

* **Intenção da Banca:** Verificar o domínio de Core Web Vitals (Cumulative Layout Shift - CLS), percepção de performance do usuário (*Perceived Performance*) e usabilidade em interfaces ricas com formulários longos.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.10: *Interface do Usuário (Frontend SPA) e Experiência do Usuário (UX/UI)* (linhas 806–850).
  - Seção 4.4: *Consumo de Recursos e Desempenho*.
* **Evidências no Repositório / Código:**
  - [`Frontend/js/app.js`](file:///home/crispim/Documentos/netspot/Frontend/js/app.js):
    - `buildSkeletonCardsHTML()` e `buildSkeletonTableRowsHTML()`: Durante o fetch assíncrono inicial de `/hosts/list`, o sistema injeta réplicas vazias realistas (cabeçalho, grade de metadados, abas e barras de progresso simuladas) com atributo `aria-busy="true"`.
  - [`Frontend/css/style.css`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css):
    - Animação vetorial `@keyframes skeleton-shimmer` sobre gradiente linear de duas paradas, reproduzindo o padrão de plataformas modernas (como GitHub e Datadog);
    - `.modal-actions` fixado com **rodapé aderente (*sticky action footer*)** (`position: sticky; bottom: -24px; z-index: 10; box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.04)`), garantindo que botões cruciais ("Salvar alterações", "Cancelar", "Mover para lixeira") permaneçam permanentemente visíveis ao operador, mesmo quando o modal exibe dezenas de portas TCP configuradas ou listas volumosas de hosts.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Eliminação do Cumulative Layout Shift (CLS):** Em conexões lentas ou com centenas de hosts, exibir mensagens secas como "Carregando..." faz a tela pular de repente quando a resposta da API chega, causando frustração e cliques acidentais. Os skeletons realistas reservam o espaço exato na geometria da página antes da renderização dos dados reais.
  2. **Ergonomia em Formulários Longos:** Em modais com rolagem interna vertical (`max-height: 88vh; overflow-y: auto`), rolar repetidamente até o rodapé para clicar em "Salvar" é uma falha clássica de UX. O rodapé aderente (*sticky footer*) mantém os botões de ação sempre ao alcance imediato do operador, prevenindo abandono de formulário e perda de contexto.

---

### Pergunta 1.10: "Como o NetSpot atende à acessibilidade em gráficos dinâmicos de telemetria (<canvas>) e à ergonomia de alvos de toque em telas móveis/touch sem poluir a interface de monitoramento NOC?"

* **Intenção da Banca:** Avaliar conformidade avançada com normas internacionais de acessibilidade (WCAG 2.1/2.2 AA) em elementos ricos de tela, foco assistivo (WAI-ARIA) e ergonomia física de toque (*Target Size*) sem sacrificar a densidade visual exigida por salas de operações.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.10: *Interface do Usuário (Frontend SPA) e Experiência do Usuário (UX/UI)* (linhas 806–850).
  - Seção 3.10.1: *Design System Dual e Ergonomia Visual*.
* **Evidências no Repositório / Código:**
  - [`Frontend/js/app.js`](file:///home/crispim/Documentos/netspot/Frontend/js/app.js):
    - Elementos `<canvas>` do Chart.js (SNMP, Latência dos checks e Disponibilidade) gerados com `role="img"`, atributo `aria-label` dinâmico contextualizado com o host (ex.: `"Histórico de latência e ping do host pc1"`) e mensagem de fallback textual em caso de incompatibilidade (WCAG 1.1.1);
    - Abas da lixeira estruturadas com padrão WAI-ARIA Tabs (`role="tab"`, `aria-controls` e `aria-labelledby`);
    - Botões de menu (`#openMenuBtn`), alternância de senha (`.password-toggle-btn`) e alternador de tema (`#themeToggleBtn`) gerenciados reativamente com `aria-expanded` e `aria-pressed`.
  - [`Frontend/css/style.css`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css):
    - Regra `@media (pointer: coarse)`: sob telas touch (smartphones e tablets), botões operacionais compactos (`.host-delete-btn` de 26px, `.noc-action-btn` de 28px, `.copy-addr-btn` e `.password-toggle-btn` de 32px) recebem pseudo-elemento invisível `::after` com dimensões mínimas de **44x44px** (WCAG 2.1 SC 2.5.5), mantendo a área física de toque generosa sem inflar o layout geométrico em desktops com ponteiro fino (`pointer: fine`).
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Superação da Opacidade do Canvas:** Elementos `<canvas>` são nativamente bitmaps opacos na Árvore de Acessibilidade (*Accessibility Tree*). A introdução de `role="img"` combinada com descrições dinâmicas estruturadas permite que softwares de tecnologia assistiva (NVDA, Orca, VoiceOver) anunciem com precisão o contexto de cada gráfico de telemetria sem exigir intervenção visual.
  2. **Ergonomia Tátil sem Degradação de Densidade:** Em um painel de NOC com dezenas de hosts, botões de 44px físicos em monitores desktop reduziriam dramaticamente o número de dispositivos visíveis simultaneamente. A técnica de pseudo-elemento `::after` ativado condicionalmente por media query de hardware (`pointer: coarse`) resolve com elegância o dilema clássico da engenharia de software entre alta densidade visual desktop e usabilidade tátil mobile.
  3. **Comunicação de Estado Reativo:** Componentes de alternância que não expõem `aria-pressed` ou `aria-expanded` forçam o usuário cego a deduzir o estado da interface. O NetSpot sincroniza programaticamente esses atributos a cada disparo de evento no DOM.

---

### Pergunta 1.11: "Por que você isolou a lógica de autenticação em um módulo leve (`login.js`) e eliminou estilos inline em favor de tokens semânticos e reserva de espaço (aspect-ratio)?"

* **Intenção da Banca:** Questionar a maturidade na gestão de assets (*Asset Bundling*), desempenho de carregamento inicial (*First Contentful Paint* - FCP), prevenção de deslocamento de layout (CLS) e separação estrita de camadas de apresentação (CSS limpo sem código espaguete).
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.10.2: *Fluxos de Autenticação e Primeiro Acesso*.
  - Seção 4.4: *Consumo de Recursos e Desempenho*.
* **Evidências no Repositório / Código:**
  - [`Frontend/js/login.js`](file:///home/crispim/Documentos/netspot/Frontend/js/login.js): Módulo desacoplado de apenas 255 linhas (~4 KB) contendo exclusivamente autenticação, primeiro acesso e modais de troca de senha.
  - [`Frontend/login.html`](file:///home/crispim/Documentos/netspot/Frontend/login.html): Deixou de importar os 172 KB (4.400+ linhas) do `app.js` (que continha Chart.js, sockets e polling do NOC).
  - [`Frontend/css/style.css`](file:///home/crispim/Documentos/netspot/Frontend/css/style.css):
    - Classes utilitárias semânticas (`.noc-th-*`, `.discovery-helper-full`, `.dhcp-helper-modal`, `.pwd-helper-modal`, `.confirm-modal-subnote`) substituindo 100% dos estilos inline antes presentes nas tags HTML;
    - Regras de `aspect-ratio: 1762 / 909` e `1726 / 902` nos logotipos em conjunto com atributos `width` e `height` no markup;
    - Migração de regras globais de inputs para tokens de design (`var(--line)`, `var(--bg-panel)`, `var(--text-main)`, `var(--primary)`, `var(--focus-ring)`).
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Otimização Crítica do FCP e Consumo de Dados:** Usuários em telas de login não autenticadas não devem pagar o custo de download, parsing e compilação de código de telemetria complexa que nem sequer têm permissão para acessar. A divisão física do script reduziu a carga de rede da página inicial em **mais de 95%**.
  2. **Prevenção Estrita de Layout Shift (CLS = 0):** Imagens sem proporção e dimensões declaradas provocam quebras visuais e recalculação forçada de estilo (*Reflow*) à medida que o binário é carregado. Declarar o `aspect-ratio` nativo instrui o motor do navegador a reservar o espaço retangular exato em microssegundos durante a fase de montagem da árvore de renderização.
  3. **Manutenibilidade e Independência de Tema:** Estilos inline (`style="..."`) possuem especificidade destrutiva, impedem a sobreposição limpa por classes de tema (`.dark-theme`) e violam o princípio de separação de responsabilidades. Centralizar todas as dimensões e cores no CSS sob variáveis nativas do Design System assegura consistência visual e facilidade de manutenção a longo prazo.

---

## Categoria 2: Arquitetura, Engenharia de Software e Padrões de Projeto

---

### Pergunta 2.1: "O NetSpot segue a Clean Architecture (Arquitetura Limpa)? Onde estão representadas as camadas no código?"

* **Intenção da Banca:** Testar seu domínio sobre engenharia de software e padrões arquiteturais modernos.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3: *Arquitetura e Implementação do NetSpot* (linhas 360–379).
  - Seção 3.1: *Modelagem de Dados e Diagrama de Classes do Projeto* (linhas 380–465).
  - Figura 4 da monografia: Diagrama de Classes e Arquitetura.
* **Evidências no Repositório / Código:**
  1. **Camada de Entidades (Núcleo):** [`Backend/models.py`](file:///home/crispim/Documentos/netspot/Backend/models.py) (`Host`, `CheckResult`, `Alert`, `SNMPMetric`, `Incident`) — representam o domínio do problema de monitoramento sem acoplamento a bibliotecas web.
  2. **Camada de Casos de Uso e Regras de Negócio:** Módulos de orquestração como [`Backend/checker.py`](file:///home/crispim/Documentos/netspot/Backend/checker.py), [`Backend/scheduler.py`](file:///home/crispim/Documentos/netspot/Backend/scheduler.py), [`Backend/services/circuit_breaker.py`](file:///home/crispim/Documentos/netspot/Backend/services/circuit_breaker.py) e [`Backend/services/retention_service.py`](file:///home/crispim/Documentos/netspot/Backend/services/retention_service.py).
  3. **Camada de Adaptadores de Interface:** [`Backend/routes/hosts.py`](file:///home/crispim/Documentos/netspot/Backend/routes/hosts.py) e [`Backend/schemas.py`](file:///home/crispim/Documentos/netspot/Backend/schemas.py) (conversão de JSON e contratos Pydantic para as entidades internas).
  4. **Camada de Frameworks e Drivers (Externa):** FastAPI, SQLAlchemy ([`Backend/database.py`](file:///home/crispim/Documentos/netspot/Backend/database.py)), RabbitMQ ([`Backend/mq_manager.py`](file:///home/crispim/Documentos/netspot/Backend/mq_manager.py)) e Nginx no Frontend.
* **Roteiro e Argumentos-Chave para a Resposta:**
  - A separação de responsabilidades foi rigorosamente mantida: as regras de negócio de monitoramento não dependem de detalhes da interface gráfica ou do canal de entrega de alertas.
  - A estrutura do projeto reflete exatamente a modelagem descrita na monografia, evitando *overengineering* (como excesso de pastas vazias ou abstrações desnecessárias que aumentariam a complexidade sem ganho real).

---

### Pergunta 2.2: "Qual é o papel do RabbitMQ e do n8n na arquitetura? Por que o backend não envia a notificação do Telegram diretamente?"

* **Intenção da Banca:** Avaliar compreensão de sistemas distribuídos, desacoplamento e resiliência a falhas de rede externa.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.4: *Protocolo da Aplicação e Envelope de Eventos do NetSpot* (linhas 503–520).
  - Seção 3.8: *Fluxograma de Decisões e Orquestração de Eventos AMQP* (linhas 784–805).
* **Evidências no Repositório / Código:**
  - [`Backend/mq_manager.py`](file:///home/crispim/Documentos/netspot/Backend/mq_manager.py): Publicação assíncrona com conexão resiliente, canal de eventos e suporte a fallback de entrega.
  - [`N8N/workflows/netspot_notifications_workflow.json`](file:///home/crispim/Documentos/netspot/N8N/workflows/netspot_notifications_workflow.json): Fluxo de orquestração com nó AMQP, formatação de mensagem e despacho para o Telegram.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Desacoplamento e Não-Bloqueio:** O ciclo de monitoramento do NetSpot precisa ser rápido e previsível. Se o backend fizesse requisições HTTP síncronas para a API do Telegram, uma lentidão ou instabilidade no link de internet bloquearia o processo de checagem dos demais hosts da rede.
  2. **Persistência de Fila (Buffer):** Se a conexão com a internet cair no exato momento de um incidente, a mensagem fica armazenada com segurança na fila do RabbitMQ e é entregue assim que o link for restabelecido.
  3. **Extensibilidade Sem Alterar Código:** Utilizando o n8n como consumidor da fila, a equipe de TI pode adicionar novos canais de notificação (Discord, e-mail, Slack, webhook interno) diretamente pelo editor visual do n8n, sem precisar alterar uma única linha de código do backend.

---

### Pergunta 2.3: "Como funciona o mecanismo de autocura (Self-Healing) e o Circuit Breaker do NetSpot?"

* **Intenção da Banca:** Verificar o tratamento de falhas em cascata e degradação suave (*Graceful Degradation*).
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.5: *Mecanismos de Autocura e Resiliência (Self-Healing)* (linhas 617–642).
* **Evidências no Repositório / Código:**
  - [`Backend/services/circuit_breaker.py`](file:///home/crispim/Documentos/netspot/Backend/services/circuit_breaker.py): Implementação do padrão Circuit Breaker (estados `CLOSED`, `OPEN`, `HALF_OPEN`) para evitar sobrecarga em nós inoperantes.
  - [`Backend/scheduler.py`](file:///home/crispim/Documentos/netspot/Backend/scheduler.py): Backoff exponencial em requisições SNMP para hosts sem resposta.
  - [`Backend/services/retention_service.py`](file:///home/crispim/Documentos/netspot/Backend/services/retention_service.py): Purga periódica de dados volumosos para evitar estouro de disco do banco de dados.
* **Roteiro e Argumentos-Chave para a Resposta:**
  - Se um switch ou servidor cai, insistir em dezenas de sondagens consecutivas por segundo esgota recursos do próprio servidor de monitoramento (*storm effect*).
  - O Circuit Breaker detecta falhas repetidas e "abre o circuito", espaçando as próximas checagens até que o host dê sinais de recuperação no estado `HALF_OPEN`.
  - O serviço de retenção limpa registros de checagem e métricas com mais de 7 dias (ou limite parametrizável), garantindo estabilidade contínua sem intervenção manual.

---

### Pergunta 2.4: "Por que você escolheu o FastAPI em vez de frameworks tradicionais como Django ou Flask?"

* **Intenção da Banca:** Avaliar se a escolha do framework backend foi técnica e aderente às características do monitoramento de redes.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.2: *Tecnologias Empregadas no Backend* (linhas 466–490).
* **Evidências no Repositório / Código:**
  - [`Backend/main.py`](file:///home/crispim/Documentos/netspot/Backend/main.py): Aplicação assíncrona baseada em ASGI (Uvicorn).
  - [`Backend/checker.py`](file:///home/crispim/Documentos/netspot/Backend/checker.py): Uso intensivo de `asyncio` para disparar sondagens concorrentes sem bloquear a thread principal.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **I/O Não-Bloqueante Nativo:** O monitoramento de rede é uma tarefa essencialmente dependente de I/O (*I/O-bound* — aguardar resposta de ping, sockets TCP e OIDs SNMP). O FastAPI, construído sobre Starlette e AsyncIO, permite aguardar centenas de respostas simultaneamente com uma única thread.
  2. **Validação de Tipos com Pydantic:** Validação automática de esquemas na entrada da API, gerando documentação OpenAPI/Swagger interativa pronta para auditoria.
  3. **Desempenho Comparado:** Em benchmarks de I/O assíncrono, o FastAPI atinge vazão ordens de grandeza superior a frameworks WSGI síncronos legados como Flask e Django puro.

---

### Pergunta 2.5: "Por que utilizar o PostgreSQL em vez de um banco de séries temporais (TSDB) como InfluxDB ou Prometheus?"

* **Intenção da Banca:** Avaliar se a escolha do banco de dados foi pragmática e se o candidato compreende o ciclo de vida dos dados de monitoramento.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.1: *Modelagem de Dados e Persistência* (linhas 380–430).
  - Seção 3.5.3: *Política de Retenção e Expiração de Séries Históricas* (linhas 635–642).
* **Evidências no Repositório / Código:**
  - [`Backend/models.py`](file:///home/crispim/Documentos/netspot/Backend/models.py): Relacionamentos relacionais íntegros (`Host` 1:N `CheckResult`, 1:N `Incident`, 1:N `Alert`).
  - [`Backend/services/retention_service.py`](file:///home/crispim/Documentos/netspot/Backend/services/retention_service.py): Limpeza periódica de métricas antigas.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Integridade Referencial e Modelo Híbrido:** O NetSpot lida com entidades altamente relacionais (hosts associados a portas, históricos de incidentes vinculados a alertas e usuários com controle de acesso). Um TSDB puro (como InfluxDB) exigiria gerenciar dois bancos de dados simultâneos (um relacional e um temporal).
  2. **Simplicidade Operacional:** Para o porte de redes monitoradas pelo NetSpot (dezenas a centenas de equipamentos), o PostgreSQL atende perfeitamente à volumetria de séries temporais quando associado ao [`Backend/services/retention_service.py`](file:///home/crispim/Documentos/netspot/Backend/services/retention_service.py).
  3. **Trabalho Futuro:** A extensão do Postgres via *TimescaleDB* foi catalogada como evolução natural caso o sistema venha a ser expandido para milhares de dispositivos simultâneos.

---

### Pergunta 2.6: "Qual é a política de segurança e gestão de credenciais adotada no sistema?"

* **Intenção da Banca:** Avaliar a postura de segurança defensiva (*Security by Default*) e a conformidade com as diretrizes do OWASP e da metodologia *Twelve-Factor App*.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.3: *Módulo de Autenticação, Criptografia e Segurança* (linhas 491–502).
  - Seção 1 de [`.agents/MEMORIA.md`](file:///home/crispim/Documentos/netspot/.agents/MEMORIA.md).
* **Evidências no Repositório / Código:**
  - [`docker-compose.yml`](file:///home/crispim/Documentos/netspot/docker-compose.yml): Todas as senhas e segredos são parametrizados via variáveis lidas do `.env`, eliminando senhas literais (*hardcoded*) no versionamento.
  - [`.env.example`](file:///home/crispim/Documentos/netspot/.env.example): Template contendo apenas nomes e valores fictícios, sem expor dados reais.
  - [`Backend/security.py`](file:///home/crispim/Documentos/netspot/Backend/security.py): Hashing de senhas com bcrypt, geração de tokens JWT com expiração configurável e leitura mandatória de `SECRET_KEY`.
* **Roteiro e Argumentos-Chave para a Resposta:**
  - Nenhuma credencial de banco, fila ou autenticação é fixada no código-fonte.
  - Em conformidade com o 3º fator do *Twelve-Factor App (Config)*, todas as variáveis confidenciais são injetadas estritamente pelo ambiente de execução, protegidas pelo `.gitignore`.

---

### Pergunta 2.7: "Como o sistema escala e garante o ciclo de 10 segundos ao monitorar 126 hosts simultâneos? Como você evitou checagens concorrentes duplicadas?"

* **Intenção da Banca:** Avaliar se o sistema realmente suporta concorrência real e alta densidade de monitoramento sem estourar o orçamento temporal de 10 segundos nem sobrecarregar o motor com checagens duplicadas.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.4: *Motor de Monitoramento Contínuo e Agendamento Assíncrono* (linhas 520–580).
  - Seção 4.4: *Consumo de Recursos, Latência e Desempenho em Escala* (linhas 998–1030).
* **Evidências no Repositório / Código:**
  - [`Backend/scheduler.py:435-440`](file:///home/crispim/Documentos/netspot/Backend/scheduler.py#L435-L440): Sondagens intra-host executadas em paralelo via `asyncio.gather(ping_task, tcp_task, http_task)`.
  - [`Backend/mq_manager.py:78`](file:///home/crispim/Documentos/netspot/Backend/mq_manager.py#L78): Controle de vazão inter-host via `prefetch_count=32` no canal AMQP.
  - [`Backend/scheduler.py:858-873`](file:///home/crispim/Documentos/netspot/Backend/scheduler.py#L858-L873): Mecanismo atômico de controle de concorrência com conjunto protegido `_in_flight_hosts` e `asyncio.Lock()`.
  - [`Backend/tests/test_audit_regressions.py`](file:///home/crispim/Documentos/netspot/Backend/tests/test_audit_regressions.py): Testes automatizados `test_parallel_monitoring_126_hosts_under_budget` e `test_process_host_check_in_flight_concurrency_lock`.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Paralelismo em Duas Camadas:**
     - *Camada Intra-Host:* Para cada dispositivo cadastrado, as checagens individuais de ICMP (`ping_host`), portas TCP (`tcp_check`) e HTTP/HTTPS (`http_check`) rodam simultaneamente via `asyncio.gather`. O tempo de sondagem por host é delimitado pela sonda mais demorada (~200ms) em vez de somar sequencialmente os tempos;
     - *Camada Inter-Host:* Com `prefetch_count=32` no RabbitMQ, 32 hosts são processados em paralelo pelos workers assíncronos. Para 126 hosts cadastrados, a rodada se completa em apenas 4 ondas consecutivas ($126 / 32 \approx 4$), consumindo entre 1.0s e 1.5s no total — muito abaixo da margem limite de 10 segundos.
  2. **Eliminação de Contenção de Banco (Row Lock Throttling):** As consultas SNMP UDP são disparadas *antes* de abrir transações de escrita com o PostgreSQL. Isso impede que locks exclusivos de linha (`RowExclusiveLock`) retenham conexões no banco enquanto aguardam pacotes UDP de rede.
  3. **Trava Atômica de Voo (`_in_flight_hosts`):** Se um host sofrer degradação severa e sua checagem demorar (por exemplo, atingindo o timeout de rede de 2 segundos), o próximo ciclo de 10 segundos poderia tentar disparar uma nova checagem simultânea do mesmo host. O NetSpot protege cada execução registrando o `host_id` em `_in_flight_hosts` sob `asyncio.Lock()`. Se o ID já estiver ativo, a nova mensagem é descartada sem duplicar trabalho, liberando o worker e garantindo idenfotência.

---

### Pergunta 2.8: "Como foi dimensionado o pool de conexões do PostgreSQL e como o sistema trata mensagens corrompidas no RabbitMQ (Dead Letter Queue)?"

* **Intenção da Banca:** Verificar se a infraestrutura foi dimensionada para evitar exaustão de conexões em alta concorrência e se o sistema possui tolerância a falhas para mensagens anômalas (*poison pills*).
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.1: *Modelagem de Dados e Persistência* (linhas 380–430).
  - Seção 3.5: *Mecanismos de Autocura e Resiliência (Self-Healing)* (linhas 617–642).
* **Evidências no Repositório / Código:**
  - [`docker-compose.yml:6-8`](file:///home/crispim/Documentos/netspot/docker-compose.yml#L6-L8): Configuração explícita `command: postgres -c max_connections=200`.
  - [`Backend/database.py:20-55`](file:///home/crispim/Documentos/netspot/Backend/database.py#L20-L55): Dimensionamento dos pools síncrono (`pool_size=20, max_overflow=10`) e assíncrono (`pool_size=35, max_overflow=30`).
  - [`Backend/mq_manager.py:48-74`](file:///home/crispim/Documentos/netspot/Backend/mq_manager.py#L48-L74): Declaração da exchange `netspot.dlx` e fila `netspot.dlq` com descarte sem requeue (`requeue=False`).
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Dimensionamento do Banco:** Por padrão, o PostgreSQL aloca 100 conexões máximas. Com 30 conexões potenciais na API REST (rotas HTTP síncronas), 65 conexões no motor assíncrono (scheduler/workers) e ~10 conexões do n8n, o pico teórico pode chegar a 105 conexões simultâneas. Parametrizamos `max_connections=200` no container do Postgres para eliminar o risco de erro crítico `FATAL: remaining connection slots are reserved`.
  2. **Isolamento de Poison Pills (Dead Letter Queue):** Em filas orientadas a eventos, mensagens malformadas (ex.: payload corrompido ou ID inexistente) provocam exceções no consumidor. Se rejeitadas com `requeue=True`, elas entram em um loop infinito que paralisa a CPU do worker. No NetSpot, qualquer mensagem não tratável é rejeitada com `requeue=False` e enviada à exchange `netspot.dlx` e arquivada na fila `netspot.dlq`, permitindo que o fluxo normal continue e mantendo a anomalia disponível para auditoria.

---

### Pergunta 2.9: "Como é gerenciado o ciclo de vida da sessão do operador no frontend e backend? O usuário é desconectado automaticamente após determinado tempo? Por que essa abordagem foi escolhida?"

* **Intenção da Banca:** Verificar o domínio sobre segurança de sessões baseadas em tokens stateless (JWT RFC 7519), conformidade com o *OWASP Session Management Cheat Sheet*, tratamento de erros reativo na camada de apresentação (interceptação de status 401 no cliente SPA) e o embasamento ergonômico vs. segurança em salas de monitoramento de redes 24/7.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.3: *Módulo de Autenticação, Criptografia e Segurança* (linhas 491–502).
* **Evidências no Repositório / Código:**
  - [`Backend/security.py:8,36-38`](file:///home/crispim/Documentos/netspot/Backend/security.py#L8-L38): Definição de `ACCESS_TOKEN_EXPIRE_MINUTES = 60` e injeção do claim `exp` com timestamp UTC expirável no payload do JWT assinado via HS256.
  - [`Backend/dependencies.py:18-49`](file:///home/crispim/Documentos/netspot/Backend/dependencies.py#L18-L49): A dependência `get_current_user` valida a assinatura e a validade temporal com `jose.jwt.decode`. Se o token tiver expirado, `jose.ExpiredSignatureError` dispara `HTTP 401 Unauthorized` (`detail: "Token inválido"`).
  - [`Frontend/js/app.js:250-266`](file:///home/crispim/Documentos/netspot/Frontend/js/app.js#L250-L266): O wrapper centralizado `fetchWithAuth` intercepta respostas com status 401, exibe o aviso em toast (`"Sessão expirada. Faça login novamente."`), expurga as credenciais e cache do navegador via `localStorage.clear()` e redireciona suavemente para `login.html`.
  - [`Frontend/js/app.js:11-14,202-211`](file:///home/crispim/Documentos/netspot/Frontend/js/app.js#L11-L14): Polling contínuo em segundo plano do Dashboard (a cada 10s visível ou 30s oculto) que garante a detecção reativa e imediata da expiração do token em tempo quase real, sem necessidade de recarregar a página manualmente.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Tempo de Vida Absoluto de 60 Minutos (Stateless JWT):**
     - O sistema adota autenticação *stateless* sem tabela de sessões no banco para cada requisição, eliminando I/O desnecessário no PostgreSQL a cada ciclo de polling de 10s.
     - A expiração absoluta de 60 minutos cumpre rigorosamente as recomendações da OWASP contra *CWE-613 (Insufficient Session Expiration)*, mitigando o risco de sequestro de credenciais (*session hijacking*), roubo de tokens em estações desacompanhadas ou uso indevido após o encerramento do turno de trabalho.
  2. **Por que Tempo Absoluto em vez de Timer de Inatividade de Mouse/Teclado?**
     - Em salas de operação de redes (NOC), o painel de monitoramento frequentemente permanece exibido em monitores de parede (*video walls*) ou telas de apoio sem cliques contínuos de mouse.
     - Um temporizador estrito de inatividade de periféricos (ex.: 15 minutos sem mover o mouse) derrubaria indevidamente painéis de acompanhamento 24/7 de operadores de plantão.
     - A expiração de 60 minutos do token oferece a janela de segurança ideal entre proteção criptográfica e comodidade operacional, permitindo renovação de login previsível e segura.
  3. **Comportamento Gracioso no Frontend:**
     - A desconexão não ocorre de forma abrupta ou silenciosa: o usuário recebe um feedback visual explícito (*Toast Notification*) e o `localStorage` é higienizado para não manter dados sensíveis ou estados residuais de autenticação.

---

## Categoria 3: Métricas de Rede, Causa Provável e Motor SNMP

---

### Pergunta 3.1: "Como é calculado o Score de Saúde (Health Score) e a Disponibilidade de um Host? Qual é a fórmula matemática?"

* **Intenção da Banca:** Verificar consistência teórica e rigor matemático do modelo proposto.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.7: *Modelagem Matemática e Métricas NOC* (linhas 704–783).
* **Evidências no Repositório / Código:**
  - [`Backend/metrics.py`](file:///home/crispim/Documentos/netspot/Backend/metrics.py): Funções `calculate_health_score`, `calculate_sla_rolling` e `calculate_jitter`.
  - [`Backend/tests/test_metrics.py`](file:///home/crispim/Documentos/netspot/Backend/tests/test_metrics.py): Testes automatizados validando o cálculo de saúde sob diferentes cenários de falha.
* **Roteiro e Argumentos-Chave para a Resposta:**
  - O score de saúde é um índice composto normalizado entre 0 e 100%, ponderando:
    1. Disponibilidade de ICMP/Ping (peso estrutural na conectividade básica);
    2. Sucesso de portas de aplicação (TCP/HTTP);
    3. Métricas de telemetria de hardware SNMP (CPU, RAM e Disco abaixo dos limiares de saturação);
    4. Estabilidade do Jitter (variação da latência entre pacotes consecutivos).
  - Não se trata de uma nota arbitrária: um host só atinge 100% de saúde quando responde satisfatoriamente na camada física, de rede, de transporte e de hardware.

---

### Pergunta 3.2: "Como o algoritmo de 'Causa Provável' (Probable Cause) funciona? Ele usa Inteligência Artificial ou lógica heurística determinística?"

* **Intenção da Banca:** Testar se o candidato confunde IA com árvores de decisão heurísticas e se o mecanismo é seguro para operação de NOC.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.7.4: *Motor de Inferência de Causa Provável* (linhas 748–783).
* **Evidências no Repositório / Código:**
  - [`Backend/routes/hosts.py:433-510`](file:///home/crispim/Documentos/netspot/Backend/routes/hosts.py#L433-L510): Função `infer_probable_cause(db, host)`.
  - [`Backend/tests/test_alert_logic.py`](file:///home/crispim/Documentos/netspot/Backend/tests/test_alert_logic.py): Testes de mesa conferindo cada diagnóstico inferido.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Lógica Determinística e Auditável:** Não utiliza modelos de linguagem estocásticos (como ChatGPT) nem redes neurais que poderiam produzir "alucinações" perigosas em redes de missão crítica.
  2. **Árvore Heurística Especialista:** O algoritmo cruza as camadas do modelo OSI:
     - Se o ICMP falha mas as portas HTTP/TCP respondem: *"Firewall bloqueando ICMP (serviço ativo)"*;
     - Se a CPU passa de 90%: *"Sobrecarga de processador (CPU > 90%)"*;
     - Se a latência varia excessivamente mas não há perda de pacotes: *"Degradação por Jitter elevado (> 80ms)"*;
     - Se o DNS falha: *"Falha na resolução de nomes (DNS indisponível)"*.
  3. **Vantagem Operacional:** Cada causa provável é **100% reproduzível, explicável e verificável** nos logs de teste.

---

### Pergunta 3.3: "Por que você implementou a community SNMP padrão como 'netspot' em vez de usar 'public'? Quais são os cuidados de segurança?"

* **Intenção da Banca:** Avaliar postura de segurança defensiva (*Security by Default*).
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.6: *Protocolos e Motor SNMP Multiplataforma* (linhas 643–660).
* **Evidências no Repositório / Código:**
  - [`Backend/scheduler.py`](file:///home/crispim/Documentos/netspot/Backend/scheduler.py): Constante `SNMP_ALLOWED_COMMUNITY = "netspot"`.
  - [`scripts/snmp/setup_snmp_linux.sh`](file:///home/crispim/Documentos/netspot/scripts/snmp/setup_snmp_linux.sh): Script de configuração com community `netspot` e restrição de acesso por IP.
* **Roteiro e Argumentos-Chave para a Resposta:**
  - A *community string* `public` é o vetor mais vulnerável em infraestruturas legadas de rede (alvo frequente de varreduras automatizadas de bots).
  - O NetSpot adota `netspot` como padrão customizado somente-leitura (*Read-Only*) e restringe o motor SNMP a não aceitar credenciais genéricas, mitigando vazamento não autorizado de tabelas MIB.

---

### Pergunta 3.4: "Como é calculado o Jitter e por que essa métrica é tão relevante em um ambiente de NOC?"

* **Intenção da Banca:** Avaliar o entendimento de métricas avançadas de telecomunicações e qualidade de serviço (QoS).
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.7.2: *Cálculo de Jitter Estatístico e Estabilidade de Tráfego* (linhas 725–740).
* **Evidências no Repositório / Código:**
  - [`Backend/metrics.py:65-90`](file:///home/crispim/Documentos/netspot/Backend/metrics.py#L65-L90): Função `calculate_jitter(samples)`.
* **Roteiro e Argumentos-Chave para a Resposta:**
  - **Definição:** Jitter é a variação estatística da latência (RTT) entre pacotes consecutivos transmitidos pela rede (baseado no cálculo da RFC 3550).
  - **Fórmula:** Média das diferenças absolutas entre os tempos de resposta consecutivos:
    $$J = \frac{1}{N-1} \sum_{i=1}^{N-1} |RTT_{i+1} - RTT_i|$$
  - **Importância Prática:** Em um NOC, um host pode apresentar 0% de perda de pacotes, mas possuir um jitter excessivo (> 50–80 ms). Isso causa interrupções severas em serviços sensíveis a tempo real (VoIP, videoconferência, streaming e replicação de banco de dados). O NetSpot sinaliza o jitter na Face 2 do card para diagnosticar gargalos antes que a queda total ocorra.

---

### Pergunta 3.5: "Como funciona a descoberta automática de rede (Network Discovery), por que hosts podem ser perdidos no primeiro ciclo de varredura e como o NetSpot mitiga esse comportamento?"

* **Intenção da Banca:** Avaliar se o aluno domina os protocolos da pilha TCP/IP (Camada 2 Enlace vs Camada 3 Rede), os mecanismos de resolução de endereços (ARP), o controle de temporização e congestionamento do Nmap, e se a solução previne negação de serviço (*Denial of Service*) ou falsos negativos na LAN.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.6.3: *Varredura e Descoberta de Nós de Rede* (linhas 685–703).
* **Evidências no Repositório / Código:**
  - [`Backend/routes/hosts.py:179-223`](file:///home/crispim/Documentos/netspot/Backend/routes/hosts.py#L179-L223): Função `_run_nmap_discovery(subnet)` com Calibração Dinâmica por Sub-rede (*CIDR-Aware Timing*).
  - [`Backend/routes/hosts.py:453-495`](file:///home/crispim/Documentos/netspot/Backend/routes/hosts.py#L453-L495): Sonda de portas aberta em lote `_discover_open_ports_batch` com semáforo assíncrono `asyncio.Semaphore(256)`.
  - [`Backend/routes/hosts.py:943-960`](file:///home/crispim/Documentos/netspot/Backend/routes/hosts.py#L943-L960): Rota `/api/network/discover`.
  - [`Frontend/dashboard.html#L240-L260`](file:///home/crispim/Documentos/netspot/Frontend/dashboard.html#L240-L260): Modal de descoberta com botão de seleção em massa (`#selectAllDiscoveryBtn`).
  - [`Backend/tests/test_audit_regressions.py:384-415`](file:///home/crispim/Documentos/netspot/Backend/tests/test_audit_regressions.py#L384-L415): Teste automatizado `test_run_nmap_discovery_fast_icmp_parameters`.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Arquitetura da Descoberta (Sem Broadcast Storm):**
     - O NetSpot não gera tempestade de broadcast cega. Ele executa uma varredura ICMP cirúrgica via Nmap (`-sn -PE -n`), desativando resoluções reversas de DNS bloqueantes no escaneador e gerando saída estruturada em XML (`-oX -`) processada em memória.
  2. **O Desafio do "Primeiro Clique" (Cold ARP Cache e Fila do Kernel):**
     - Em redes recém-iniciadas ou após períodos de inatividade, o emissor e os roteadores intermediários (como no laboratório Kathará) **não possuem os endereços físicos MAC dos nós na tabela de vizinhos (ARP cache miss)**.
     - Ao disparar o pacote ICMP Echo Request, o kernel do Linux precisa reter o pacote e enviar previamente um broadcast `ARP Request`. Os nós respondem com `ARP Reply`, e só então o ICMP é transmitido. Esse ciclo consome entre 80 ms e 350 ms em redes emuladas ou com múltiplos switches.
     - Se o scanner utilizar parâmetros rígidos e agressivos (ex.: RTT máximo de 200 ms e apenas 1 retentativa a 300 pacotes/s), dois problemas ocorrem:
       a) O pacote ICMP expira antes do ciclo ARP se completar, fazendo o Nmap marcar erroneamente o host como inativo (`down`);
       b) A rajada de 300 pacotes/s sobrecarrega a fila padrão de ARP não resolvido do kernel Linux (`/proc/sys/net/ipv4/neigh/default/unres_qlen`, cujo limite padrão é de apenas 3 pacotes por vizinho), descartando pacotes excedentes.
     - No segundo clique, o cache ARP já está "quente" (*warm cache*); as respostas chegam em < 5 ms e os hosts finalmente aparecem, gerando a falsa impressão de que a descoberta exige cliques repetidos.
  3. **Solução Adotada no NetSpot: Calibração Dinâmica Consciente da Sub-rede (CIDR-Aware Dynamic Tuning):**
     - O sistema avalia a máscara de rede informada (`net.num_addresses`) e calibra os argumentos de temporização do Nmap:
       - **Sub-redes Típicas ($\le 1.024$ IPs: `/24`, `/23`, `/22`)**:
         - `--initial-rtt-timeout 300ms`: tempo inicial realista para absorver o handshake ARP inicial sem descarte prematuro;
         - `--max-rtt-timeout 800ms`: margem segura para contenção de CPU de containers e atrasos de comutação L2/L3;
         - `--max-retries 2`: tolerância a eventuais perdas na primeira tentativa enquanto o nó popula sua tabela ARP;
         - `--min-rate 150`: fluxo estável que evita estouro da fila `unres_qlen` do kernel Linux, varrendo um `/24` completo em ~2 segundos com 100% de assertividade já na primeira execução.
       - **Sub-redes Massivas ($> 1.024$ IPs: `/21`, `/20` até 4.096 hosts)**:
         - `--initial-rtt-timeout 200ms`, `--max-rtt-timeout 500ms`, `--max-retries 1`, `--min-rate 350` para garantir que o scan de 4.096 endereços termine confortavelmente bem abaixo do tempo limite de 120 segundos da API HTTP.
  4. **Enriquecimento Assíncrono Multithread e Semáforo Concorrente:**
     - Após a detecção dos IPs ativos, o backend aplica enriquecimento paralelo:
       - Descoberta dinâmica de servidores DNS na sub-rede/rotas e resolução reversa de hostname (`PTR`);
       - Varredura de portas abertas (`80`, `443`, `22`, `8080`, etc.) com semáforo assíncrono `asyncio.Semaphore(256)`;
       - Consulta SNMP sysName direto no nó (`1.3.6.1.2.1.1.5.0`) via UDP 161.

---

### Pergunta 3.6: "Como o algoritmo de SLA calcula a disponibilidade sem duplicar o tempo de parada quando há múltiplos incidentes sobrepostos?"

* **Intenção da Banca:** Avaliar o rigor matemático na medição de Service Level Agreement (SLA) e garantir que o aluno não somou cegamente tempos de incidentes concorrentes, o que geraria downtime duplicado ou disponibilidade negativa.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.7.1: *Cálculo de SLA Contínuo e Janelas Temporais* (linhas 704–724).
* **Evidências no Repositório / Código:**
  - [`Backend/metrics.py:422-455`](file:///home/crispim/Documentos/netspot/Backend/metrics.py#L422-L455): Função `calculate_availability_from_incidents(incidents, window_minutes)`.
  - [`Backend/routes/hosts.py:1670-1685`](file:///home/crispim/Documentos/netspot/Backend/routes/hosts.py#L1670-L1685): Reutilização consistente do algoritmo na rota `/api/hosts/{id}/availability`.
  - [`Backend/tests/test_audit_regressions.py`](file:///home/crispim/Documentos/netspot/Backend/tests/test_audit_regressions.py): Teste automatizado `test_calculate_availability_merges_overlapping_incidents`.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **O Problema da Soma Simples:** Em um host real, múltiplos serviços podem falhar simultaneamente (por exemplo: porta HTTP 80 cai às 10:00 e retorna às 10:05; no mesmo intervalo, o Ping cai às 10:02 e retorna às 10:07). Somar $5\text{ min} + 5\text{ min} = 10\text{ min}$ de downtime em uma janela de 10 minutos resultaria em 0% de disponibilidade, embora o host estivesse operando normalmente entre 10:07 e 10:10 (o downtime real conjunto foi de apenas 7 minutos, de 10:00 a 10:07).
  2. **Algoritmo de Interval Merging (União de Intervalos):**
     - O NetSpot delimita o intervalo de cada incidente no período avaliado: $[s_i, e_i] = [\max(\text{start}_i, \text{since}), \min(\text{end}_i, \text{now})]$;
     - Ordena todos os intervalos pelo tempo inicial ($s_i$);
     - Itera fundindo intervalos sobrepostos: se o início do próximo for menor ou igual ao fim do anterior ($s_k \le \text{prev\_e}$), o fim é expandido: $\text{prev\_e} = \max(\text{prev\_e}, e_k)$;
     - O tempo de inatividade real ($\text{total\_down}$) é a soma estrita dos intervalos unificados, sem redundância;
  3. **Fórmula Normalizada:**
     $$\text{Disponibilidade (\%)} = \left(\frac{\text{Período Total} - \text{Total Down}}{\text{Período Total}}\right) \times 100$$
     O resultado é confinado deterministicamente entre $0.0\%$ e $100.0\%$.

---

### Pergunta 3.7: "Se uma empresa bloquear o tráfego ICMP (Ping) em seus firewalls, como o NetSpot evita falsos alarmes de 'Host Offline'?"

* **Intenção da Banca:** Verificar se o sistema trata cenários reais de redes corporativas e data centers onde políticas de segurança barram pacotes ICMP Echo Request.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.4.2: *Classificação de Estados e Resolução de Ambiguidade de Conectividade* (linhas 540–565).
  - Seção 3.7.4: *Motor de Inferência de Causa Provável* (linhas 748–783).
* **Evidências no Repositório / Código:**
  - [`Backend/scheduler.py:133-162`](file:///home/crispim/Documentos/netspot/Backend/scheduler.py#L133-L162): Função `determine_operational_state(check_results)` com a variável `service_up_without_icmp`.
  - [`Backend/metrics.py:12-24`](file:///home/crispim/Documentos/netspot/Backend/metrics.py#L12-L24): Normalização de peso em `calculate_health_score`.
  - [`Backend/routes/hosts.py:440-475`](file:///home/crispim/Documentos/netspot/Backend/routes/hosts.py#L440-L475): Regra heurística em `infer_probable_cause`.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Mitigação de Falsos Positivos:** Ferramentas tradicionais que dependem exclusivamente de Ping geram falsos alarmes ao monitorar servidores atrás de firewalls restritivos.
  2. **Regra de Decisão:** O NetSpot adota a lógica `service_up_without_icmp`: se a checagem ICMP falha (timeout ou bloqueio), mas a sonda de porta TCP (SSH 22, HTTPS 443) ou a aplicação HTTP responde positivamente, o sistema assume que a máquina está operacional e define o status como `UP`.
  3. **Transparência Operacional:** O motor de inferência (`infer_probable_cause`) assinala textualmente: *"ICMP bloqueado por firewall mas serviço operacional"*. O Health Score ajusta a ponderação para não penalizar indevidamente a conectividade, e nenhum falso incidente de queda total é aberto no NOC.

---

### Pergunta 3.8: "Como o NetSpot rastreia alterações de IP dinâmico por DHCP sem utilizar ARP broadcast e sem perder o histórico do dispositivo?"

* **Intenção da Banca:** Explorar arquitetura de rede e protocolos de Camada 2 (Data Link) versus Camada 3 e 7 (Network / Application).
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.4.1: *Ciclo de Vida do Host e Resolução de Nomes* (linhas 525–539).
* **Evidências no Repositório / Código:**
  - [`Backend/scheduler.py:379-415`](file:///home/crispim/Documentos/netspot/Backend/scheduler.py#L379-L415): Rastreamento de `last_resolved_ip` e emissão do evento `DNS_CHANGE`.
  - [`Backend/checker.py`](file:///home/crispim/Documentos/netspot/Backend/checker.py): Função assíncrona `resolve_dns_cached`.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Por que não usar ARP Broadcast:** O protocolo ARP opera na Camada 2 (enlace local) e seus pacotes de difusão (*broadcast*) não ultrapassam os roteadores de borda para alcançar outras sub-redes. Além disso, containers Docker isolados em bridges virtuais não têm acesso direto à tabela ARP do switch físico sem causar tempestades de pacotes ruidosas.
  2. **Abordagem Camada 7 via DNS Dinâmico:** Cadastrando os hosts via FQDN (ex.: `pc1.lab.local`), o NetSpot consulta o DNS com cache inteligente baseado no TTL. Se o servidor DHCP conceder um novo endereço IP, o scheduler detecta que o IP retornado difere de `host.last_resolved_ip`.
  3. **Continuidade de Dados:** O sistema emite um alerta do tipo `DNS_CHANGE` registrando a migração do IP no histórico de auditoria. Como a chave primária (`host.id`) permanece a mesma na base PostgreSQL, todas as séries temporais, gráficos e SLA são preservados sem fragmentação de histórico.

---

### Pergunta 3.9: "Como o NetSpot prevê que um host está para cair antes da queda acontecer? Qual a fundamentação matemática?"

* **Intenção da Banca:** Verificar o embasamento matemático de monitoramento preditivo (*Predictive Monitoring*) e avaliar se o candidato domina regressão linear aplicada à engenharia de software.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.7.3: *Análise de Tendência de Degradação por Regressão Linear* (linhas 741–747).
* **Evidências no Repositório / Código:**
  - [`Backend/metrics.py:301-386 e 453-530`](file:///home/crispim/Documentos/netspot/Backend/metrics.py#L301-L386): Funções `calculate_rtt_trend` e `apply_preventive_logic`.
  - [`arquitetura.md: Seção 6.2`](file:///home/crispim/Documentos/netspot/arquitetura.md): Tabela de limiares estatísticos da taxa de inclinação ($\text{slope}$).
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Fundamentação Matemática:** O NetSpot aplica o método dos **Mínimos Quadrados Ordinários (OLS - Ordinary Least Squares)** sobre a série temporal das últimas 10 amostras de Round-Trip Time (RTT):
     $$\text{slope} = \frac{\sum_{i=1}^N (x_i - \bar{x})(y_i - \bar{y})}{\sum_{i=1}^N (x_i - \bar{x})^2}$$
     Onde $x_i$ é a ordem temporal da coleta e $y_i$ é o tempo de resposta em milissegundos.
  2. **Classificação da Tendência de Degradação:**
     - $\text{slope} \le 15$: Conexão estável (`STABLE`);
     - $15 < \text{slope} \le 40$: Degradação progressiva (`DEGRADING`);
     - $\text{slope} > 40$: Degradação crítica acelerada (`FAST_DEGRADING`).
  3. **Ação Proativa:** Caso a inclinação acuse degradação acelerada, a função `apply_preventive_logic` eleva preventivamente a severidade para `WARNING` e aciona o despachante de alertas antes mesmo de ocorrer a perda definitiva de pacotes, permitindo à equipe de TI conter saturações de banda ou esgotamento de memória no servidor antes da interrupção do serviço.

---

## Categoria 4: Validação, Testes, Limitações e Trabalhos Futuros

---

### Pergunta 4.1: "Como você validou que o NetSpot realmente funciona? O que foi testado em ambiente simulado vs físico?"

* **Intenção da Banca:** Exigir evidências empíricas de que o software não é um projeto meramente conceitual.
* **Onde encontrar a base no texto do TCC:**
  - Seção 4.1: *Laboratório de Simulação Kathará* (linhas 910–958).
  - Seção 4.2: *Validação em Ambiente Físico Real (IFNMG — Campus Januária)* (linhas 959–969).
  - Seção 4.3: *Suíte de Testes Automatizados (Pytest)* (linhas 970–997).
* **Evidências no Repositório / Código:**
  - Diretório [`Teste - Kathará/`](file:///home/crispim/Documentos/netspot/Teste%20-%20Kathará/): Topologia com laboratórios virtuais, servidores DNS BIND, servidores web e roteadores Linux.
  - Suíte de Testes: 86 testes automatizados em [`Backend/tests/`](file:///home/crispim/Documentos/netspot/Backend/tests/) com 100% de cobertura funcional das regras críticas.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Validação Simulações de Alta Escala (Kathará):** Testado em topologia emulada complexa com laboratórios de até 126 nós heterogêneos, simulando quedas de interfaces, perda de rota e congelamento de serviços.
  2. **Validação Físico Real:** Validado na rede real do IFNMG Campus Januária, monitorando equipamentos reais com respostas a eventos de indisponibilidade e notificação em smartphone via Telegram em menos de 5 segundos.
  3. **Qualidade de Software Contínua:** 86 testes automatizados que garantem ausência de regressões em cálculo de SLA, purga de banco de dados, detecção de incidentes, controle de concorrência e autenticação JWT.

---

### Pergunta 4.2: "Quais são as principais limitações conhecidas do NetSpot e o que você faria de diferente hoje?"

* **Intenção da Banca:** Demonstrar autocrítica acadêmica e maturidade profissional (avaliar se o autor tem clareza dos limites do seu próprio trabalho).
* **Onde encontrar a base no texto do TCC:**
  - Seção 5: *Considerações Finais e Trabalhos Futuros* (linhas 1031–1060).
  - Seção 5 de [`.agents/MEMORIA.md`](file:///home/crispim/Documentos/netspot/.agents/MEMORIA.md).
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Limitação 1 (Visualização em Larga Escala):** A exibição em cards 3D é rica e ergonômica para até 20 hosts, mas em redes com centenas de dispositivos uma visualização tabular densa com paginação server-side é superior.
  2. **Limitação 2 (Protocolos SNMPv3):** O suporte atual concentra-se em SNMPv2c (amplamente adotado pela simplicidade). A implementação de criptografia e autenticação por usuário (SNMPv3 com USM) é o próximo passo natural de evolução.
  3. **Limitação 3 (Alta Disponibilidade do Poller):** Atualmente o motor de agendamento executa em uma única instância Docker. Em redes geograficamente distribuídas, a adoção de múltiplos agentes coletores (*distributed probes*) permitiria monitorar filiais remotas sem tráfego centralizado.

---

### Pergunta 4.3: "Qual é a cobertura da suíte de testes e por que não foram criados testes E2E no frontend?"

* **Intenção da Banca:** Avaliar conhecimento sobre a pirâmide de testes e critérios de custo-benefício em projetos de software.
* **Onde encontrar a base no texto do TCC:**
  - Seção 4.3: *Suíte de Testes Automatizados (Pytest)* (linhas 970–997).
* **Evidências no Repositório / Código:**
  - [`Backend/tests/`](file:///home/crispim/Documentos/netspot/Backend/tests/): 86 testes automatizados cobrindo rotas da API, regras de autocura, métricas estatísticas, circuit breaker, retenção de dados, controle de concorrência e regressões de auditoria.
  - [`docs/RELATORIO-UIUX.md`](file:///home/crispim/Documentos/netspot/docs/RELATORIO-UIUX.md): Auditoria e checklist manual exaustivo de UI/UX e WCAG.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Foco na Criticidade (Pirâmide de Testes):** Em sistemas de monitoramento, a criticidade reside na precisão dos cálculos de saúde, integridade das transações do banco, contenção de concorrência e agendamento dos eventos. Por isso, a automação com Pytest priorizou 100% dessas regras de negócio com 86 testes automatizados (100% de sucesso).
  2. **Pragmatismo no Frontend:** Por se tratar de uma SPA em JavaScript Vanilla sem framework pesado, testes E2E (como Cypress ou Playwright) demandariam dependências pesadas de Node.js e navegadores headless. A interface foi validada por meio de inspeção estrita de conformidade WCAG 2.1 AA, navegação completa por teclado e testes manuais multiplataforma.

---

### Pergunta 4.4: "Se a banca pedir uma demonstração ao vivo, qual é o passo a passo para executar?"

* **Intenção da Banca:** Confirmar reprodutibilidade imediata (*Infrastructure as Code*).
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.9: *Implantação e Conteinerização com Docker Compose* (linhas 806–830).
  - Arquivo [`README.md`](file:///home/crispim/Documentos/netspot/README.md).
* **Evidências no Repositório / Código:**
  - [`docker-compose.yml`](file:///home/crispim/Documentos/netspot/docker-compose.yml): Orquestração de 5 containers (`netspot-db`, `netspot-rabbitmq`, `netspot-n8n`, `netspot-backend`, `netspot-frontend`).
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. Executar no terminal:
     ```bash
     cp .env.example .env
     docker compose up -d
     ```
  2. Abrir o navegador em `http://localhost:8080` (Frontend) e logar com as credenciais administrativas.
  3. Demonstrar o cadastro de um host local ou simulação Kathará:
     - Apresentar a Face 1 (Saúde e Causa Provável);
     - Girar para a Face 2 (SLA e Jitter);
     - Girar para a Face 3 (Métricas SNMP de CPU/RAM/Disco);
     - Simular a queda do host (ou desligar porta) e mostrar a transição imediata para incidente e notificação.

---

### Pergunta 4.5: "Por que você escolheu o Kathará para a validação empírica do TCC em vez de simuladores como o Packet Tracer ou VMs pesadas?"

* **Intenção da Banca:** Avaliar se o aluno compreende a diferença entre simulação abstrata e emulação real com pilha de protocolos do kernel do sistema operacional.
* **Onde encontrar a base no texto do TCC:**
  - Seção 4.1: *Laboratório de Simulação Kathará* (linhas 910–958).
* **Evidências no Repositório / Código:**
  - Diretório [`Teste - Kathará/Lab-126hosts/`](file:///home/crispim/Documentos/netspot/Teste%20-%20Kathar%C3%A1/Lab-126hosts/): Arquivo `lab.conf` com 126 hosts distribuídos em 3 domínios de colisão interconectados por roteadores.
  - [`scripts/setup_kathara_network.sh`](file:///home/crispim/Documentos/netspot/scripts/setup_kathara_network.sh): Script de automação das interfaces de rede virtuais.
  - [`docs/kathara.md`](file:///home/crispim/Documentos/netspot/docs/kathara.md): Manual completo de operação e topologia.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Simulador vs Emulador:** O Cisco Packet Tracer é um ambiente fechado para fins didáticos de certificação que roda software proprietário sintetizado e não interage com o tráfego do mundo real do host operacional.
  2. **Pilha de Rede Real do Linux:** O Kathará instancia containers Docker ultra-leves rodando distribuições Linux reais (Debian). Cada nó tem sua própria tabela de roteamento no kernel, socket sockets reais, daemons verdadeiros (Apache2, Bind9, PostgreSQL, snmpd) e interfaces Ethernet virtuais (`veth`).
  3. **Eficiência de Recursos:** 126 máquinas virtuais convencionais (em VirtualBox ou VMware) exigiriam mais de 128 GB de memória RAM de um hipervisor. No Kathará, a emulação de 126 containers roda consumindo menos de 2 GB de memória RAM compartilhada no kernel do Linux, permitindo validar o NetSpot com tráfego real de rede em hardware convencional de estudante.

---

### Pergunta 4.6: "Quais práticas de segurança defensiva (OWASP) e proteção de endpoints foram aplicadas no backend e nos containers?"

* **Intenção da Banca:** Verificar o alinhamento com as diretrizes do OWASP Top 10 e OWASP ASVS (Application Security Verification Standard).
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.3: *Módulo de Autenticação, Criptografia e Segurança* (linhas 491–502).
* **Evidências no Repositório / Código:**
  - [`Backend/security.py`](file:///home/crispim/Documentos/netspot/Backend/security.py): Hashing seguro de senhas com `bcrypt` (salt individual) e geração de tokens JWT stateless (HS256) com claim `exp` de 60 minutos.
  - [`Backend/models.py`](file:///home/crispim/Documentos/netspot/Backend/models.py): Campos `failed_login_attempts` e `locked_until` para bloqueio de força bruta (*Brute-force Lockout*) após 5 tentativas consecutivas.
  - [`Backend/routes/hosts.py:1720-1745`](file:///home/crispim/Documentos/netspot/Backend/routes/hosts.py#L1720-L1745): Validação estrita na rota `/auth/first-password` (rejeita requisições com HTTP 400 se `user.must_change_password` for falso, bloqueando alteração indevida de senha de contas ativas).
  - [`Backend/main.py:100-120`](file:///home/crispim/Documentos/netspot/Backend/main.py#L100-L120): Sanitização rigorosa de sub-redes em `setup_kathara_routes` utilizando o módulo `ipaddress`, mitigando injeção de parâmetros de rede.
  - [`docker-compose.yml`](file:///home/crispim/Documentos/netspot/docker-compose.yml): Princípio do Menor Privilégio na exposição de portas: backend (`127.0.0.1:8000:8000`), PostgreSQL (`127.0.0.1:5432:5432`) e n8n (`127.0.0.1:5678:5678`) estão vinculados exclusivamente à interface de loopback interna, deixando apenas a porta do Nginx (8080) acessível externamente.
* **Roteiro e Argumentos-Chave para a Resposta:**
  - O sistema implementa o princípio da **Defesa em Profundidade (Defense-in-Depth)**: segurança na camada de infraestrutura (loopback binding), segurança na camada de transporte/sessão (JWT assinado com chave protegida) e segurança na camada de aplicação (lockout de força bruta e validação rigorosa de payloads com Pydantic).

---

### Pergunta 4.7: "Como a pesquisa é classificada formalmente em termos metodológicos e como o método de Wazlawick (2011) e o Design Science Research (DSR) estruturam o desenvolvimento do NetSpot?"

* **Intenção da Banca:** Avaliar o domínio do aluno sobre metodologia científica, taxonomia de pesquisa e rigor de engenharia de software acadêmica.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3: *Metodologia* (linhas 412–455).
  - Seção 3.1: *Classificação da Pesquisa*.
  - Seção 3.2: *Método de Engenharia e Modelagem de Software*.
* **Evidências no Repositório / Código:**
  - [`docs/analise_projeto_netspot_wazlawick.html`](file:///home/crispim/Documentos/netspot/docs/analise_projeto_netspot_wazlawick.html): Modelagem OO segundo Wazlawick (DCP, DSS, GRASP, FURPS+).
  - [`Backend/models.py`](file:///home/crispim/Documentos/netspot/Backend/models.py) e [`Backend/services/`](file:///home/crispim/Documentos/netspot/Backend/services/): Separação formal de entidades de domínio e classes de serviço com injeção de dependência.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Classificação Canônica:**
     - *Natureza:* **Aplicada** (foco na resolução de um gargalo prático real na gestão de TIC em redes de menor porte);
     - *Abordagem:* **Quali-quantitativa mista** (qualitativa na modelagem OO, ergonomia da interface e análise de causa provável; quantitativa na telemetria contínua de latência, jitter, SLA, uso de CPU e alocação de memória RAM);
     - *Objetivos:* **Descritivo-exploratória**;
     - *Procedimentos:* **Método experimental orientado a Design Science Research (DSR)** e Engenharia de Software.
  2. **Método Wazlawick e FURPS+:**
     - O desenvolvimento adotou a engenharia orientada a objetos de Raul Wazlawick (2011), estruturando requisitos pelo modelo FURPS+ (Funcionalidade, Usabilidade, Confiabilidade/Resiliência, Desempenho e Suportabilidade) e distribuindo responsabilidades por meio dos padrões GRASP (Craig Larman, 2005/2007) e Clean Architecture (Robert C. Martin, 2019), garantindo que regras de negócio não dependam de frameworks web ou bancos específicos.

---

### Pergunta 4.8: "Por que adotar uma estratégia de validação híbrida (Kathará 40/126 nós vs. computadores físicos do IFNMG Januária) e como ela mitiga riscos operacionais na instituição?"

* **Intenção da Banca:** Verificar a justificativa ética e operacional da pesquisa experimental e se o aluno soube contornar contingências reais de infraestrutura institucional sem comprometer a validade dos testes.
* **Onde encontrar a base no texto do TCC:**
  - Seção 3.3: *Estratégia Híbrida de Experimentação e Controle* (linhas 436–450).
  - Seção 5.1 e 5.2: *Laboratório Kathará* e *Validação Física Real*.
* **Evidências no Repositório / Código:**
  - [`Teste - Kathará/lab.conf`](file:///home/crispim/Documentos/netspot/Teste%20-%20Kathar%C3%A1/lab.conf) (40 nós) e [`Teste - Kathará/Lab-126hosts/lab.conf`](file:///home/crispim/Documentos/netspot/Teste%20-%20Kathar%C3%A1/Lab-126hosts/lab.conf) (126 nós).
  - Scripts de injeção controlada de perturbação de tráfego (`tc`) e estresse de hardware (`stress-ng`).
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Contingência Institucional Ética:** Os laboratórios de informática do IFNMG Januária possuem grade ininterrupta de aulas presenciais para turmas de graduação e cursos técnicos. Mobilizar dezenas de computadores físicos por dias seguidos para testes de estresse destrutivo (saturação de enlaces, derrubada de interfaces, desativação de firewalls) causaria interferência inaceitável nas atividades letivas.
  2. **Divisão de Responsabilidades da Abordagem Híbrida:**
     - *No Kathará:* Validou-se o comportamento sob estresse e escala extrema (40 e 126 nós monitorados em alta densidade, injeção de jitter via `tc`, simulação de loops de camada 2 com Spanning Tree e teste de saturação de CPU/RAM com `stress-ng`);
     - *No Ambiente Físico Real:* Validou-se a interoperabilidade prática com hardware real heterogêneo (Ubuntu Linux e Windows 10/11), a eficácia da descoberta automática de rede (LAN Discovery) e a resposta imediata do painel a eventos físicos reais (desconexão de cabos de rede e queda de servidores locais) durante janelas programadas de manutenção.

---

### Pergunta 4.9: "Qual foi o critério para a seleção e substituição de fontes bibliográficas na monografia (eliminação de posts/blogs e priorização de normas IETF/W3C e literatura clássica)?"

* **Intenção da Banca:** Avaliar o rigor metodológico e a qualidade da fundamentação teórica do trabalho acadêmico.
* **Onde encontrar a base no texto do TCC:**
  - Seção 2: *Referencial Teórico*.
  - [`referencias.bib`](file:///home/crispim/Documentos/netspot/Escrita_TCC/Escrita_latex/referencias.bib).
* **Evidências no Repositório / Código:**
  - Inclusão das normas formais da IETF (RFC 1157, RFC 1180, RFC 3411, RFC 3550), manuais normativos W3C (WCAG 2.1) e obras canônicas de engenharia de software e redes (Tanenbaum, Kurose, Forouzan, Wazlawick, Larman, Martin, Nygard, Hohpe & Woolf).
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Vulnerabilidade de Fontes Transitórias:** Posts de blogs comerciais, fóruns de internet e links de figuras avulsas (como imagens no ResearchGate) não passam por revisão por pares (*peer review*), podem se tornar links quebrados (*dead links*) e carecem de autoridade normativa perante uma banca de graduação.
  2. **Ancoragem nas Fontes Canônicas:**
     - Arquitetura de Redes e Protocolos: Livros clássicos (Tanenbaum, Kurose, Forouzan) e normas originais da ISO (ISO/IEC 7498-1) e IETF (RFC 1180);
     - Gerenciamento SNMP: Normas oficiais da IETF que especificam o protocolo (RFC 1157 e RFC 3411) e livros de administração de redes (Basso);
     - Engenharia de Software e Padrões: As obras originais que formularam cada padrão utilizado — Craig Larman (padrões GRASP), Robert C. Martin (SOLID e Clean Architecture), Michael Nygard (Circuit Breaker em *Release It!*) e Gregor Hohpe & Bobby Woolf (Enterprise Integration Patterns para Event-Driven Architecture);
     - Telemetria e Criptografia: RFC 3550 para mensuração normativa de Jitter, Niels Provos & David Mazières (USENIX) para a criptografia Bcrypt e W3C para as diretrizes de acessibilidade WCAG 2.1.

---

### Pergunta 4.10: "Ferramentas como Zabbix e Prometheus são muito maduras, consolidadas e reconhecidamente leves no nível de máquina. Por que propor o NetSpot em vez de utilizar uma delas?"

* **Intenção da Banca:** Verificar se o aluno conhece a realidade das ferramentas de mercado, se não reproduz mitos simplistas (como chamar Zabbix e Prometheus de "pesados", quando na verdade são compilados em C e Go de altíssimo desempenho) e se sabe defender com maturidade a verdadeira proposta de valor do NetSpot.
* **Onde encontrar a base no texto do TCC:**
  - Seção 1.3: *Justificativa* (linhas 341–353).
  - Seção 2.3: *Trabalhos Correlatos* (linhas 405–411).
  - Seção 5.3: *Consumo de Recursos, Desempenho e Comparativo Operacional* (linhas 1181–1213 e Tabela 7).
* **Evidências no Repositório / Código:**
  - [`docker-compose.yml`](file:///home/crispim/Documentos/netspot/docker-compose.yml): Implantação *turn-key* completa de 5 serviços em comando único (`docker compose up -d`).
  - [`Frontend/`](file:///home/crispim/Documentos/netspot/Frontend/): Interface SPA integrada sem necessidade de Grafana desacoplado.
  - [`N8N/workflows/`](file:///home/crispim/Documentos/netspot/N8N/workflows/): Fluxos de notificação prontos para Telegram sem compilação de regras de Alertmanager.
* **Roteiro e Argumentos-Chave para a Resposta:**
  1. **Reconhecimento Técnico do Estado da Arte:**
     - Inicie concordando com a premissa da banca: *"Zabbix (escrito em C) e Prometheus (escrito em Go) são de fato extremamente eficientes e leves em termos de processador e memória. O NetSpot não nasceu com a premissa de que eles são 'pesados' em consumo de máquina"*.
  2. **A Verdadeira Barreira: Custo de Tempo Humano (Instalação e Manutenção):**
     - O gargalo que o NetSpot resolve em escolas, prefeituras e pequenas e médias empresas (MPEs) é a **complexidade de instalação inicial e a curva íngreme de manutenção contínua**:
       - **No Zabbix:** Exige provisionar e dimensionar um SGBD dedicado (PostgreSQL/MySQL com particionamento manual), instalar e configurar agentes em cada ativo, gerenciar dezenas de macros e triggers, e criar ou importar templates de MIBs complexas;
       - **No Prometheus:** Exige orquestrar múltiplos serviços desacoplados (Prometheus Server, Alertmanager, Grafana para visualização, node_exporter, snmp_exporter com compilação prévia de MIBs via snmp.yml), além de exigir o domínio da linguagem de consulta PromQL;
     - Para um administrador generalista de TI ou suporte de rede em uma escola ou pequena empresa sem equipe dedicada de NOC, manter essa pilha exige horas excessivas de engenharia especializada.
  3. **A Proposta NOC Lite do NetSpot:**
     - Uma solução pronta para uso (*turn-key*) em um único comando `docker compose up -d`: banco relacional pré-configurado com expurgo automático (`RetentionService`), barramento AMQP resiliente, alertas automáticos formatados no Telegram via N8N, descoberta visual de LAN com um clique e interface ergonômica com cartões 3D;
     - Elimina completamente arquivos YAML manuais de exporters, compilação de MIBs ou linguagens de consulta proprietárias, entregando observabilidade proativa e cálculo de SLA instantâneo out-of-the-box.

---

## Diretrizes de Postura e Articulação Durante a Arguição

1. **Segurança e Firmeza:** Inicie cada resposta de forma afirmativa e direta ("Sim, essa decisão foi pautada pelo requisito de..."). Evite expressões de insegurança como "Acho que...", "Talvez..." ou "Fiz assim porque foi mais fácil".
2. **Engenharia com Propósito:** Sempre que justificar uma decisão, conecte-a com a realidade da administração de redes:
   - Exemplo: *"Optamos pelo RabbitMQ desacoplado para que a indisponibilidade momentânea do link de internet da instituição não trave a checagem dos equipamentos internos da rede local"*.
3. **Maturidade Diante das Limitações:** Todo software possui limites de escopo. Ao ser questionado sobre o que falta, reconheça com serenidade e indique que a solução já está planejada na seção de Trabalhos Futuros da monografia.
4. **Domínio do Próprio Código:** Cite com naturalidade os módulos (`metrics.py`, `checker.py`, `circuit_breaker.py`) e os padrões de projeto empregados. Isso demonstra que você é o autor autêntico do projeto de ponta a ponta.
