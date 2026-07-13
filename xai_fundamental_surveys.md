# Fundamentos e Surveys de XAI (Explainable AI) — Referências Validadas

Lista de referências REAIS (surveys, taxonomias e métodos fundamentais de XAI, incluindo NLP e LIME/SHAP/attention). Todas validadas por URL/DOI real.

## Obrigatórias (validadas)

1. **Danilevsky, M., Qian, K., Aharonov, R., Katsis, Y., Kawas, B., & Sen, P. (2020).** *A Survey of the State of Explainable AI for Natural Language Processing.* AACL-IJCNLP 2020. arXiv:2010.00711. DOI: https://doi.org/10.18653/v1/2020.aacl-main.46 | https://arxiv.org/abs/2010.00711
   - Relevância: Survey dedicado especificamente a XAI no domínio de NLP, com taxonomia de explicações e técnicas de interpretabilidade para modelos de linguagem.

2. **Arrieta, A. B., Díaz-Rodríguez, N., Del Ser, J., Bennetot, A., Tabik, S., Barbado, A., ... & Herrera, F. (2020).** *Explainable Artificial Intelligence (XAI): Concepts, Taxonomies, Opportunities and Challenges toward Responsible AI.* Information Fusion, 58, 82–115. Elsevier. DOI: https://doi.org/10.1016/j.inffus.2019.12.012 | https://www.sciencedirect.com/science/article/pii/S1566253519308103
   - Relevância: Uma das taxonomias de XAI mais citadas, organizando a literatura em duas taxonomias (modelos gerais e deep learning) rumo a Responsible AI.

3. **Adadi, A., & Berrada, M. (2018).** *Peeking Inside the Black-Box: A Survey on Explainable Artificial Intelligence (XAI).* IEEE Access, 6, 52138–52160. IEEE. DOI: https://doi.org/10.1109/ACCESS.2018.2870052 | https://ieeexplore.ieee.org/document/8466590
   - Relevância: Survey introdutório holístico de XAI, com classificação de abordagens e discussão de tendências e questões em aberto.

4. **Guidotti, R., Monreale, A., Ruggieri, S., Turini, F., Giannotti, F., & Pedreschi, D. (2018/2019).** *A Survey of Methods for Explaining Black Box Models.* ACM Computing Surveys, 51(5), 1–42. ACM. DOI: https://doi.org/10.1145/3236009 | https://dl.acm.org/doi/10.1145/3236009
   - Relevância: Classificação sistemática dos problemas de explicação de black boxes por tipo de modelo e tipo de explicação desejada.

5. **Molnar, C. (2020/2022).** *Interpretable Machine Learning: A Guide for Making Black Box Models Explainable.* 2ª ed., christophm.github.io. https://christophm.github.io/interpretable-ml-book/ (PDF: https://originalstatic.aminer.cn/misc/pdf/Molnar-interpretable-machine-learning_compressed.pdf)
   - Relevância: Livro de referência aberto cobrindo métodos model-agnostic (incluindo LIME e SHAP) e princípios de interpretabilidade.

6. **Ribeiro, M. T., Singh, S., & Guestrin, C. (2016).** *"Why Should I Trust You?": Explaining the Predictions of Any Classifier.* KDD 2016. arXiv:1602.04938. DOI: https://doi.org/10.1145/2939672.2939778 (KDD) | https://arxiv.org/abs/1602.04938
   - Relevância: Introduz o LIME (Local Interpretable Model-agnostic Explanations), método local modelo-independente para explicar predições.

7. **Lundberg, S. M., & Lee, S.-I. (2017).** *A Unified Approach to Interpreting Model Predictions.* NeurIPS 2017. arXiv:1705.07874. DOI: https://doi.org/10.48550/arXiv.1705.07874 | https://arxiv.org/abs/1705.07874
   - Relevância: Introduz o SHAP (SHapley Additive exPlanations), unificando seis métodos de atribuição de importância sob estrutura de valores de Shapley.

8. **Gilpin, L. H., Bau, D., Yuan, B. Z., Bajwa, A., Specter, M., & Kagal, L. (2018).** *Explaining Explanations: An Overview of Interpretability of Machine Learning.* IEEE DSAA 2018. arXiv:1806.00069. DOI: https://doi.org/10.1109/DSAA.2018.00018 | https://arxiv.org/abs/1806.00069
   - Relevância: Discute definições de explicabilidade e classifica a literatura, apontando lacunas em métodos para redes neurais profundas.

9. **Samek, W., Montavon, G., Vedaldi, A., Hansen, L. K., & Müller, K.-R. (eds.) (2019).** *Explainable AI: Interpreting, Explaining and Visualizing Deep Learning.* Springer Lecture Notes in Computer Science, vol. 11700. ISBN 978-3-030-28954-6. DOI: https://doi.org/10.1007/978-3-030-28954-6 | https://dl.acm.org/doi/10.5555/3365202
   - Relevância: Livro/editado pela Springer reunindo métodos de interpretação, explicação e visualização de deep learning.

10. **Montavon, G., Samek, W., & Müller, K.-R. (2018).** *Methods for Interpreting and Understanding Deep Neural Networks.* Digital Signal Processing, 73, 1–15. Elsevier. DOI: https://doi.org/10.1016/j.dsp.2017.10.011 | https://www.sciencedirect.com/science/article/pii/S1051200417302385
    - Relevância: Revisão de métodos de interpretação de DNNs, com ênfase em Layer-wise Relevance Propagation (LRP) e decomposição de Taylor.

## Adicionais (para reforçar o corpus, todas validadas)

11. **Doshi-Velez, F., & Kim, B. (2017).** *Towards A Rigorous Science of Interpretable Machine Learning.* arXiv:1702.08608. DOI: https://doi.org/10.48550/arXiv.1702.08608 | https://arxiv.org/abs/1702.08608
    - Relevância: Position paper fundando a taxonomia de avaliação de interpretabilidade (application, human, functionality) e o rigor científico da área.

12. **Bodria, F., Giannotti, F., Guidotti, R., Naretto, F., Pedreschi, D., & Rinzivillo, S. (2021/2023).** *Benchmarking and Survey of Explanation Methods for Black Box Models.* Data Mining and Knowledge Discovery, 37, 1712–1769. Springer. arXiv:2102.13076. DOI: https://doi.org/10.1007/s10618-023-00933-9 | https://arxiv.org/abs/2102.13076
    - Relevância: Survey recente com benchmarking empírico de métodos de explicação modelo-agostic e específicos.

13. **Linardatos, P., Papastefanopoulos, V., & Kotsiantis, S. (2021).** *Explainable AI: A Review of Machine Learning Interpretability Methods.* Entropy, 23(1), 18. MDPI. DOI: https://doi.org/10.3390/e23010018 | https://www.mdpi.com/1099-4300/23/1/18
    - Relevância: Revisão e taxonomia de métodos de interpretabilidade de ML com links para implementações.

14. **Tjoa, E., & Guan, C. (2021).** *A Survey on Explainable Artificial Intelligence (XAI): Toward Medical XAI.* IEEE Transactions on Neural Networks and Learning Systems, 32(11), 4793–4813. IEEE. DOI: https://doi.org/10.1109/TNNLS.2020.3027314 | https://arxiv.org/abs/2007.15998
    - Relevância: Survey de XAI com foco em aplicações médicas e requisitos de confiabilidade/regulatórios.

15. **Jain, S., & Wallace, B. C. (2019).** *Attention is not Explanation.* NAACL-HLT 2019, pp. 3543–3556. ACL. DOI: https://doi.org/10.18653/v1/N19-1357 | https://aclanthology.org/N19-1357/
    - Relevância: Questiona criticamente se pesos de atenção em NLP constituem explicação válida (ensaio fundamental sobre attention interpretability).

16. **Wiegreffe, S., & Pinter, Y. (2019).** *Attention is not not Explanation.* EMNLP-IJCNLP 2019. arXiv:1908.04626. DOI: https://doi.org/10.18653/v1/D19-1002 | https://arxiv.org/abs/1908.04626
    - Relevância: Réplica aos achados de Jain & Wallace, defendendo condições sob as quais atenção pode servir como explicação em NLP.

17. **Adebayo, J., Gilmer, J., Muelly, M., Goodfellow, I., Hardt, M., & Kim, B. (2018).** *Sanity Checks for Saliency Maps.* ICLR 2018 / NeurIPS 2018. arXiv:1810.03292. https://arxiv.org/abs/1810.03292 (proc. NeurIPS: papers.neurips.cc/paper/8160)
    - Relevância: Demonstra que muitos métodos de saliência falham em testes de sanidade, balizando a validação de explicações baseadas em atribuição.

---
Total: 17 referências (≥14 exigidas). Todas com URL/DOI real verificado.
