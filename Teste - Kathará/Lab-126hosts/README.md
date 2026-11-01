# Laboratório Kathará de Alta Densidade — 126 Hosts Monitorados (`10.0.0.0/22`)

Este diretório (`Teste - Kathará/Lab-126hosts/`) contém a topologia de emulação **Kathará** escalada proporcionalmente para **126 hosts monitoráveis** na super-rede `10.0.0.0/22`, com serviços de rede, servidores corporativos, zonas DNS diretas/reversas completas e portas TCP/HTTP/HTTPS/UDP diversificadas.

---

## 1. Distribuição Proporcional dos 126 Hosts (`10.0.0.0/22`)

Ao executar a **Descoberta Automática** do NetSpot na faixa `10.0.0.0/22`, são descobertos exatamente **126 ativos roteáveis**, todos com **SNMPv2c (`161/udp`, community `netspot`)** e **resolução DNS Direta (`A`) e Reversa (`PTR`)** pré-configurados:

| Sub-rede | Faixa CIDR | Quantidade | Perfil / Dispositivos | Endereços IP | Nome DNS (`lab.local`) | Portas e Serviços Monitorados |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| **Lab 1 (Roteador)** | `10.0.1.0/24` | **1** | `router_lab1` (Gateway L3 Lab 1) | `10.0.1.1` | `router-lab1.lab.local` | ICMP + SNMP (`161/udp`) + SSH (`22/tcp`) |
| **Lab 1 (Acadêmico)** | `10.0.1.0/24` | **26** | `pc1` a `pc26` (Estações Acadêmicas) | `10.0.1.2` – `10.0.1.27` | `pc1.lab.local` – `pc26.lab.local` | ICMP + SNMP (`161/udp`) |
| **Lab 1 (DevOps)** | `10.0.1.0/24` | **12** | `pc27` a `pc38` (Estações DevOps) | `10.0.1.28` – `10.0.1.39` | `pc27.lab.local` – `pc38.lab.local` | ICMP + SNMP (`161/udp`) + SSH (`22/tcp`) + HTTP Dev (`8080/tcp`) |
| **Lab 1 (Admin)** | `10.0.1.0/24` | **8** | `pc39` a `pc46` (Estações Suporte/Admin) | `10.0.1.40` – `10.0.1.47` | `pc39.lab.local` – `pc46.lab.local` | ICMP + SNMP (`161/udp`) + SSH (`22/tcp`) |
| **Lab 2 (Roteador)** | `10.0.2.0/24` | **1** | `router_lab2` (Gateway L3 Lab 2) | `10.0.2.1` | `router-lab2.lab.local` | ICMP + SNMP (`161/udp`) + SSH (`22/tcp`) |
| **Lab 2 (Acadêmico)** | `10.0.2.0/24` | **26** | `pc47` a `pc72` (Estações Acadêmicas) | `10.0.2.2` – `10.0.2.27` | `pc47.lab.local` – `pc72.lab.local` | ICMP + SNMP (`161/udp`) |
| **Lab 2 (Full-Stack)** | `10.0.2.0/24` | **12** | `pc73` a `pc84` (Estações Web/Frontend) | `10.0.2.28` – `10.0.2.39` | `pc73.lab.local` – `pc84.lab.local` | ICMP + SNMP (`161/udp`) + SSH (`22/tcp`) + Web App (`3000/tcp`) |
| **Lab 2 (Dados)** | `10.0.2.0/24` | **8** | `pc85` a `pc92` (Estações Eng. Dados) | `10.0.2.40` – `10.0.2.47` | `pc85.lab.local` – `pc92.lab.local` | ICMP + SNMP (`161/udp`) + SSH (`22/tcp`) + PostgreSQL (`5432/tcp`) |
| **Datacenter (Roteador)** | `10.0.3.0/24` | **1** | `router_lab3` (Gateway L3 Datacenter) | `10.0.3.1` | `router-lab3.lab.local` | ICMP + SNMP (`161/udp`) + SSH (`22/tcp`) |
| **Servidores Web** | `10.0.3.0/24` | **9** | `web_server1` a `web_server9` | `10.0.3.2` – `10.0.3.10` | `web1.lab.local` – `web9.lab.local` | Apache HTTP (`80/tcp`) + HTTPS (`443/tcp`) + Status (`8080/tcp`) + SSH (`22/tcp`) + SNMP (`161/udp`) |
| **Servidores App/API** | `10.0.3.0/24` | **6** | `app_server1` a `app_server6` | `10.0.3.11` – `10.0.3.16` | `app1.lab.local` – `app6.lab.local` | App HTTP (`8080/tcp`) + API REST (`8000/tcp`) + SSH (`22/tcp`) + SNMP (`161/udp`) |
| **Servidores PostgreSQL** | `10.0.3.0/24` | **4** | `db_server1` a `db_server4` | `10.0.3.17` – `10.0.3.20` | `db1.lab.local` – `db4.lab.local` | PostgreSQL (`5432/tcp`) + Exporter HTTP (`9187/tcp`) + SSH (`22/tcp`) + SNMP (`161/udp`) |
| **Servidores Multi-DB** | `10.0.3.0/24` | **2** | `db_server5` a `db_server6` | `10.0.3.21` – `10.0.3.22` | `db5.lab.local` – `db6.lab.local` | MySQL (`3306/tcp`) + PostgreSQL (`5432/tcp`) + Exporter (`9187/tcp`) + SSH (`22/tcp`) + SNMP (`161/udp`) |
| **Servidores DNS BIND9** | `10.0.3.0/24` | **4** | `dns_server1` a `dns_server4` | `10.0.3.23` – `10.0.3.26` | `ns1.lab.local` – `ns4.lab.local` | BIND9 DNS (`53/tcp`, `53/udp`) + SSH (`22/tcp`) + SNMP (`161/udp`) |
| **Servidores Cache/Fila** | `10.0.3.0/24` | **3** | `cache_server1` a `cache_server3` | `10.0.3.27` – `10.0.3.29` | `cache1.lab.local` – `cache3.lab.local` | Redis (`6379/tcp`) + RabbitMQ AMQP (`5672/tcp`) + Admin HTTP (`8080/tcp`) + SSH (`22/tcp`) + SNMP (`161/udp`) |
| **Servidores Proxy/LB** | `10.0.3.0/24` | **3** | `proxy_server1` a `proxy_server3` | `10.0.3.30` – `10.0.3.32` | `proxy1.lab.local` – `proxy3.lab.local` | Nginx HTTP (`80/tcp`) + HTTPS (`443/tcp`) + Gateway HTTPS (`8443/tcp`) + SSH (`22/tcp`) + SNMP (`161/udp`) |
| **TOTAL MONITORADO** | **`10.0.0.0/22`** | **126** | **92 PCs + 31 Servidores + 3 Roteadores** | **126 IPs ativos** | **100% com DNS `A` e `PTR`** | **126 SNMP, 74 com portas TCP (13 portas distintas), 49 com HTTP/HTTPS** |

---

## 2. Como Executar na Máquina de Teste (Ryzen 7 7800X3D / 32 GB RAM)

1. **Certifique-se de que o NetSpot está em execução via Docker Compose**:
   ```bash
   docker compose up -d
   ```

2. **Caso o laboratório menor (40 hosts) esteja rodando, encerre-o antes**:
   ```bash
   cd "Teste - Kathará"
   kathara lclean
   ```

3. **Inicie o laboratório de 126 hosts com a imagem `adrianoifnmg/kathara`**:
   ```bash
   cd "Teste - Kathará/Lab-126hosts"
   kathara lstart --image adrianoifnmg/kathara
   ```

4. **Conecte o `router_core` do Kathará ao container `netspot-backend`**:
   Volte para a raiz do projeto e execute o script de interconexão:
   ```bash
   cd ../..
   ./scripts/setup_kathara_network.sh
   ```

5. **Descubra e importe automaticamente os 126 hosts com portas e serviços**:
   - Acesse o Dashboard do NetSpot (`http://localhost:8080`).
   - Em **Descoberta Automática**, informe a super-rede:
     ```text
     10.0.0.0/22
     ```
   - Clique em **Descobrir rede**: o NetSpot descobrirá os **126 hosts**, resolverá automaticamente os nomes via DNS reverso (`db.10.0.1`, `db.10.0.2`, `db.10.0.3`) / SNMP `sysName.0`, e detectará automaticamente todas as portas TCP abertas (`22, 53, 80, 443, 3000, 3306, 5432, 5672, 6379, 8000, 8080, 8443, 9187`) e checks Web HTTP/HTTPS!
   - Clique em **Adicionar selecionados** para iniciar o monitoramento simultâneo dos 126 ativos.

