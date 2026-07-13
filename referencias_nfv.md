# Referências Acadêmicas Validadas — Network Function Virtualization (NFV)

Lista com 13 referências REAIS, validadas por web (web_search + web_extract em 13/jul/2026).
Foco: surveys, arquitetura, MANO, orquestração (OSM/ONAP), placement de VNFs e desafios.
Para cada item: (1) Citação completa; (2) URL/DOI validado; (3) frase de IMPORTÂNCIA para anomalias em SDN com LLMs;
(4) frase de CONTRIBUIÇÃO.

---

1. **ETSI NFV — Introductory White Paper (2012)**
   - Citação: ETSI Industry Specification Group (ISG) NFV. "Network Functions Virtualisation (NFV): An Introduction, Benefits, Enablers, Challenges & Call for Action," White Paper Issue 1, Outubro 2012. Autores/operadoras: AT&T (M. Chiosi), BT, CenturyLink, China Mobile, Colt, Deutsche Telekom, KDDI, NTT, Orange, Telecom Italia, Telefónica, Telstra, Verizon (P. Sen).
   - URL validada: https://portal.etsi.org/nfv/nfv_white_paper.pdf
   - IMPORTÂNCIA: Ao expor os desafios de gerenciar e orquestrar muitas VNFs junto a sistemas legados e à segurança contra ataque/má-configuração, este documento funda a taxonomia de anomalias operacionais que um LLM pode aprender a detectar em SDN/NFV.
   - CONTRIBUIÇÃO: Introduziu o conceito de NFV e seu alinhamento complementar (não dependente) com SDN, estabelecendo o campo e o chamado para padronização que originou o ETSI ISG NFV.

2. **ETSI GS NFV 002 V1.2.1 — Architectural Framework (2014)**
   - Citação: ETSI GS NFV 002 V1.2.1, "Network Functions Virtualisation (NFV); Architectural Framework," Dezembro 2014. Reference RGS/NFV-002.
   - URL validada: https://www.etsi.org/deliver/etsi_gs/NFV/001_099/002/01.02.01_60/gs_NFV002v010201p.pdf
   - IMPORTÂNCIA: O modelo de blocos funcionais e pontos de referência (incluindo novas interfaces de interconexão) define exatamente onde novos vetores de ameaça e anomalias de orquestração surgem — alvo natural para monitoramento por LLM.
   - CONTRIBUIÇÃO: Define o framework arquitetural de alto nível de NFV, com os blocos NFVI, VNF, MANO e seus pontos de referência, servindo de base para toda a padronização subsequente.

3. **ETSI GS NFV-MAN 001 V1.1.1 — Management and Orchestration (2014)**
   - Citação: ETSI GS NFV-MAN 001 V1.1.1, "Network Functions Virtualisation (NFV); Management and Orchestration," Dezembro 2014. Reference DGS/NFV-MAN001. Rapporteur: Jürgen Quittek (NEC).
   - URL validada: https://www.etsi.org/deliver/etsi_gs/NFV-MAN/001_099/001/01.01.01_60/gs_NFV-MAN001v010101p.pdf
   - IMPORTÂNCIA: Como o MANO governa o ciclo de vida (on-boarding, instanciação, scaling, migração) das VNFs, suas falhas e desvios de políticas são a principal fonte de anomalias operacionais passíveis de detecção assistida por LLM em SDN.
   - CONTRIBUIÇÃO: Especifica o framework de gerenciamento e orquestração de NFV (NFV-MANO), seus elementos de informação e interfaces (OR-Vi, Or-Vnfm, Os-Ma, etc.), padronizando o LCM de VNFs e Network Services.

4. **Mijumbi et al. (2016) — Communications Surveys & Tutorials**
   - Citação: Mijumbi, R., Serrat, J., Gorricho, J.-L., Bouten, N., De Turck, F., Boutaba, R. "Network Function Virtualization: State-of-the-Art and Research Challenges." IEEE Communications Surveys & Tutorials, vol. 18, no. 1, pp. 236–262, 2016.
   - DOI/URL validada: https://doi.org/10.1109/COMST.2015.2477041 (https://dl.acm.org/doi/10.1109/COMST.2015.2477041) — ~2.726 citações.
   - IMPORTÂNCIA: Ao mapear desafios em aberto (confiabilidade, segurança, gerenciamento, desempenho) do estado da arte em NFV, este survey delimita as categorias de anomalias cuja detecção pode ser potencializada por LLMs em redes SDN.
   - CONTRIBUIÇÃO: Oferece o survey mais citado e abrangente de NFV, relacionando NFV a SDN e cloud, e identificando direções de pesquisa promissoras, projetos-chave e esforços de padronização.

5. **Han et al. (2015) — Challenges and Opportunities for Innovations**
   - Citação: Han, B., Gopalakrishnan, V., Ji, L., Lee, S. "Network Function Virtualization: Challenges and Opportunities for Innovations." IEEE Communications Magazine, vol. 53, no. 2, pp. 90–97, Fevereiro 2015.
   - DOI/URL validada: https://doi.org/10.1109/MCOM.2015.7045396 (https://ieeexplore.ieee.org/document/7045396/) — citado na ref. 4.
   - IMPORTÂNCIA: Discute requisitos arquiteturais e casos de uso onde a degradação de VNFs e a má orquestração geram anomalias de serviço — sinais que um LLM pode correlacionar em tempo real no plano SDN.
   - CONTRIBUIÇÃO: Apresenta visão prática de NFV (requisitos, framework arquitetural, use cases) e discute oportunidades de inovação e os principais desafios de implantação.

6. **Hawilo et al. (2014) — NFV State of the Art, vEPC**
   - Citação: Hawilo, H., Shami, A., Mirahmadi, M., Asal, R. "NFV: State of the Art, Challenges, and Implementation in Next Generation Mobile Networks (vEPC)." IEEE Network, vol. 28, no. 6, pp. 18–26, Novembro 2014.
   - DOI/URL validada: https://doi.org/10.1109/MNET.2014.6963800 (https://arxiv.org/abs/1409.4149) — ~680 citações.
   - IMPORTÂNCIA: Ao detalhar a implementação de vEPC e seus requisitos, evidencia pontos de falha específicos de funções críticas que, uma vez anomalados, comprometem o plano de dados SDN — detecção natural para LLM.
   - CONTRIBUIÇÃO: Propõe um framework NFV aplicado a redes móveis de próxima geração (vEPC), definindo serviços, use cases e os desafios de sua adoção em ambiente real.

7. **Yi et al. (2018) — A Comprehensive Survey of NFV**
   - Citação: Yi, B., Wang, X., Li, K., Huang, M. "A Comprehensive Survey of Network Function Virtualization." Computer Networks, vol. 133, pp. 212–262, Março 2018.
   - DOI/URL validada: https://doi.org/10.1016/j.comnet.2018.01.021 (https://www.sciencedirect.com/science/article/abs/pii/S1389128618300306) — ~716 citações.
   - IMPORTÂNCIA: Sua discussão aprofundada de algoritmos de VNF placement, scheduling, migração e chaining revela as métricas e estados cujos desvios constituem anomalias operacionais rastreáveis por LLM.
   - CONTRIBUIÇÃO: Fornece survey abrangente de NFV cobrindo motivações, arquitetura, e o estado da arte em algoritmos de VNF (placement, scheduling, migração, chaining, multicast).

8. **Bhamare et al. (2016) — Survey on Service Function Chaining**
   - Citação: Bhamare, D., Jain, R., Samaka, M., Bhamare, G. "A Survey on Service Function Chaining." Journal of Network and Computer Applications, vol. 75, pp. 138–155, Novembro 2016.
   - DOI/URL validada: https://doi.org/10.1016/j.jnca.2016.09.001 (https://dl.acm.org/doi/10.1016/j.jnca.2016.09.001) — ~444 citações.
   - IMPORTÂNCIA: Como SFC encadeia VNFs via plano SDN, quebras de encadeamento ou roteamento anômalo são sinais de alta fidelidade para um LLM diagnosticar falhas de serviço.
   - CONTRIBUIÇÃO: Sintetiza a arquitetura de SFC e os esforços de padronização/implementação, servindo de base para compreender encadeamento de funções virtualizadas.

9. **Quinn & Nadeau (2015) — RFC 7498, SFC Problem Statement**
   - Citação: Quinn, P., Ed., Nadeau, T., Ed. "Problem Statement for Service Function Chaining." IETF RFC 7498, Abril 2015.
   - DOI/URL validada: https://doi.org/10.17487/RFC7498 (https://datatracker.ietf.org/doc/html/rfc7498) — norma IETF.
   - IMPORTÂNCIA: Define o problema de implantação de service functions (firewalls, load balancers) cujas falhas de encadeamento são anomalias de política que um LLM pode identificar no controlador SDN.
   - CONTRIBUIÇÃO: Estabelece o problema e a motivação padronizada para SFC no IETF, fundamentando arquiteturas de encadeamento de funções de rede.

10. **Pham et al. (2020) — Traffic-Aware and Energy-Efficient vNF Placement**
    - Citação: Pham, C., Tran, N. H., Ren, S., Saad, W., Hong, C. S. "Traffic-Aware and Energy-Efficient vNF Placement for Service Chaining: Joint Sampling and Matching Approach." IEEE Transactions on Services Computing, vol. 13, no. 1, pp. 172–185, Jan.-Fev. 2020 (publicado online 20/Fev/2017).
    - DOI/URL validada: https://doi.org/10.1109/TSC.2017.2671867 (https://ieeexplore.ieee.org/document/7859379/) — ~382 citações.
    - IMPORTÂNCIA: Formula o problema OPNET (custo operacional + tráfego) e mostra que decisões de placement têm impacto direto em latência/custo — desvios que um LLM pode detectar como anomalias de alocação em SDN.
    - CONTRIBUIÇÃO: Modela o placement de VNF para service chaining como problema NP-duro de otimização e propõe o algoritmo SAMA (sampling + matching), reduzindo o custo total em até 19%.

11. **Sun et al. (2022) — A Survey on the Placement of Virtual Network Functions**
    - Citação: Sun, J., Zhang, Y., Liu, F. "A Survey on the Placement of Virtual Network Functions." Journal of Network and Computer Applications, vol. 202, art. 103361, Março 2022.
    - DOI/URL validada: https://doi.org/10.1016/j.jnca.2022.103361 (https://www.sciencedirect.com/science/article/abs/pii/S1084804522000285) — ~65 citações.
    - IMPORTÂNCIA: Ao sistematizar o VNF placement problem (modelos de chaining, placing, embedding, restrições), classifica os vetores de falha de alocação que um LLM pode aprender como padrões anômalos.
    - CONTRIBUIÇÃO: Oferece survey dedicado e taxonômico do problema de placement de VNFs, unificando definições e abordagens para encadeamento e alocação de funções.

12. **Yilma et al. (2020) — Benchmarking Open Source NFV MANO: OSM and ONAP**
    - Citação: Yilma, G. M., Yousaf, Z. F., Sciancalepore, V., Costa-Perez, X. "Benchmarking Open Source NFV MANO Systems: OSM and ONAP." Computer Communications, vol. 161, pp. 86–98, 1 Setembro 2020.
    - DOI/URL validada: https://doi.org/10.1016/j.comcom.2020.07.013 (https://www.sciencedirect.com/science/article/abs/pii/S0140366420305946) — ~88 citações.
    - IMPORTÂNCIA: Revela lacunas entre o que OSM/ONAP prometem e o que efetivamente suportam (TRL, eficiência operacional), evidenciando que a instabilidade de orquestradores reais é fonte contínua de anomalias para um LLM monitorar.
    - CONTRIBUIÇÃO: Introduz uma metodologia formal de benchmarking e KPIs para sistemas MANO e compara empiricamente as duas principais plataformas open-source (OSM e ONAP) usando um vCPE.

13. **Kreutz et al. (2015) — Software-Defined Networking: A Comprehensive Survey** (contraparte SDN)
    - Citação: Kreutz, D., Ramos, F. M. V., Verissimo, P. E., Rothenberg, C. E., Azodolmolky, S., Uhlig, S. "Software-Defined Networking: A Comprehensive Survey." Proceedings of the IEEE, vol. 103, no. 1, pp. 14–76, Janeiro 2015.
    - DOI/URL validada: https://doi.org/10.1109/JPROC.2014.2371999 (https://orbilu.uni.lu/handle/10993/20596) — ~7.679 citações.
    - IMPORTÂNCIA: Ao detalhar a separação plano de controle/plano de dados e os desafios de segurança do SDN, fornece o substrato conceitual sobre o qual anomalias de controlador podem ser correlacionadas com falhas de VNF por um LLM.
    - CONTRIBUIÇÃO: É o survey definitivo de SDN (arquitetura, northbound/southbound, segurança, desafios), essencial para entender a camada de controle que coexiste e orquestra NFV.

---

## Resumo de validação
- 13 referências, todas verificadas por web_search/web_extract em 13/jul/2026 (URLs/PDFs do ETSI, IEEE, Elsevier/ScienceDirect, IETF, ACM DL acessíveis e confirmados).
- Cobertura exigida: White Paper ETSI NFV 2012 (1), Arquitetura NFV (2), ETSI MANO (3), Survey Mijumbi 2016 (4), Challenges/Han (5), vEPC/Hawilo (6), Surveys NFV (7,11), SFC (8,9), VNF Placement (10,11), Orquestração OSM/ONAP (12), e contraparte SDN (13).
- Nenhuma referência inventada; DOIs e URLs reais incluídos.
