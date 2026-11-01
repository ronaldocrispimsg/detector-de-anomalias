# Planejamento e Execução do Laboratório Experimental com Kathará no NetSpot

Este documento apresenta a arquitetura da topologia, a análise de viabilidade computacional e a metodologia experimental para a simulação de uma rede corporativa e acadêmica em larga escala (40+ dispositivos) utilizando a ferramenta **Kathará**, validando o protótipo **NetSpot (NOC Lite)** no âmbito do Trabalho de Conclusão de Curso (TCC) em Sistemas de Informação no IFNMG — Campus Januária.

---

## 1. Análise de Viabilidade Técnica e Desempenho

O **Kathará** é uma plataforma de emulação de redes baseada em containers leves, compartilhando o kernel do sistema operacional hospedeiro. Isso viabiliza a execução simultânea de dezenas de nós virtuais com consumo reduzido de memória quando comparado a hipervisores tradicionais de virtualização completa (KVM/QEMU, GNS3 ou EVE-NG).

### Estimativa de Carga Computacional:

* **Consumo por Nó Kathará (Debian/Alpine com SNMPD e ferramentas de rede)**: $\approx 15\text{ MB a } 25\text{ MB de RAM}$ por nó ocioso.
* **Carga de 40 Nós Kathará**:
  $$\text{RAM dos 40 Nós Simulados} \approx 40 \times 20\text{ MB} = 800\text{ MB de RAM}$$
* **Carga da Infraestrutura NetSpot (5 Containers Docker)**:
  * PostgreSQL 15: $\approx 150\text{ MB}$
  * RabbitMQ Broker: $\approx 180\text{ MB}$
  * Backend FastAPI (Python 3.11 / 3.12): $\approx 120\text{ MB}$
  * n8n Automation: $\approx 350\text{ MB}$
  * Frontend Nginx Alpine: $\approx 20\text{ MB}$
  * **Total NetSpot**: $\approx 820\text{ MB a } 1.2\text{ GB}$
* **Consumo Global Estimado do Laboratório Completo**: **~2.0 GB a 3.0 GB de RAM Total**.

> **Conclusão de Viabilidade**: O experimento completo com 40 computadores e 4 roteadores executa com estabilidade em computadores pessoais equipados com 8 GB ou 16 GB de memória RAM.

---

## 2. Arquitetura da Topologia de Rede Simulada

A topologia emulada reproduz uma infraestrutura corporativa/acadêmica dividida em **4 Sub-redes Roteadas**:

```text
                               +-----------------------------+
                               |     NetSpot Server (NOC)    |
                               | (Bridge Docker 172.17.0.x)  |
                               +--------------+--------------+
                                              | (172.17.0.2)
                                      +-------+-------+
                                      | Roteador Core |
                                      | (router_core) |
                                      +---+---+---+---+
                                          |   |   |
         +--------------------------------+   |   +--------------------------------+
         |                                    |                                    |
+--------+--------+                  +--------+--------+                  +--------+--------+
| Roteador Lab 1  |                  | Roteador Lab 2  |                  | Roteador Servid. |
|  (10.0.1.1/24)  |                  |  (10.0.2.1/24)  |                  |  (10.0.3.1/24)  |
+--------+--------+                  +--------+--------+                  +--------+--------+
         |                                    |                                    |
   (15 Clientes)                        (15 Clientes)                        (10 Servidores)
   - pc1 a pc15                         - pc16 a pc30                        - Web, DNS, DB, App
   - Agente SNMP (netspot)              - Agente SNMP (netspot)              - Agente SNMP (netspot)
```

### Mapeamento dos Nós Monitorados no `lab.conf` (40 Hosts Finais + 4 Roteadores):
- **Sub-rede Laboratório 1 (`10.0.1.0/24`)**: `router_lab1` (`10.0.1.1`) + 15 estações clientes (`pc1` a `pc15`, `10.0.1.2` a `10.0.1.16`).
- **Sub-rede Laboratório 2 (`10.0.2.0/24`)**: `router_lab2` (`10.0.2.1`) + 15 estações clientes (`pc16` a `pc30`, `10.0.2.2` a `10.0.2.16`).
- **Sub-rede Servidores de Aplicação (`10.0.3.0/24`)**: `router_lab3` (`10.0.3.1`) + 10 servidores dedicados:
  - 3 Servidores Web (`web_server1..3` em `10.0.3.2` a `10.0.3.4`);
  - 2 Servidores de Aplicação (`app_server1..2` em `10.0.3.5` e `10.0.3.6`);
  - 2 Servidores DNS BIND9 (`dns_server1..2` em `10.0.3.7` e `10.0.3.8`, com zonas diretas `db.lab.local` e reversas `db.10.0.1`, `db.10.0.2`, `db.10.0.3`);
  - 3 Servidores de Banco de Dados (`db_server1..3` em `10.0.3.9` a `10.0.3.11`).
- **Roteadores e Infraestrutura de Enlace**:
  - `router_core`: Interconexão em modo `bridged` (`172.17.0.2`) com os containers `netspot-backend` e `netspot-n8n` e enlaces ponto-a-ponto `100.0.1.0/24`, `100.0.2.0/24` e `100.0.3.0/24`.
  - `router_lab1`, `router_lab2`, `router_lab3`: Roteadores de distribuição configurados via diretivas `[exec]` no `lab.conf`, também inicializando `./setup_snmp_linux.sh`.

---

## 3. Configuração dos Agentes SNMP nos Nós

Todos os nós do laboratório Kathará executam o daemon `snmpd` configurado com a community somente-leitura customizada **`netspot`**, conforme a diretriz de segurança do projeto (mitigando o uso da credencial genérica `public`).

O script de inicialização do SNMP (`setup_snmp_linux.sh`) presente nos nós aplica a configuração:

```bash
agentAddress udp:161
rocommunity netspot default .1
sysName $(hostname)
sysLocation NetSpot Lab
sysContact admin@lab.local
```

---

## 4. Cenários de Testes Práticos e Injeção de Falhas

Com o Kathará, é possível aplicar perturbações controladas de tráfego para avaliar o tempo de reação, o algoritmo de Causa Provável e a resiliência do NetSpot:

### Cenário A: Queda Abrupta de Dispositivo (Estado DOWN)
* **Ação**: Interrupção do container ou encerramento de interface:
  ```bash
  kathara vclean -n pc12
  ```
* **Métrica Aferida**: Tempo até a detecção pelo coletor, abertura do incidente no PostgreSQL e notificação via Telegram.
* **Resultado Esperado**: Detecção rápida ($\text{MTTD} < 30\text{ s}$), ativação do Circuit Breaker e transição visual do card para status crítico.

### Cenário B: Degradação por Latência e Variação de Tráfego (Estado DEGRADED)
* **Ação**: Injeção de latência e perda de pacotes via `tc` (Traffic Control) na interface do nó:
  ```bash
  tc qdisc add dev eth0 root netem delay 250ms loss 12%
  ```
* **Métrica Aferida**: Reclassificação do **Health Score (0 a 100%)**, elevação do **Jitter estatístico (ms)** e acionamento da heurística de causa provável (*Degradação por Jitter elevado*).

### Cenário C: Sobrecarga de Recursos Físicos (Telemetria SNMP)
* **Ação**: Execução do utilitário `stress-ng` dentro de um nó Kathará para forçar sobrecarga de CPU:
  ```bash
  stress-ng --cpu 4 --timeout 60s
  ```
* **Métrica Aferida**: Coleta da telemetria de processamento via SNMP, exibição do pico de carga na Face 3 do card do host e diagnóstico preditivo de *"Sobrecarga de processador (CPU > 90%)"*.

---

## 5. Estratégia Metodológica para a Defesa do TCC

A validação experimental do NetSpot combina duas abordagens complementares:
1. **Emulação em Larga Escala (Kathará)**:
   - Validação da capacidade do motor assíncrono frente a 40+ ativos distribuídos em múltiplas sub-redes roteadas;
   - Avaliação do consumo computacional do servidor de monitoramento sob cenários de estresse.
2. **Ambiente Físico Real (IFNMG Campus Januária)**:
   - Validação com computadores e equipamentos de rede reais no ambiente acadêmico;
   - Avaliação da usabilidade prática e experiência do operador na sala de controle.

---

## 6. Como Executar o Laboratório Kathará

1. **Instalar o Kathará no Linux (Ubuntu / Debian)**:
   ```bash
   sudo apt-get install kathara
   ```
2. **Navegar até a pasta do laboratório e iniciar a topologia**:
   ```bash
   cd "Teste - Kathará"
   kathara lstart
   ```
3. **Integrar a rede do Kathará com o NetSpot**:
   Se os containers do NetSpot já estiverem rodando, execute o script de interconexão:
   ```bash
   chmod +x ./scripts/setup_kathara_network.sh
   ./scripts/setup_kathara_network.sh
   ```
4. **Abrir o Dashboard do NetSpot**:
   Acesse [http://localhost:8080](http://localhost:8080) e inicie a descoberta automática da rede para cadastrar os nós monitorados.

---

## 7. Topologia Escalada de Estresse — 126 Hosts (`Teste - Kathará/Lab-126hosts/`)

Para testes de capacidade máxima (equivalente a uma sub-rede `/25` completa com **126 hosts monitorados** simultaneamente a cada 10s), o repositório disponibiliza o laboratório dedicado `Teste - Kathará/Lab-126hosts/`:

* **Sub-rede 1 (`10.0.1.0/24`)**: `router_lab1` (`10.0.1.1`) + **46 estações** (`pc1` a `pc46`, divididas em perfis Acadêmico ICMP+SNMP, DevOps SSH `22` + HTTP `8080` + SNMP, e Suporte/Admin SSH `22` + SNMP) = **47 hosts**.
* **Sub-rede 2 (`10.0.2.0/24`)**: `router_lab2` (`10.0.2.1`) + **46 estações** (`pc47` a `pc92`, divididas em perfis Acadêmico ICMP+SNMP, Full-Stack SSH `22` + Web `3000` + SNMP, e Engenharia de Dados SSH `22` + PostgreSQL `5432` + SNMP) = **47 hosts**.
* **Sub-rede 3 (`10.0.3.0/24`)**: `router_lab3` (`10.0.3.1`) + **31 servidores corporativos** (`web_server1..9` em `80, 443, 8080, 22`; `app_server1..6` em `8080, 8000, 22`; `db_server1..6` em `5432, 3306, 9187, 22`; `dns_server1..4` BIND9 em `53, 22` com zonas diretas e reversas `db.10.0.1`, `db.10.0.2`, `db.10.0.3`; `cache_server1..3` em `6379, 5672, 8080, 22`; `proxy_server1..3` em `80, 443, 8443, 22`) = **32 hosts**.
* **Execução recomendada (16 GB a 32 GB de RAM)**:
  ```bash
  cd "Teste - Kathará/Lab-126hosts"
  kathara lstart --image adrianoifnmg/kathara
  cd ../..
  ./scripts/setup_kathara_network.sh
  ```
  Consulte `Teste - Kathará/Lab-126hosts/README.md` para a tabela detalhada de IPs, nomes DNS e portas.
