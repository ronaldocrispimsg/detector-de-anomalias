# Como Funciona a Arquitetura RAG na Prática

Este repositório contém uma demonstração completa e prática da arquitetura **RAG (Retrieval-Augmented Generation)** utilizando **ChromaDB**, **LangChain**, e o modelo **Qwen 2.5:7B** (via Ollama local).

---

## 🏗️ As 5 Etapas do RAG na Prática

```mermaid
flowchart TD
    subgraph Ingestao ["1. Ingestão & Preparação"]
        A[Documentos Brutos: PDF/Texto] -->|LangChain TextSplitter| B[Chunks de 500-1000 Tokens]
    end

    subgraph Vetorizacao ["2 & 3. Vetorização & Armazenamento"]
        B -->|Modelo de Embedding: nomic-embed-text / MiniLM| C[Vetores Numéricos D-dim]
        C -->|Indexação| D[(Banco Vetorial ChromaDB)]
    end

    subgraph Consulta ["4. A Busca (Retrieval)"]
        E[Pergunta do Usuário] -->|Vetorização com mesmo Embedding| F[Vetor da Pergunta]
        F -->|Busca por Cosseno / Distância Euclidiana| D
        D -->|Retorna Top-K Chunks Relevantes| G[Contexto Selecionado]
    end

    subgraph Geracao ["5. Geração Aumentada"]
        G --> H[Prompt Formatado: Contexto + Pergunta]
        E --> H
        H -->|Envio de Prompt Delimitado| I[LLM: Qwen 2.5:7B]
        I --> J[Resposta Final Formada de Forma Humana]
    end
```

---

## 📁 Conteúdo do Repositório

- 🐍 **`rag_pipeline.py`**: Script Python autocontido que conecta LangChain, ChromaDB e Ollama local para executar todo o fluxo no terminal.
- 📋 **`requirements.txt`**: Requisitos do projeto Python (`chromadb`, `langchain-text-splitters`, `ollama`, `sentence-transformers`).
- 🌐 **`index.html` & `src/`**: Aplicação Web Interativa (RAG Playground) para visualizar interativamente cada uma das 5 etapas do RAG.

---

## 🚀 Como Executar o Script Python

### 1. Instalar as Dependências

```bash
pip install -r requirements.txt
```

### 2. (Opcional) Iniciar o Ollama com Qwen 2.5:7B

Caso deseje rodar a geração real com o LLM localmente:

```bash
# Baixar e rodar o Qwen 2.5 7B
ollama run qwen2.5:7b
```

### 3. Executar o Pipeline RAG

```bash
python rag_pipeline.py "Como funciona a nova política de férias e o fracionamento?"
```

---

## 💻 Como Executar o Visualizador Web Interativo

Para abrir o painel gráfico interativo no navegador:

```bash
# Opção 1: Usando Python HTTP Server
python3 -m http.server 8080

# Opção 2: Usando Npx Serve ou Live Server
npx serve .
```

Abra o seu navegador em `http://localhost:8080` para visualizar os chunks, os vetores do ChromaDB, a busca por similaridade e a geração do Qwen 2.5:7B!
