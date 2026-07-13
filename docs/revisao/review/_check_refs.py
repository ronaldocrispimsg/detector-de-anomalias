import re

base = "/Users/marcio/Projetos/rodrigo/docs/revisao/artigo"
art = open(f"{base}/artigo.tex", encoding="utf-8").read()
ref = open(f"{base}/referencias.tex", encoding="utf-8").read()
cit = open(f"{base}/citacoes.tex", encoding="utf-8").read()

cites = re.findall(r'\\cite\{([^}]+)\}', art)
cite_keys = []
for c in cites:
    for k in c.split(','):
        cite_keys.append(k.strip())
cite_count = {}
for k in cite_keys:
    cite_count[k] = cite_count.get(k, 0) + 1

bib_keys = re.findall(r'\\bibitem\{([^}]+)\}', ref)
q_keys = re.findall(r'\\def\\(q[A-Za-z0-9]+)\{', cit)

print("=== COUNTS ===")
print("cite commands:", len(cites), "| unique cited keys:", len(cite_count))
print("bibitems:", len(bib_keys), "| qA defs in citacoes:", len(q_keys))

bib_set = set(bib_keys)
broken = [k for k in cite_count if k not in bib_set]
print("\n=== BROKEN CITATIONS (cited, no bibitem) ===")
print(broken if broken else "NONE")

cited_set = set(cite_count)
orphan = [k for k in bib_keys if k not in cited_set]
print("\n=== ORPHAN BIBITEMS (defined, never cited) ===")
for k in orphan:
    print(" ", k)

dups = [k for k, c in __import__('collections').Counter(bib_keys).items() if c > 1]
print("\n=== DUPLICATE BIBITEM KEYS ===")
print(dups if dups else "NONE")

missing_q = [k for k in bib_keys if ("q" + k[1:]) not in q_keys]
print("\n=== BIBITEMS WITHOUT MATCHING qA IN citacoes.tex ===")
print(missing_q if missing_q else "NONE (all bibitems have qA)")

q_used = re.findall(r'\\(qA[A-Za-z0-9]+)', art)
print("\n=== Does artigo.tex use any \\qAxx commands? ===")
print("count:", len(q_used), "examples:", list(set(q_used))[:5] if q_used else "NONE")
print("Is \\input{citacoes} present?", ("\\input{citacoes" in art))

# total unique cite keys
print("\n=== FULL CITED KEY LIST ===")
for k in sorted(cite_count, key=lambda x: (x[1:],) if x[1:].isdigit() else (x,)):
    print(f"  {k}: x{cite_count[k]}")
