import re, os
from pathlib import Path

base = Path('/Users/marcio/Projetos/rodrigo/docs/revisao/artigo')
root = base.parent
out = base/'referencias_autor_data.bib'

# 1) monta dicionário de metadados por número a partir dos areaNN*.txt
area_meta = {}
for p in sorted((root/'literature').glob('area*.txt')):
    txt = p.read_text(encoding='utf-8')
    # separa blocos numerados [N]
    for bloc in re.split(r'\n\s*\n', txt):
        m = re.search(r'\[(\d+)\]\s*(.*?)\n\s*DOI/URL:\s*(\S+)', bloc, re.DOTALL)
        if not m:
            continue
        num, cap, doi = m.group(1), m.group(2), m.group(3)
        # primeira linha é geralmente AUTORES; ano entre parênteses
        first, *rest = cap.splitlines()
        first = first.strip()
        year_m = re.search(r'\(?(\d{4})\)?', first)
        year = year_m.group(1) if year_m else ''
        author = re.sub(r'[\(,\)]\s*\d{4}.*', '', first).strip()
        if not author:
            author = 'Desconhecido'
        title = ' '.join(x.strip() for x in rest).strip()
        if not title:
            title = first
        # normalizações ABNT básicas para autor/ano/título
        title = re.sub(r'\s+', ' ', title)
        # remove prefixos字幕 terminados por ponto que são só classificação
        title = re.sub(r'^(ESSENCIAL|RECOMENDADO|COMPLEMENTAR)[\.\-]\s*', '', title, flags=re.IGNORECASE)
        area_meta[num] = dict(author=author, year=year, title=title, doi=doi)

# 2) tenta extrair entradas da .bib como fallback
source = base/'referencias.bib'
bib_text = source.read_text(encoding='utf-8') if source.exists() else ''
entries = {}
pattern = re.compile(r'@(\w+)\s*\{\s*([^,\s]+)\s*,\s*(.*?)\n\}', re.DOTALL|re.IGNORECASE)
for m in pattern.finditer(bib_text):
    entries[m.group(2).strip()] = m.group(3)

def clean(s):
    for pat in [r'IMPORTÂNCIA:.*?(?=\n\s*CONTRIBUIÇÃO:|$)', r'CONTRIBUIÇÃO:.*', r'\[ver areaNN_\*\.txt\]']:
        s = re.sub(pat, '', s, flags=re.DOTALL)
    s = re.sub(r'\s+', ' ', s)
    return s.strip(' ,;.-')

# 3) chaves citadas no tex
tex = (base/'artigo.tex').read_text(encoding='utf-8')
cited = sorted(set(re.findall(r'\\cite\{([^}]+)\}', tex)))
# rRODRIGUES2026 -> rRODRIGUES
cited = ['rRODRIGUES' if x=='rRODRIGUES2026' else x for x in cited]

lines = []
lines.append('# Gerado em duas fases: (1) areaNN_*.txt, (2) fallback referencias.bib\n')
lines.append('# Apenas chaves citadas, sem tags, sem órfãs, sem notas editoriais.\n\n')

kept = []
for key in cited:
    m_num = re.match(r'rA(\d+)$', key)
    if m_num and m_num.group(1) in area_meta:
        meta = area_meta[m_num.group(1)]
        author = meta['author']
        year = meta['year'] or '2026'
        title = meta['title']
        doi = meta['doi']
    elif key == 'rRODRIGUES':
        author = 'Rodrigues, Joao Pedro Santos'
        year = '2026'
        title = 'Projeto de pesquisa: deteccao e mitigacao inteligente de anomalias em redes definidas por software com LLMs open-source (Edital 26/2026)'
        doi = ''
    elif key in entries:
        body = entries[key]
        def get(k):
            mm = re.search(r'\b' + k + r'\s*=\s*\{(.*?)\}(?=\s*,\s*\w+\s*=|$)', body, re.DOTALL)
            return mm.group(1) if mm else ''
        author = clean(get('author') or key)
        year = re.sub(r'\D','', get('year')) or '2026'
        title = clean(get('title') or key)
        doi = clean(get('url') or get('URL') or get('DOI') or '')
    else:
        author = 'Desconhecido'
        year = '2026'
        title = key
        doi = ''

    if not title:
        title = key
    lines.append(f'@misc{{{key},\n')
    lines.append(f'  author={{{author}}},\n')
    lines.append(f'  year={{{year}}},\n')
    lines.append(f'  title={{{title}}},\n')
    if doi:
        lines.append(f'  doi={{{doi}}},\n')
    lines.append('}\n\n')
    kept.append(key)

out.write_text(''.join(lines), encoding='utf-8')
print('Gerado:', out)
print('Citadas:', len(cited), 'Mantidas:', len(kept), 'Ausentes:', sorted(set(cited)-set(kept)))
