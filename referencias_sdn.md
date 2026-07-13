# Referências Acadêmicas Validadas sobre SDN

Lista de 15 referências REAIS, validadas por web (URL/DOI conferidos em IEEE Xplore, ACM DL, USENIX, ScienceDirect, arXiv, NTT). Nenhuma referência foi inventada.

---

## 1. Kreutz et al. (2015) — Survey abrangente de SDN
- **Citação:** KREUTZ, D.; RAMOS, F. M. V.; VERISSIMO, P. E.; ROTHENBERG, C. E.; AZODOLMOLKY, S.; UHLIG, S. Software-Defined Networking: A Comprehensive Survey. *Proceedings of the IEEE*, v. 103, n. 1, p. 14–76, 2015.
- **URL/DOI:** https://doi.org/10.1109/JPROC.2014.2371999 (preprint: https://arxiv.org/abs/1406.0440)
- **Importância (anomalias SDN+LLM):** Ao mapear formalmente plano de controle, plano de dados e canais lógicos de OpenFlow, este survey fornece a ontologia de estados e eventos de rede sobre a qual um LLM open-source (LoRA/QLoRA) pode ser fine-tunado para rotular anomalias de forma consistente.
- **Contribuição:** É o survey de referência que consolida conceitos, taxonomia e desafios de SDN, servindo de base estrutural para quase toda a literatura posterior.

## 2. McKeown et al. (2008) — OpenFlow (seminal)
- **Citação:** MCKEOWN, N.; ANDERSON, T.; BALAKRISHNAN, H.; PARULKAR, G.; PETERSON, L.; REXFORD, J.; SHENKER, S.; TURNER, J. OpenFlow: Enabling Innovation in Campus Networks. *ACM SIGCOMM Computer Communication Review (CCR)*, v. 38, n. 2, p. 69–74, 2008.
- **URL/DOI:** https://dl.acm.org/doi/10.1145/1355734.1355746
- **Importância (anomalias SDN+LLM):** Como OpenFlow é o canal padronizado de extração de fluxos (contagem de pacotes, bytes, durções), seus campos são a fonte primária de features tabulares para treinar detectores baseados em LLM.
- **Contribuição:** Introduziu o OpenFlow, o protocolo que viabilizou a separação prática entre plano de controle e plano de dados e deu origem ao paradigma SDN.

## 3. Lantz, Heller & McKeown (2010) — Mininet
- **Citação:** LANTZ, B.; HELLER, B.; MCKEOWN, N. A Network in a Laptop: Rapid Prototyping for Software-Defined Networks. *ACM SIGCOMM Workshop on Hot Topics in Networks (HotNets)*, 2010.
- **URL/DOI:** https://dl.acm.org/doi/10.1145/1868447.1868466
- **Importância (anomalias SDN+LLM):** Mininet permite gerar em um laptop topologias e tráfego reprodutíveis para construir datasets sintéticos de ataques (DDoS, scanning) usados no pré-treinamento e validação de modelos LLM.
- **Contribuição:** Criou o emulador leve (uso de containers/OS-level virtualization) que democratizou a prototipação e o ensino de SDN.

## 4. Pfaff et al. (2015) — Open vSwitch
- **Citação:** PFAFF, B.; PETTIT, J.; KOPONEN, T.; JACKSON, E.; ZHOU, A.; RAJAHALME, J.; GROSS, J.; WANG, A.; STRINGER, J.; SHELFUT, K.; AMIDON, K.; CASADO, M.; DAVIE, B. The Design and Implementation of Open vSwitch. *USENIX Symposium on Networked Systems Design and Implementation (NSDI)*, 2015.
- **URL/DOI:** https://www.usenix.org/conference/nsdi15/technical-sessions/presentation/pfaff
- **Importância (anomalias SDN+LLM):** O Open vSwitch é o plano de dados concreto (sFlow, tabelas de fluxo, regras) cujos logs alimentam a observabilidade necessária à detecção de anomalias por LLM.
- **Contribuição:** Descreveu o switch virtual multi-camada open-source dominante em ambientes virtualizados e de nuvem, conectando SDN a hypervisors reais.

## 5. Medved et al. (2014) — OpenDaylight
- **Citação:** MEDVED, J.; VARGA, R.; TKACIK, A.; GRAY, K. OpenDaylight: Towards a Model-Driven SDN Controller architecture. *IEEE Int'l Symposium on a World of Wireless, Mobile and Multimedia Networks (WoWMoM)*, 2014.
- **URL/DOI:** https://doi.org/10.1109/WoWMoM.2014.6918985 (https://ieeexplore.ieee.org/document/6918985/)
- **Importância (anomalias SDN+LLM):** A arquitetura orientada a modelos (YANG/NETCONF) do OpenDaylight expõe uma representação estruturada do estado da rede que pode ser serializada como prompt/contexto para um LLM de análise.
- **Contribuição:** Propos o controlador SDN baseado em Model-Driven Software Engineering, unindo abordagem OpenFlow e gerenciamento model-driven.

## 6. Berde et al. (2014) — ONOS
- **Citação:** BERDE, P.; GEROLA, M.; HART, J.; HIGASHI, Y.; KOBAYASHI, M.; KOIDE, T.; LANTZ, B.; O'CONNOR, B.; RADOSLAVOV, P.; SNOW, W.; PARULKAR, G. ONOS: Towards an Open, Distributed SDN OS. *ACM SIGCOMM Workshop on Hot Topics in Software-Defined Networking (HotSDN)*, 2014.
- **URL/DOI:** https://dl.acm.org/doi/10.1145/2620728.2620744
- **Importância (anomalias SDN+LLM):** Por ser distribuído e tolerante a falhas, o ONOS gera eventos de consistência/partição que constituem anomalias de controle a serem aprendidas por um LLM.
- **Contribuição:** Apresentou a primeira plataforma de controle SDN distribuída e de alto desempenho voltada a provedores de serviço.

## 7. Gude et al. (2008) — NOX (controlador pioneiro)
- **Citação:** GUDE, N.; KOPONEN, T.; PETTIT, J.; FLOYD, B.; McPHERSON, M.; CASADO, M.; SHERWOOD, R. NOX: Towards an Operating System for Networks. *ACM SIGCOMM Computer Communication Review (CCR)*, v. 38, n. 3, p. 105–110, 2008.
- **URL/DOI:** https://dl.acm.org/doi/10.1145/1384609.1384625
- **Importância (anomalias SDN+LLM):** NOX estabeleceu a abstração de "sistema operacional de rede" centralizado cujos conceitos de aplicação de políticas ainda orientam a detecção de desvios por LLM.
- **Contribuição:** Primeiro controlador SDN baseado em OpenFlow, introduzindo a noção de network operating system com visão e controle de toda a rede.

## 8. Kubo et al. (2014) — Ryu
- **Citação:** KUBO, R.; FUJITA, T.; AGAWA, Y.; SUZUKI, H. Ryu SDN Framework — Open-source SDN Platform Software. *NTT Technical Review*, v. 12, n. 8, 2014.
- **URL/DOI:** https://doi.org/10.53829/ntr201408fa4 (https://www.ntt-review.jp/archive/ntttechnical.php?contents=ntr201408fa4.html)
- **Importância (anomalias SDN+LLM):** O Ryu (Python, REST API) facilita a instrumentação de controladores em experimentos, permitindo coletar facilmente traces de fluxo para rotular anomalias em fine-tuning de LLM.
- **Contribuição:** Documentou o framework SDN baseado em componentes, de alto conformidade com OpenFlow, amplamente usado em pesquisa e ensino.

## 9. Kaur, Singh & Ghumman (2014) — POX
- **Citação:** KAUR, S.; SINGH, J.; GHUMMAN, N. S. Network Programmability Using POX Controller. *Proc. Int'l Conf. on Communication, Computing & Systems (ICCCS)*, 2014.
- **URL/DOI:** http://sbsstc.ac.in/icccs2014/Papers/Paper28.pdf
- **Importância (anomalias SDN+LLM):** O POX, por ser didático e em Python, é ideal para montar cenários de ataque/controle e exportar dados de treino para modelos LLM de detecção.
- **Contribuição:** Sistematizou o uso programável do controlador POX para prototipação de aplicações SDN e experimentos com Mininet.

## 10. Casado et al. (2007) — Ethane (precursor do plano de controle)
- **Citação:** CASADO, M.; FREEDMAN, M. J.; PETTIT, J.; LUO, J.; MCKEOWN, N.; SHENKER, S. Ethane: Taking Control of the Enterprise. *ACM SIGCOMM*, 2007.
- **URL/DOI:** https://dl.acm.org/doi/10.1145/1282380.1282382
- **Importância (anomalias SDN+LLM):** O modelo de políticas de rede de grão fino do Ethane antecipa a necessidade de detectar violações de política — tarefa natural para classificação por LLM.
- **Contribuição:** Propos uma arquitetura onde o controlador define políticas de rede fim-a-fim, precursor direto dos modelos de controle centralizado do SDN.

## 11. Jain et al. (2013) — B4 (deploy real em WAN)
- **Citação:** JAIN, S.; KUMAR, A.; MANDAL, S.; ONG, J.; POUTIEVSKI, L.; SINGH, A.; VENKATA, S.; WANDERER, J.; ZHOU, J.; ZHUA, M.; et al. B4: Experience with a Globally-Deployed Software Defined WAN. *ACM SIGCOMM*, 2013.
- **URL/DOI:** https://dl.acm.org/doi/10.1145/2534169.2486019
- **Importância (anomalias SDN+LLM):** Como evidência de SDN em escala de produção, o B4 define padrões de tráfego normais (baseline) contra os quais um LLM pode identificar anomalias em WANs.
- **Contribuição:** Primeiro relato de implantação global de SDN em WAN de data center, provando viabilidade e ganhos de utilização.

## 12. Feamster, Rexford & Zegura (2014) — História intelectual do SDN
- **Citação:** FEAMSTER, N.; REXFORD, J.; ZEGURA, E. The Road to SDN: An Intellectual History of Programmable Networks. *ACM SIGCOMM Computer Communication Review (CCR)*, v. 44, n. 2, p. 87–98, 2014.
- **URL/DOI:** https://dl.acm.org/doi/10.1145/2602204.2602219
- **Importância (anomalias SDN+LLM):** Ao explicitar que SDN = separação de planos + programabilidade, o artigo justifica por que anomalias em SDN podem ser modeladas como desvios de sinais de controle independentes.
- **Contribuição:** Traçou a linhagem das redes programáveis (active networks, separação de planos) até o SDN moderno, fundamentando o conceito.

## 13. Alsmadi & Xu (2015) — Survey de segurança em SDN
- **Citação:** ALSMADI, I.; XU, D. Security of Software Defined Networks: A Survey. *Computers & Security*, v. 53, p. 79–108, 2015.
- **URL/DOI:** https://doi.org/10.1016/j.cose.2015.05.006 (https://www.sciencedirect.com/science/article/abs/pii/S016740481500070X)
- **Importância (anomalias SDN+LLM):** Este survey cataloga ameaças (spoofing, tampering, DDoS no controlador) e fornece o vocabulário de rótulos de anomalia para treinar/curar datasets de LLM.
- **Contribuição:** Revisão extensa das ameaças à segurança de SDN organizadas por efeito, base para sistemas de detecção.

## 14. Feamster et al. (2004) — Separar roteamento dos roteadores
- **Citação:** FEAMSTER, N.; BALAKRISHNAN, H.; REXFORD, J.; SHAIKH, A.; VAN DER MERWE, J. The Case for Separating Routing from Routers. *ACM SIGCOMM Workshop on Future Directions in Network Architecture (FDNA)*, 2004.
- **URL/DOI:** https://dl.acm.org/doi/10.1145/1016707.1016709
- **Importância (anomalias SDN+LLM):** É a fundamentação teórica da separação de planos; entender o "Routing Control Platform" ajuda a modelar anomalias como falhas de sincronia controle-dados.
- **Contribuição:** Argumentou pioneiramente a favor da desacoplagem do plano de controle do plano de encaminhamento, raiz conceitual do SDN.

## 15. Sherwood et al. (2009/2010) — FlowVisor (separação de planos / virtualização) — *technical report*
- **Citação:** SHERWOOD, R.; GIBB, G.; YAP, K.-K.; APPERSON, G.; CASADO, M.; MCKEOWN, N.; PARULKAR, G.; TALMADGE, R. FlowVisor: A Network Virtualization Layer. *OpenFlow Tech Report, Stanford/ON.LAB*, 2009/2010.
- **URL/DOI:** https://www.semanticscholar.org/paper/FlowVisor%3A-A-Network-Virtualization-Layer-Sherwood-Gibb/64f3a81fff495ac336dccdd63136d451852eb1c9 (PDF via researchgate: https://www.researchgate.net/publication/238109224_FlowVisor_A_Network_Virtualization_Layer)
- **Importância (anomalias SDN+LLM):** O FlowVisor materializa a separação entre plano de controle e plano de dados através de "fatias" — conceito-chave para isolar e rotular anomalias por domínio de controle.
- **Contribuição:** Introduziu a camada de virtualização de rede que posiciona um plano de controle entre hardware e plano de dados,Isolando múltiplos controladores.

---

### Resumo de cobertura
- **Fundamentos / separação de planos:** #2, #10, #12, #14, #15
- **Controladores:** OpenDaylight (#5), ONOS (#6), NOX (#7), Ryu (#8), POX (#9)
- **Emulação / plano de dados:** Mininet (#3), Open vSwitch (#4)
- **Surveys:** Kreutz (#1), Alsmadi (#13)
- **Deploy real:** B4 (#11)

Total: 15 referências validadas (14 peer-reviewed com DOI/URL de editora + 1 technical report amplamente citado). Todas as URLs/DOIs foram conferidas por web_search / web_extract.
