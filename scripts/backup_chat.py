#!/usr/bin/env python3
"""
Script de backup do histórico de conversas do Antigravity para o repositório NetSpot.
Copia os logs brutos de todas as sessões ativas para .agents/historico_chat/ (ignorado pelo .gitignore),
mantendo cada conversa preservada em sua própria subpasta e o arquivo mais recente na raiz de historico_chat.
"""

import glob
import json
import os
import shutil
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST_DIR = os.path.join(BASE_DIR, ".agents", "historico_chat")
BRAIN_DIR = os.path.expanduser("~/.gemini/antigravity/brain")


def get_all_user_conversation_dirs():
    """Localiza todos os diretórios de conversas principais com interações USER_EXPLICIT."""
    pattern = os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl")
    candidates = glob.glob(pattern)
    if not candidates:
        return []

    valid_dirs = []
    for transcript_path in candidates:
        try:
            with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
                head = f.read(65536)
                if '"USER_EXPLICIT"' in head:
                    conv_dir = os.path.dirname(os.path.dirname(os.path.dirname(transcript_path)))
                    logs_dir = os.path.dirname(transcript_path)
                    mtime = os.path.getmtime(transcript_path)
                    valid_dirs.append({
                        "conv_id": os.path.basename(conv_dir),
                        "logs_dir": logs_dir,
                        "mtime": mtime,
                        "transcript_path": transcript_path
                    })
        except OSError:
            continue

    # Ordena da mais recente para a mais antiga
    valid_dirs.sort(key=lambda x: x["mtime"], reverse=True)
    return valid_dirs


def resolve_source_dir() -> str:
    """Localiza dinamicamente o diretório de logs da conversa principal mais recente."""
    explicit_dir = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ANTIGRAVITY_LOG_DIR")
    if explicit_dir:
        return explicit_dir
    user_convs = get_all_user_conversation_dirs()
    if user_convs:
        return user_convs[0]["logs_dir"]
    return ""



def sync_chat_backup():
    os.makedirs(DEST_DIR, exist_ok=True)
    user_convs = get_all_user_conversation_dirs()

    if not user_convs:
        print(f"[AVISO] Nenhuma conversa com interações de usuário encontrada em {BRAIN_DIR}")
        return False

    synced_count = 0
    sessions_manifest = []

    for idx, conv in enumerate(user_convs):
        conv_id = conv["conv_id"]
        logs_dir = conv["logs_dir"]
        target_conv_dir = os.path.join(DEST_DIR, conv_id)
        os.makedirs(target_conv_dir, exist_ok=True)

        is_latest = (idx == 0)
        copied_files = []

        for fname in ["transcript.jsonl", "transcript_full.jsonl"]:
            src_path = os.path.join(logs_dir, fname)
            if os.path.isfile(src_path):
                # 1. Copia para a subpasta isolada da conversa
                dst_conv = os.path.join(target_conv_dir, fname)
                shutil.copy2(src_path, dst_conv)
                copied_files.append(fname)

                # 2. Se for a sessão mais recente, copia também para a raiz de historico_chat (compatibilidade)
                if is_latest:
                    dst_root = os.path.join(DEST_DIR, fname)
                    shutil.copy2(src_path, dst_root)

        mod_time_str = datetime.fromtimestamp(conv["mtime"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        sessions_manifest.append({
            "conv_id": conv_id,
            "last_modified": mod_time_str,
            "is_active_session": is_latest,
            "files": copied_files
        })
        synced_count += 1
        print(f"[OK] Sessão sincronizada: {conv_id} ({mod_time_str}) -> .agents/historico_chat/{conv_id}/")

    # Catalogar também sessões históricas arquivadas em DEST_DIR que não estavam na lista ativa
    synced_ids = {c["conv_id"] for c in sessions_manifest}
    for item in os.listdir(DEST_DIR):
        item_path = os.path.join(DEST_DIR, item)
        if os.path.isdir(item_path) and item not in synced_ids:
            archived_transcript = os.path.join(item_path, "transcript.jsonl")
            if os.path.isfile(archived_transcript):
                archived_files = [f for f in ["transcript.jsonl", "transcript_full.jsonl"] if os.path.isfile(os.path.join(item_path, f))]
                mtime = os.path.getmtime(archived_transcript)
                mod_time_str = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                sessions_manifest.append({
                    "conv_id": item,
                    "last_modified": mod_time_str,
                    "is_active_session": False,
                    "files": archived_files
                })

    # Ordena o manifesto do mais recente para o mais antigo
    sessions_manifest.sort(key=lambda x: x["last_modified"], reverse=True)

    # Salva manifesto de sessões
    manifest_path = os.path.join(DEST_DIR, "manifesto_sessoes.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(sessions_manifest, f, indent=2, ensure_ascii=False)

    print(f"[SUCESSO] Total de {len(sessions_manifest)} sessões registradas no manifesto ({synced_count} sincronizadas agora)")
    return True


if __name__ == "__main__":
    success = sync_chat_backup()
    sys.exit(0 if success else 1)
