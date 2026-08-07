# NetSpot RAG Module - Arquitetura RAG na Prática (ChromaDB + LangChain)

Este diretório contém a demonstração e os módulos do **RAG (Retrieval-Augmented Generation)** utilizando **ChromaDB**, **LangChain**, o modelo **Qwen 2.5:7B** (via Ollama local) e a integração nativa com o **Classificador Híbrido de Anomalias do NetSpot**.

---

## 🏗️ As 5 Etapas do RAG na Prática

```mermaid
flowchart TD
    subgraph Ingestao ["1. Ingestão & Preparação"]
        A[Dataset Real de Anomalias: netspot_anomaly_dataset.csv] -->|LangChain TextSplitter| B[Chunks de Métricas & Diagnósticos]
    end

    subgraph Vetorizacao ["2 & 3. Vetorização & Armazenamento"]
        B -->|Modelo de Embedding: MiniLM / Sentence-Transformers| C[Vetores Numéricos D-dim]
        C -->|Indexação| D[(Banco Vetorial ChromaDB)]
    end

    subgraph Consulta ["4. A Busca (Retrieval)"]
        E[Métricas Simuladas no Front / API] -->|Vetorização da Telemetria| F[Vetor de Consulta]
        F -->|Busca por Cosseno / Distância Euclidiana| D
        D -->|Retorna Top-3 Vetores com Menor Distância| G[Contexto Enriquecido RAG]
    end

    subgraph Geracao ["5. Geração Aumentada (Motor Ensemble)"]
        G --> H[Prompt Formatado com Evidências Vetoriais]
        E --> H
        H -->|Classificação Ponderada (H 40%, ML 35%, LLM 25%)| I[Engine GenAI / Ollama Local]
        I --> J[Parecer Técnico + Causa Raiz + Playbook de Mitigação]
    end
```

---

## 📁 Conteúdo do Módulo RAG

- 🐍 **`rag_pipeline.py`**: Pipeline Python autocontido de testes RAG com LangChain, ChromaDB e Ollama.
- 📋 **`requirements.txt`**: Dependências Python do ecossistema RAG (`chromadb`, `langchain-text-splitters`, `ollama`, `sentence-transformers`).
- 🌐 **`index.html`**: Visualizador e Playground Web Interativo para simular as 5 etapas do RAG.
- 🔗 **Integrado ao Backend**: Código de produção localizado em `Backend/services/anomaly_classifier.py` (`RAGAnomalyRetriever`).

---

## 🚀 Como Executar o Script Python

### 1. Instalar as Dependências

```bash
pip install -r requirements.txt
```

### 2. (Opcional) Iniciar o Ollama com Qwen 2.5:7B

```bash
ollama run qwen2.5:7b
```

### 3. Executar o Pipeline RAG

```bash
python rag_pipeline.py "Como funciona a nova política de férias e o fracionamento?"
```

---

## 💻 Como Executar o Visualizador Web Interativo

Para abrir o painel gráfico interativo do RAG Playground no navegador:

```bash
python3 -m http.server 8085 --directory RAG
```

Acesse em **[http://localhost:8085](http://localhost:8085)** para inspecionar os chunks, embeddings do ChromaDB e o fluxo do Qwen 2.5:7B.
