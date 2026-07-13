# Referências sobre LLMs em Segurança/SOC, Calibração/Confiança e Explicação por Cadeia de Raciocínio

Lista curada e validada (≥14 referências REAIS). Todos os URLs/DOIs verificados em 13/07/2026.
Organizada em 3 eixos: (A) LLMs em segurança/SOC/NOC e explicabilidade; (B) Calibração e confiança de modelos; (C) Justificativa textual / cadeia de raciocínio como explicação.

---

## A. LLMs em Segurança Cibernética / SOC / NOC e Explicabilidade

1. **Large Language Models in Cybersecurity: State-of-the-Art**
   Autores: Farzad Nourmohammadzadeh Motlagh, Mehrdad Hajizadeh, Mehryar Majd, Pejman Najafi, Feng Cheng, Christoph Meinel
   Ano: 2024 | Veículo: arXiv:2402.00891 (cs.CR)
   URL: https://arxiv.org/abs/2402.00891 | DOI: https://doi.org/10.48550/arXiv.2402.00891
   Relevância: Revisão abrangente das aplicações defensivas e adversariais de LLMs em segurança cibernética, mapeando o estado da arte e lacunas de pesquisa.

2. **LLMs in the SOC: An Empirical Study of Human-AI Collaboration in Security Operations Centres**
   Autores: Ronal Singh, Shahroz Tariq, Fatemeh Jalalvand, Mohan Baruwal Chhetri, Surya Nepal, Cecile Paris, Martin Lochner
   Ano: 2025 | Veículo: arXiv:2508.18947 (cs.CR)
   URL: https://arxiv.org/abs/2508.18947 | DOI: https://doi.org/10.48550/arXiv.2508.18947
   Relevância: Estudo longitudinal de 3.090 consultas de 45 analistas SOC, mostrando que LLMs atuam como apoio cognitivo sob demanda, preservando a autoridade de decisão do analista.

3. **AI-Augmented SOC: A Survey of LLMs and Agents for Security Automation**
   Autores: Siddhant Srinivas, Brandon Kirk, Julissa Zendejas, Michael Espino, Matthew Boskovich, Abdul Bari, Khalil Dajani, Nabeel Alzahrani
   Ano: 2025 | Veículo: Journal of Cybersecurity and Privacy, 5(4), 95 (MDPI)
   URL: https://www.mdpi.com/2624-800X/5/4/95 | DOI: https://doi.org/10.3390/jcp5040095
   Relevância: Survey de LLMs/agentes em funções SOC (triage de alertas, inteligência de ameaças, resposta a incidentes), com taxonomia e discussão de interpretabilidade e alucinações.

4. **Explainable AI for cybersecurity automation, intelligence and trustworthiness in digital twin: Methods, taxonomy, challenges and prospects**
   Autores: Iqbal H. Sarker, Helge Janicke, Ahmad Mohsin, Asif Gill, Leandros Maglaras
   Ano: 2024 | Veículo: ICT Express, 10(4), 935–958 (Elsevier)
   URL: https://www.sciencedirect.com/science/article/pii/S2405959524000572 | DOI: https://doi.org/10.1016/j.icte.2024.05.007
   Relevância: Estudo de XAI para modelagem de segurança cibernética, com taxonomia que auxilia analistas a compreender ameaças e anomalias de forma confiável.

5. **EXPLICATE: Enhancing Phishing Detection through Explainable AI and LLM-Powered Interpretability**
   Autores: Bryan Lim, Roman Huerta, Alejandro Sotelo, Anthonie Quintela, Priyanka Kumar
   Ano: 2025 | Veículo: arXiv:2503.20796 (cs.CR)
   URL: https://arxiv.org/abs/2503.20796 | DOI: https://doi.org/10.48550/arXiv.2503.20796
   Relevância: Framework que usa LLM para traduzir explicações de LIME/SHAP em linguagem natural acessível, fechando a lacuna entre IA automatizada e confiança do usuário em detecção de phishing.

---

## B. Calibração e Confiança de Modelos (especialmente LLMs)

6. **Language Models (Mostly) Know What They Know**  *(OBRIGATÓRIO)*
   Autores: Saurav Kadavath, Tom Conerly, Amanda Askell, Tom Henighan, et al. (Jared Kaplan, último autor)
   Ano: 2022 | Veículo: arXiv:2207.05221 (cs.CL)
   URL: https://arxiv.org/abs/2207.05221 | DOI: https://doi.org/10.48550/arXiv.2207.05221
   Relevância: Trabalho fundacional sobre calibração de LLMs via autoavaliação P(True) e P(IK); base para compreender quando o modelo sabe o que afirma.

7. **Just Ask for Calibration: Strategies for Eliciting Calibrated Confidence Scores from Language Models Fine-Tuned with Human Feedback**  *(OBRIGATÓRIO)*
   Autores: Katherine Tian, Eric Mitchell, Allan Zhou, Archit Sharma, Rafael Rafailov, Huaxiu Yao, Chelsea Finn, Christopher D. Manning
   Ano: 2023 | Veículo: Proceedings of EMNLP 2023
   URL: https://arxiv.org/abs/2305.14975 | DOI: https://doi.org/10.48550/arXiv.2305.14975
   Relevância: Mostra que confiança verbalizada ("just ask") é melhor calibrada que probabilidades condicionais em modelos RLHF (ChatGPT, GPT-4, Claude), reduzindo erro de calibração em ~50%.

8. **On the Calibration of Large Language Models and Alignment**  *(OBRIGATÓRIO)*
   Autores: Chiwei Zhu, Benfeng Xu, Quan Wang, Yongdong Zhang, Zhendong Mao
   Ano: 2023 | Veículo: Findings of EMNLP 2023, pp. 9778–9795
   URL: https://arxiv.org/abs/2311.13240 | DOI: https://doi.org/10.48550/arXiv.2311.13240 (ACL: 10.18653/v1/2023.findings-emnlp.654)
   Relevância: Exame sistemático de como pré-treinamento e alinhamento (RLHF) afetam a calibração de LLMs em geração, facticidade e compreensão.

9. **A Survey of Confidence Estimation and Calibration in Large Language Models**  *(OBRIGATÓRIO)*
   Autores: Jiahui Geng, Fengyu Cai, Yuxia Wang, Heinz Koeppl, Preslav Nakov, Iryna Gurevych
   Ano: 2023 | Veículo: arXiv:2311.08298 (cs.CL)
   URL: https://arxiv.org/abs/2311.08298 | DOI: https://doi.org/10.48550/arXiv.2311.08298
   Relevância: Survey abrangente das técnicas de estimativa de confiança e calibração em LLMs, organizando avanços e aplicações.

10. **The Internal State of an LLM Knows When It's Lying**
    Autores: Amos Azaria, Tom Mitchell
    Ano: 2023 | Veículo: Findings of EMNLP 2023
    URL: https://arxiv.org/abs/2304.13734 | DOI: https://doi.org/10.48550/arXiv.2304.13734
    Relevância: Demonstra que classificadores sobre ativações ocultas dos LLMs detectam a veracidade de afirmações (71–83% de acurácia), útil para sinalizar confiança em respostas de segurança.

11. **Do Large Language Models Know What They Don't Know?**
    Autores: Zhangyue Yin, Qiushi Sun, Qipeng Guo, Jiawen Wu, Xipeng Qiu, Xuanjing Huang
    Ano: 2023 | Veículo: Findings of ACL 2023, pp. 8653–8665
    URL: https://arxiv.org/abs/2305.18153 | DOI: https://doi.org/10.48550/arXiv.2305.18153
    Relevância: Introduz o dataset SelfAware e mede a auto-conhecimento ("self-knowledge") de LLMs sobre o que não sabem — central para deferral a analistas humanos.

---

## C. Justificativa Textual / Cadeia de Raciocínio como Explicação

12. **Chain-of-Thought Prompting Elicits Reasoning in Large Language Models**  *(OBRIGATÓRIO)*
    Autores: Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, Fei Xia, Ed Chi, Quoc Le, Denny Zhou
    Ano: 2022 | Veículo: NeurIPS 2022
    URL: https://arxiv.org/abs/2201.11903 | DOI: https://doi.org/10.48550/arXiv.2201.11903
    Relevância: Introduz o Chain-of-Thought (CoT), cujas justificativas textuais passo-a-passo servem como explicação legível para analistas sobre o raciocínio do modelo.

13. **Measuring Faithfulness in Chain-of-Thought Reasoning**
    Autores: Tamera Lanham, Anna Chen, Ansh Radhakrishnan, Benoit Steiner, Carson Denison, et al. (Ethan Perez, Samuel R. Bowman)
    Ano: 2023 | Veículo: arXiv:2307.13702 (cs.AI)
    URL: https://arxiv.org/abs/2307.13702 | DOI: https://doi.org/10.48550/arXiv.2307.13702
    Relevância: Investiga se o CoT é uma explicação fiel do raciocínio real do modelo; essencial para confiar em justificativas textuais em decisões de alto risco.

14. **Faithful Chain-of-Thought Reasoning**
    Autores: Qing Lyu, Shreya Havaldar, Adam Stein, Li Zhang, Delip Rao, Eric Wong, Heng Huang, Marianna Apidianaki, Chris Callison-Burch
    Ano: 2023 | Veículo: IJCNLP-AACL 2023
    URL: https://arxiv.org/abs/2301.13379 | DOI: https://doi.org/10.48550/arXiv.2301.13379 (ACL: 10.18653/v1/2023.ijcnlp-main.20)
    Relevância: Propõe o "Faithful CoT", garantindo que a cadeia de raciocínio reflita um processo simbólico real, mitigando explicações enganosas em domínios críticos.

15. **Explainable AI for cybersecurity automation, intelligence and trustworthiness in digital twin** (vide item 4 — também cobre explicabilidade XAI para confiança de analistas)
    (Referência duplicada propositalmente para o eixo de confiança/explicação; ver item 4.)

16. **LLMs in the SOC: An Empirical Study of Human-AI Collaboration in Security Operations Centres** (vide item 2 — também evidencia necessidade de transparência/explicação para adoção)
    (Referência transversal; ver item 2.)

---

## Contagem por eixo
- A. Segurança/SOC/NOC + Explicabilidade: itens 1–5 (5 referências)
- B. Calibração/Confiança: itens 6–11 (6 referências, incluindo os 4 obrigatórios de calibração)
- C. Justificativa/CoT como explicação: itens 12–14 (3 referências, incluindo CoT e os 2 de faithfulness)

Total de referências únicas validadas: **14 primárias** (itens 1–14) + 2 transversais (15–16). Todos os itens 1–14 possuem URL/DOI real verificado.

## Obrigatórios atendidos
✅ Kadavath et al. 2022 — arXiv:2207.05221
✅ Tian et al. 2023 "Just Ask for Calibration" — arXiv:2305.14975
✅ Zhu et al. 2023 (On the Calibration of LLMs and Alignment) — arXiv:2311.13240
✅ Geng et al. 2023 (Survey of Confidence Estimation and Calibration) — arXiv:2311.08298
✅ Wei et al. 2022 Chain-of-Thought — arXiv:2201.11903
✅ Papers de LLMs em detecção de ameaças / apoio a analistas SOC — itens 1, 2, 3, 5
✅ Papers de confiança/transparência para analistas — itens 4, 10, 11
✅ Explainable LLM decision-making — itens 4, 5, 12, 13, 14
