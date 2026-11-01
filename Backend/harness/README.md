# Backend Harness: Avaliação Rigorosa e Benchmarking Científico

O diretório `Backend/harness/` fornece a infraestrutura experimental para avaliar modelos de detecção e classificação de anomalias sem viés ou vazamento de dados.

## Principais Módulos

- `baselines.py`: Execução dos baselines de referência (Heurística de NOC, Isolation Forest, Random Forest e XGBoost).
- `datasets.py` & `splits.py`: Particionamento sintético e temporal com faixas de severidade separadas entre treino e teste.
- `datasets_external.py`: Avaliação de generalização em benchmarks públicos (UNSW-NB15 e CSE-CIC-IDS2018).
- `metrics.py`: Implementação de Macro F1, Calibração ECE, Brier Score e tempo de inferência.
- `kathara/`: Runner de experimentos de ciclo fechado em ambiente emulado com Kathará.
- `report.py` & `repro.py`: Geração automatizada de tabelas e gráficos comparativos.

## Execução

```bash
# Rodar todos os baselines com sementes reprodutíveis
python scripts/eval_benchmarks.py

# Gerar gráficos e sumários para o artigo
python scripts/generate_article_stats.py
```
