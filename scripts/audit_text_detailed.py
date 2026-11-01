import re

tex_path = "Escrita_TCC/Escrita_latex/TCC - NetSpot.tex"
with open(tex_path, "r", encoding="utf-8") as f:
    text = f.read()
    lines = text.splitlines()

print(f"Total de linhas no documento: {len(lines)}")

# 1. Resumo e Abstract
resumo_m = re.search(r"\\begin\{resumo\}(.*?)\\end\{resumo\}", text, re.DOTALL)
if resumo_m:
    # remove comments
    clean_resumo = "\n".join([l.split("%")[0] for l in resumo_m.group(1).splitlines()])
    words = len(clean_resumo.split())
    print(f"\n[1] Resumo: {words} palavras (ABNT NBR 6028 recomenda entre 150 e 500 palavras)")

abstract_m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, re.DOTALL)
if abstract_m:
    clean_abstract = "\n".join([l.split("%")[0] for l in abstract_m.group(1).splitlines()])
    words = len(clean_abstract.split())
    print(f"[1] Abstract: {words} palavras")

# 2. Aspas retas duplas (") no corpo do texto em vez de `` e ''
straight_quotes = []
for i, l in enumerate(lines, 1):
    l_strip = l.split("%")[0]
    # ignore latex package commands or options
    if i > 250 and '"' in l_strip:
        straight_quotes.append((i, l_strip.strip()))
print(f"\n[2] Aspas retas duplas (\") no corpo do texto: {len(straight_quotes)} ocorrências")
for i, sample in straight_quotes[:8]:
    print(f"    Linha {i}: {sample[:90]}")

# 3. Lista de Siglas vs Siglas Usadas
tbl_m = re.search(r"\\begin\{longtable\}.*?(.*?)\\end\{longtable\}", text, re.DOTALL)
if tbl_m:
    siglas_decl = set(re.findall(r"^([A-Za-z0-9\+\-]+)\s*&", tbl_m.group(1), re.MULTILINE))
else:
    siglas_decl = set()
print(f"\n[3] Total de siglas formalizadas na Lista de Siglas: {len(siglas_decl)}")

body_lines = lines[240:]
body_text = "\n".join([l.split("%")[0] for l in body_lines])

# Find uppercase acronyms of 2+ chars
tokens = set(re.findall(r"\b([A-Z]{2,}[0-9\+]?)\b", body_text))

# Filter out common standard terms or noise
noise = {
    "POST", "GET", "PUT", "DELETE", "HTTP", "HTTPS", "TCP", "IP", "UDP", "SNMP",
    "NOC", "IFNMG", "TCC", "ABNT", "NBR", "ISO", "OSI", "RFC", "ORM", "API",
    "DTO", "JSON", "SSH", "DNS", "DDNS", "SLA", "CRUD", "RBAC", "URL", "HTML",
    "CSS", "UI", "UX", "CPU", "RAM", "ROM", "MAC", "ARP", "ICMP", "VPN", "LAN",
    "WAN", "WLAN", "VLAN", "FQDN", "CIDR", "DCP", "DSS", "FURPS+", "GRASP",
    "OCL", "OLS", "RLS", "EDA", "TTL", "RTT", "MIB", "OID", "PDU", "USM",
    "DES", "AES", "MD5", "SHA", "AMQP", "CI", "CD", "FCAPS", "WCAG", "SQL",
    "JWT", "DB", "PDF", "OK", "AA", "AAA", "P1", "P2", "P3", "UC", "RF", "RNF", "DPI"
}

unregistered = [t for t in tokens if t not in siglas_decl and t not in noise and not t.startswith("RFC")]
print(f"[3] Siglas potenciais encontradas no texto mas AUSENTES na Lista de Siglas ({len(unregistered)}):")
for u in sorted(unregistered):
    # find lines where it appears
    occs = [i+241 for i, l in enumerate(body_lines) if re.search(r"\b" + re.escape(u) + r"\b", l.split("%")[0])]
    print(f"    - {u}: linhas {occs[:4]}")

# 4. Checagem de números e consistência factual com o código
print("\n[4] Consistência factual com o repositório:")
for i, l in enumerate(lines, 1):
    clean = l.split("%")[0]
    # Check "61 testes"
    if "61" in clean and "teste" in clean.lower():
        print(f"    [DIVERGÊNCIA] Linha {i}: Cita 61 testes: {clean.strip()[:100]}")
    # Check references to 40 hosts without Kathará 126
    if "40 hosts" in clean.lower() or "40 nós" in clean.lower():
        print(f"    [AVISO] Linha {i}: Menção a 40 nós/hosts: {clean.strip()[:100]}")

# 5. Caça a clichês de IA (Unslop Scan)
slop_patterns = [
    (r"cen[aá]rio atual", "Cacoete de abertura genérica ('cenário atual')"),
    (r"mundo contempor[aâ]neo", "Cacoete de abertura genérica ('mundo contemporâneo')"),
    (r"faz-se imperativo|[eé] imperativo", "Muleta verbal de IA ('é imperativo')"),
    (r"vale ressaltar|vale destacar|cabe destacar", "Muleta verbal de preenchimento ('vale ressaltar/destacar')"),
    (r"n[aã]o apenas .*? mas tamb[eé]m", "Estrutura sintética de IA ('não apenas X mas também Y')"),
    (r"em suma|em s[ií]ntese", "Transição conclusiva artificial"),
    (r"\brobusto\b|\brobusta\b|\brobustez\b", "Adjetivação vaidosa vazia ('robusto/robustez')"),
    (r"revolucion[aá]rio|revolucion[aá]ria", "Hipérbole desnecessária ('revolucionário')"),
    (r"pioneiro|pioneira", "Afirmação de pioneirismo sem fonte"),
    (r"orquestra[cç][aã]o harmoniosa", "Metáfora poética em computação"),
    (r"tape[cç]aria|mosaico|farol", "Metáfora poética de IA"),
    (r"de suma import[aâ]ncia", "Adjetivação prolixa ('de suma importância')"),
    (r"crucial|primordial", "Adjetivação enfática vaga ('crucial/primordial')"),
]

print("\n[5] Auditoria de Unslop (Vídeos de linguagem e clichês de IA):")
slop_count = 0
for i, l in enumerate(lines, 1):
    clean = l.split("%")[0]
    for pat, desc in slop_patterns:
        m = re.search(pat, clean, re.IGNORECASE)
        if m:
            slop_count += 1
            print(f"    Linha {i}: [{desc}] -> \"{m.group(0)}\" em: {clean.strip()[:90]}...")
print(f"Total de ocorrências de slop/vícios detectadas: {slop_count}")

# 6. Estrutura de Seções e Numeração ABNT
print("\n[6] Estrutura das Seções Primárias e Secundárias:")
sections = re.findall(r"\\(section|subsection|subsubsection)\*?\{([^}]+)\}", text)
for level, title in sections[:15]:
    print(f"    \\{level}{{{title}}}")

# 7. Formatação de Tabelas e Quadros
print("\n[7] Auditoria de Tabelas e Quadros:")
tables = re.findall(r"\\begin\{table\}(.*?)\\end\{table\}", text, re.DOTALL)
print(f"Total de tabelas: {len(tables)}")
for idx, tbl in enumerate(tables, 1):
    cap = re.search(r"\\caption\{([^}]+)\}", tbl)
    fonte = re.search(r"\\fonte\{([^}]+)\}", tbl)
    cap_str = cap.group(1) if cap else "SEM CAPTION"
    fonte_str = fonte.group(1) if fonte else "SEM FONTE"
    print(f"    Tabela {idx}: Caption: \"{cap_str}\" | Fonte: \"{fonte_str}\"")

