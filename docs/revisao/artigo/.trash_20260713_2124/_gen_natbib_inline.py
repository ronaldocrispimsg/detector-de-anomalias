
import re
from pathlib import Path

base = Path('/Users/marcio/Projetos/rodrigo/docs/revisao/artigo')
root = base.parent
tex = base/'artigo.tex'
out = base/'artigo_autor_data.tex'

text = tex.read_text(encoding='utf-8')

# Remove bibliografia anterior adicionada pelo script anterior
for rem in [
    '\\bibliographystyle{abntex2-alf}\n\\bibliography{referencias_autor_data}\n',
    '\\bibliographystyle{abntex2-alf}\n\\bibliography{referencias_numerico}\n',
]:
    text = text.replace(rem, '')

# Remove addbibresource/printbibliography se houver
text = re.sub(r'\\addbibresource\{referencias_autor_data\.bib\}\n', '', text)
text = re.sub(r'% =+\\n% Bibliografia ABNT autor-data\\n% =+\\n\\printbibliography\\n\\n', '', text)

# 1) Metadados ABNT a partir dos areaNN_*.txt
meta = {}
for p in sorted((root/'docs/revisao/literature').glob('area*.txt')):
    txt = p.read_text(encoding='utf-8')
    for bloc in re.split(r'\n\s*\n', txt):
        m = re.search(r'\[(\d+)\]\s*(.*?)\n\s*DOI/URL:\s*(\S+)', bloc, re.DOTALL)
        if not m:
            continue
        num, cap, doi = m.group(1), m.group(2), m.group(3)
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
        title = re.sub(r'^(ESSENCIAL|RECOMENDADO|COMPLEMENTAR)[\.\-]\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+', ' ', title).strip()
        meta[num] = dict(author=author, year=year, title=title, doi=doi)

# 2) Fallback da .bib existente
source = base/'referencias.bib'
bib = source.read_text(encoding='utf-8', errors='ignore') if source.exists() else ''
entries = {}
for m in re.finditer(r'@\w+\s*\{\s*([^,\s]+)\s*,\s*(.*?)\n\}', bib, re.DOTALL|re.IGNORECASE):
    entries[m.group(1).strip()] = m.group(2)

def clean(s):
    if not s: return ''
    s = re.sub(r'IMPORTÂNCIA:.*?(?=\n\s*CONTRIBUIÇÃO:|$)', '', s, flags=re.DOTALL)
    s = re.sub(r'CONTRIBUIÇÃO:.*', '', s, flags=re.DOTALL)
    s = re.sub(r'\[ver areaNN_\*\.txt\]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip(' ,;.-')

def field(body, k):
    m = re.search(r'\b'+k+r'\s*=\s*\{(.*?)\}(?=\s*,\s*\w+\s*=|$)', body, re.DOTALL)
    return m.group(1) if m else ''

# 3) Gera mapa key -> macro \citea<key>
maps = {}
macros = []
macros.append('% =====================================================================')
macros.append('% Macros de citação ABNT autor-data (NBR 10520)')
macros.append('% =====================================================================')
macros.append('\\makeatletter')
macros.append('\\newcommand{\\citea}[1]{\\begingroup\\edef\\@currentlabel{\\csname citea@#1\\endcsname}\\@currentlabel\\endgroup}')
# dedup cite aliases
for key in sorted(set(re.findall(r'\\cite\{([^}]+)\}', text))):
    if key == 'rRODRIGUES2026':
        key = 'rRODRIGUES'
    m = re.match(r'rA(\d+)$', key)
    if key == 'rRODRIGUES':
        author = 'Rodrigues, João Pedro Santos'
        year = '2026'
        title = 'Projeto de pesquisa: detecção e mitigação inteligente de anomalias em redes definidas por software com LLMs open-source'
        doi = ''
    elif m and m.group(1) in meta:
        author = meta[m.group(1)]['author']
        year = meta[m.group(1)]['year'] or '2026'
        title = meta[m.group(1)]['title'] or key
        doi = meta[m.group(1)]['doi'] or ''
    elif key in entries:
        body = entries[key]
        author = clean(field(body,'author') or key)
        year = re.sub(r'\D','',field(body,'year')) or '2026'
        title = clean(field(body,'title') or key)
        doi = clean(field(body,'url') or field(body,'URL') or field(body,'DOI') or '')
    else:
        author = 'Desconhecido'
        year = '2026'
        title = key
        doi = ''
    if not title:
        title = key
    maps[key] = (author, year, title, doi)
    macros.append(f'\\newcommand{{\\citea@{key}}}{{{author}, {year}}}')

# remove abntex2cite header if any
text = re.sub(r'%\s*Citacao ABNT autor-data.*\n','',text)
# add macros after date
if '% ===== macros autor-data' not in text:
    text = text.replace('\\date{Julho de 2026}', '\\date{Julho de 2026}\n\n% ===== macros autor-data\n' + '\n'.join(macros)+'\n% ===== end macros autor-data\n')

# substitui \cite{key} por \citea{key}
text = re.sub(r'\\cite\{([^}]+)\}', lambda m: '\\citea{' + (m.group(1).replace('rRODRIGUES2026','rRODRIGUES')) + '}', text)

# add references block at end
bib_block = ['\n% =====================================================================',
             '% Referências ABNT (autor-data)',
             '% =====================================================================',
             '\\begin{thebibliography}{99}',
             '\\raggedright']
for key in sorted(maps.keys()):
    author, year, title, doi = maps[key]
    # remove quotes/trailing noise for display
    title_disp = re.sub(r'^"(.*)"\.\s*$', r'\1.', title)
    title_disp = re.sub(r'\s*DOI/URL:.*$','',title_disp).strip()
    author_disp = author
    line = f'\\bibitem{{{key}}} {author_disp}, {year}. {title_disp}.'
    if doi:
        line += f' DOI:\\url{{{doi}}}.'
    bib_block.append(line)
bib_block.append('\\end{thebibliography}')
text = text.replace('\\end{document}', '\n'.join(bib_block)+'\n\n\\end{document}\n')

out.write_text(text, encoding='utf-8')
print('Gerado:', out)
print('Linhas:', text.count('\n')+1)
print('Chaves:', len(maps))
