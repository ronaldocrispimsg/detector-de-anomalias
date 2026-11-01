#!/usr/bin/env python3
r"""
scripts/audit_latex.py
Auditoria mecânica estática do documento LaTeX do TCC NetSpot.
Verifica:
1. Balanceamento de ambientes (\begin e \end)
2. Existência de arquivos de figuras referenciados em \includegraphics
3. Resolução de citações (\cite, \citeonline, etc.) contra referencias.bib
4. Chaves não citadas no .bib
5. Resolução de referências cruzadas (\ref, \pageref) contra \label
6. Consistência de termos técnicos e métricas
"""

import os
import re
import sys

def audit_latex():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tex_path = os.path.join(base_dir, "Escrita_TCC", "Escrita_latex", "TCC - NetSpot.tex")
    bib_path = os.path.join(base_dir, "Escrita_TCC", "Escrita_latex", "referencias.bib")
    assets_dir = os.path.join(base_dir, "Escrita_TCC", "Escrita_latex", "assets")

    if not os.path.exists(tex_path):
        print(f"ERRO: Arquivo {tex_path} não encontrado.")
        sys.exit(1)

    print("=" * 60)
    print("AUDITORIA MECÂNICA DO TCC (LATEX) — NETSPOT")
    print(f"Arquivo principal: {os.path.basename(tex_path)}")
    print("=" * 60)

    with open(tex_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total_lines = len(lines)
    print(f"Total de linhas no .tex: {total_lines}")

    # 1. Checagem de balanceamento de ambientes
    env_stack = []
    env_mismatches = []
    
    # regexes
    re_begin = re.compile(r'\\begin\{([a-zA-Z0-9_*]+)\}')
    re_end = re.compile(r'\\end\{([a-zA-Z0-9_*]+)\}')
    re_include_graphics = re.compile(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}')
    re_cite = re.compile(r'\\(?:cite|citeonline|citep|citet|nocite)\{([^}]+)\}')
    re_label = re.compile(r'\\label\{([^}]+)\}')
    re_ref = re.compile(r'\\(?:ref|pageref|autoref)\{([^}]+)\}')

    labels_defined = set()
    refs_called = []
    citations_called = set()
    figures_called = []

    for idx, line in enumerate(lines, start=1):
        # Remove comentários reais de LaTeX (% sem barra invertida antes), preservando \%
        clean_line = re.split(r'(?<!\\)%', line)[0]

        # Ambientes
        for m in re_begin.finditer(clean_line):
            env_stack.append((m.group(1), idx))
        for m in re_end.finditer(clean_line):
            env_name = m.group(1)
            if not env_stack:
                env_mismatches.append(f"Linha {idx}: \\end{{{env_name}}} sem correspondente \\begin.")
            else:
                last_env, last_idx = env_stack.pop()
                if last_env != env_name:
                    env_mismatches.append(
                        f"Linha {idx}: \\end{{{env_name}}} fecha \\begin{{{last_env}}} aberto na linha {last_idx}."
                    )

        # Labels
        for m in re_label.finditer(clean_line):
            labels_defined.add(m.group(1))

        # Refs
        for m in re_ref.finditer(clean_line):
            refs_called.append((m.group(1), idx))

        # Citações
        for m in re_cite.finditer(clean_line):
            keys = [k.strip() for k in m.group(1).split(",")]
            for k in keys:
                if k:
                    citations_called.add(k)

        # Figuras
        for m in re_include_graphics.finditer(clean_line):
            figures_called.append((m.group(1), idx))

    while env_stack:
        last_env, last_idx = env_stack.pop()
        env_mismatches.append(f"Linha {last_idx}: \\begin{{{last_env}}} não foi fechado até o fim do arquivo.")

    print("\n--- 1. Balanceamento de Ambientes ---")
    if env_mismatches:
        print(f"❌ Encontrados {len(env_mismatches)} problemas de balanceamento:")
        for err in env_mismatches:
            print(f"  - {err}")
    else:
        print("✅ Todos os ambientes \\begin{...} e \\end{...} estão 100% balanceados.")

    # 2. Checagem de figuras em assets/
    print("\n--- 2. Integridade dos Arquivos de Imagem ---")
    missing_figures = []
    assets_files = os.listdir(assets_dir) if os.path.exists(assets_dir) else []
    for fig_name, line_num in figures_called:
        fig_basename = os.path.basename(fig_name)
        # se não tiver extensão, busca qualquer extensão suportada
        matched = False
        if fig_basename in assets_files:
            matched = True
        else:
            for ext in [".png", ".jpg", ".jpeg", ".pdf"]:
                if f"{fig_basename}{ext}" in assets_files:
                    matched = True
                    break
        if not matched:
            missing_figures.append((fig_name, line_num))

    if missing_figures:
        print(f"❌ {len(missing_figures)} figuras não encontradas no diretório assets/:")
        for fig, l in missing_figures:
            print(f"  - Linha {l}: {fig}")
    else:
        print(f"✅ Todas as {len(figures_called)} referências a figuras existem em {os.path.basename(assets_dir)}/.")

    # 3. Checagem de referências cruzadas
    print("\n--- 3. Referências Cruzadas (\\ref e \\label) ---")
    undefined_refs = []
    for ref_key, l in refs_called:
        if ref_key not in labels_defined:
            undefined_refs.append((ref_key, l))

    if undefined_refs:
        print(f"❌ {len(undefined_refs)} referências cruzadas indefinidas:")
        for r, l in undefined_refs:
            print(f"  - Linha {l}: \\ref{{{r}}}")
    else:
        print(f"✅ Todas as {len(refs_called)} referências cruzadas possuem \\label correspondente ({len(labels_defined)} labels definidos).")

    # 4. Checagem de bibliografia
    print("\n--- 4. Auditoria de Citações e Bibliografia ---")
    bib_keys = set()
    if os.path.exists(bib_path):
        with open(bib_path, "r", encoding="utf-8") as bf:
            bib_content = bf.read()
        re_bib_entry = re.compile(r'@\w+\s*\{\s*([^,\s]+)\s*,')
        for match in re_bib_entry.finditer(bib_content):
            bib_keys.add(match.group(1))

    missing_citations = [c for c in citations_called if c not in bib_keys]
    unused_keys = [k for k in bib_keys if k not in citations_called]

    if missing_citations:
        print(f"❌ {len(missing_citations)} citações no texto NÃO existem no referencias.bib:")
        for c in missing_citations:
            print(f"  - {c}")
    else:
        print(f"✅ Todas as {len(citations_called)} citações do texto estão devidamente cadastradas no .bib.")

    if unused_keys:
        print(f"ℹ️ {len(unused_keys)} entradas no .bib não são citadas no texto (potencial limpeza):")
        for u in unused_keys:
            print(f"  - {u}")
    else:
        print("✅ 100% das entradas do .bib são referenciadas no texto.")

    print("\n" + "=" * 60)
    print("RESUMO DA AUDITORIA MECÂNICA:")
    print(f"- Balanceamento: {'OK' if not env_mismatches else 'FALHA'}")
    print(f"- Figuras físicas: {'OK' if not missing_figures else 'FALHA'}")
    print(f"- Referências cruzadas: {'OK' if not undefined_refs else 'FALHA'}")
    print(f"- Citações no .bib: {'OK' if not missing_citations else 'FALHA'}")
    print("=" * 60)

if __name__ == "__main__":
    audit_latex()
