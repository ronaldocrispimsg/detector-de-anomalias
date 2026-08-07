import os
import json
import sys
import csv
import urllib.request
import urllib.error
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Caminho para o dataset definitivo
DATASET_PATH = os.path.join(os.path.dirname(__file__), "src", "dataset.csv")

def carregar_e_processar_csv(filepath: str):
    """
    Lê o dataset de telemetria CSV e converte linhas/cenários em documentos textuais estruturados.
    """
    if not os.path.exists(filepath):
        print(f"❌ Arquivo de dataset não encontrado em: {filepath}")
        sys.exit(1)

    print(f"📖 Lendo dataset CSV: {filepath}")
    
    cenarios = {}
    total_linhas = 0

    with open(filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_linhas += 1
            scenario = row.get("scenario", "UNKNOWN")
            if scenario not in cenarios:
                cenarios[scenario] = []
            cenarios[scenario].append(row)

    print(f"✅ Total de registros lidos: {total_linhas} em {len(cenarios)} cenários distintos.\n")

    # Gera textos descritivos e informativos para cada cenário
    documentos_textuais = []

    for scenario, rows in cenarios.items():
        # Cálculo de métricas médias do cenário
        num_recs = len(rows)
        avg_latency = sum(float(r["latency_ms"]) for r in rows) / num_recs
        avg_loss = sum(float(r["packet_loss_pct"]) for r in rows) / num_recs
        avg_cpu = sum(float(r["cpu_usage_pct"]) for r in rows) / num_recs
        avg_ram = sum(float(r["ram_usage_pct"]) for r in rows) / num_recs
        avg_net_in = sum(float(r["network_in_bps"]) for r in rows) / num_recs / (1024 * 1024) # Mbps
        avg_net_out = sum(float(r["network_out_bps"]) for r in rows) / num_recs / (1024 * 1024) # Mbps
        avg_conns = sum(float(r["active_connections"]) for r in rows) / num_recs
        
        status_codes = list(set(r["http_status_code"] for r in rows))

        relatorio_cenario = f"""CENÁRIO DE TELEMETRIA E INCIDENTE: {scenario}
Descrição do Evento: Análise dos logs de métricas do sistema para o cenário de eventos '{scenario}'.
Total de Registros Amostrados: {num_recs}
Métricas Médias Observadas:
- Latência de Rede: {avg_latency:.2f} ms
- Perda de Pacotes: {avg_loss:.2f}%
- Uso de CPU: {avg_cpu:.2f}%
- Uso de RAM: {avg_ram:.2f}%
- Tráfego Entrada (Net In): {avg_net_in:.2f} Mbps
- Tráfego Saída (Net Out): {avg_net_out:.2f} Mbps
- Conexões Ativas: {avg_conns:.1f}
- Códigos HTTP Retornados: {', '.join(status_codes)}

Amostra de Logs Individuais de Telemetria ({scenario}):
"""
        # Adiciona amostras de registros para detalhamento
        for r in rows[:10]:
            relatorio_cenario += f"• [Timestamp {r['timestamp']}] Latência={r['latency_ms']}ms | Loss={r['packet_loss_pct']}% | CPU={r['cpu_usage_pct']}% | RAM={r['ram_usage_pct']}% | NetIn={float(r['network_in_bps'])/(1024*1024):.2f}Mbps | NetOut={float(r['network_out_bps'])/(1024*1024):.2f}Mbps | HTTP={r['http_status_code']} | Conns={r['active_connections']}\n"
        
        documentos_textuais.append(relatorio_cenario)

    # Documento consolidado geral
    resumo_geral = f"RESUMO GERAL DO DATASET DE TELEMETRIA DE REDE E SISTEMA\n"
    resumo_geral += f"Total de amostras analisadas no dataset: {total_linhas} linhas.\n"
    resumo_geral += f"Cenários identificados no dataset: {', '.join(cenarios.keys())}.\n"
    documentos_textuais.append(resumo_geral)

    return "\n\n=========================================\n\n".join(documentos_textuais)


def executar_pipeline_rag(pergunta: str):
    print("=" * 70)
    print("🚀 PIPELINE RAG ALIMENTADO PELO DATASET DEFINITIVO (src/dataset.csv)")
    print("=" * 70)
    print(f"❓ Pergunta do Usuário: '{pergunta}'\n")

    # -------------------------------------------------------------------------
    # ETAPA 1: Preparação e Chunking do Dataset CSV
    # -------------------------------------------------------------------------
    print("--- ETAPA 1: Preparação e Chunking dos Dados do Dataset CSV ---")
    texto_base = carregar_e_processar_csv(DATASET_PATH)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=80,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )

    chunks = text_splitter.split_text(texto_base)
    print(f"✅ Dataset transformado e dividido em {len(chunks)} chunks de alta relevância:")
    for i, chunk in enumerate(chunks[:5], 1):
        print(f"   [Chunk {i}] ({len(chunk)} caract):")
        preview = chunk.replace('\n', ' ')
        print(f"      \"{preview[:110]}...\"")
    if len(chunks) > 5:
        print(f"   ... e mais {len(chunks) - 5} chunks.")
    print()

    # -------------------------------------------------------------------------
    # ETAPA 2 & 3: Embeddings & Banco Vetorial (ChromaDB)
    # -------------------------------------------------------------------------
    print("--- ETAPA 2 & 3: Embeddings & Banco Vetorial (ChromaDB) ---")
    print("Vetorizando chunks do dataset e indexando no ChromaDB...\n")

    default_ef = embedding_functions.DefaultEmbeddingFunction()
    chroma_client = chromadb.Client()
    collection_name = "telemetria_dataset_rag"

    try:
        chroma_client.delete_collection(collection_name)
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name=collection_name,
        embedding_function=default_ef
    )

    ids = [f"telemetry_chunk_{i+1}" for i in range(len(chunks))]
    metadatas = [{"source": "src/dataset.csv", "chunk_index": i+1} for i in range(len(chunks))]

    collection.add(
        documents=chunks,
        metadatas=metadatas,
        ids=ids
    )
    print(f"✅ {len(chunks)} vetores armazenados com sucesso na coleção '{collection_name}' do ChromaDB!\n")

    # -------------------------------------------------------------------------
    # ETAPA 4: A Busca (Retrieval)
    # -------------------------------------------------------------------------
    print("--- ETAPA 4: A Busca (Retrieval Semântico) ---")
    print(f"Buscando chunks relevantes para a pergunta: '{pergunta}'...\n")

    results = collection.query(
        query_texts=[pergunta],
        n_results=3
    )

    retrieved_chunks = results['documents'][0]
    distances = results['distances'][0]
    retrieved_ids = results['ids'][0]

    print("✅ Top Chunks Recuperados do ChromaDB:")
    contexto_formatado = ""
    for idx, (c_id, doc, dist) in enumerate(zip(retrieved_ids, retrieved_chunks, distances), 1):
        print(f"   [{idx}] ID: {c_id} | Distância Vetorial: {dist:.4f}")
        print(f"       Resumo: \"{doc.replace(chr(10), ' ')[:120]}...\"")
        contexto_formatado += f"\n--- Chunk Recuperado {idx} ---\n{doc}\n"
    print()

    # -------------------------------------------------------------------------
    # ETAPA 5: Geração com Qwen 2.5:7B
    # -------------------------------------------------------------------------
    print("--- ETAPA 5: Geração com Qwen 2.5:7B ---")
    
    prompt_final = f"""Baseado APENAS nos dados de telemetria do dataset fornecido no contexto, responda de forma técnica, quantitativa e objetiva à pergunta do usuário.

Contexto dos Logs do Dataset (ChromaDB):
{contexto_formatado}

Pergunta do Usuário:
{pergunta}

Resposta Diagnóstica:"""

    print("📄 Prompt Formato Final enviado ao LLM:\n")
    print("-" * 50)
    print(prompt_final)
    print("-" * 50)
    print("\n⏳ Conectando ao Ollama (Modelo: qwen2.5:7b)...")

    resposta_llm = None
    try:
        url = "http://localhost:11434/api/generate"
        payload = json.dumps({
            "model": "qwen2.5:7b",
            "prompt": prompt_final,
            "stream": False
        }).encode('utf-8')

        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode('utf-8'))
                resposta_llm = data.get("response")
    except Exception as e:
        print(f"ℹ️ Conexão direta com Ollama em http://localhost:11434 não concluída ({e}).")

    print("\n🤖 RESPOSTA GERADA PELO QWEN 2.5:7B (DIAGNÓSTICO):")
    print("=" * 70)
    if resposta_llm:
        print(resposta_llm.strip())
    else:
        print("[Análise Diagnóstica Fundamentada no Dataset src/dataset.csv]")
        print("Com base nos dados reais recuperados do dataset:")
        for doc in retrieved_chunks:
            print(f"\n- {doc.strip()}")
    print("=" * 70)

if __name__ == "__main__":
    pergunta_padrao = "Quais os impactos de rede, CPU e erros HTTP observados no cenário de DDOS_ATTACK?"
    if len(sys.argv) > 1:
        pergunta_padrao = " ".join(sys.argv[1:])
    executar_pipeline_rag(pergunta_padrao)
