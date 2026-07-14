
from pathlib import Path

base = Path('/Users/marcio/Projetos/rodrigo/docs/revisao/artigo')
src = base/'artigo.tex'
out = base/'artigo_autor_data.tex'

text = src.read_text(encoding='utf-8')

# 1) troca preambulo para suporte ABNT via natbib + abntex2-alf
if r'\usepackage{natbib}' not in text:
    text = text.replace('\\usepackage{hyperref}\n', '\\usepackage{hyperref}\n\\usepackage{natbib}\n', 1)

# 2) linhas de cabeçalho enganadoras
text = text.replace('pdflatex artigo.tex 2x (TinyTeX; abntex2cite para citação\\nautor-data ABNT NBR 10520)', 'pdflatex + bibtex (TinyTeX; abntex2-alf para ABNT autor-data NBR 10520)')
text = text.replace('% --- Citacao ABNT autor-data (NBR 10520) via abntex2cite ---', '% --- Citacao ABNT autor-data (NBR 10520) via natbib + abntex2-alf ---')

# 3) Richard issues: texto
text = text.replace('degradação espectral', 'degradação de desempenho')
text = text.replace('cinco de severidade crítica/maior', 'seis de severidade crítica/maior')
text = text.replace('216 referências validadas', '118 referências')

# 4) bib resource / bibtex style
if r'\bibliographystyle{abntex2-alf}' not in text:
    text = text.replace(r'\addbibresource{referencias_autor_data.bib}' + '\n', '')
    text = text.replace('\\maketitle', '\\bibliographystyle{abntex2-alf}\n\\bibliography{referencias_autor_data}\n\\maketitle', 1)

# 5) remover referencias.tex input
text = text.replace('\\input{referencias.tex}\n', '')

# 6) remover printbibliography se entrou errado
if r'\printbibliography' in text:
    text = text.replace('% =====================================================================\n% Bibliografia ABNT autor-data\n% =====================================================================\n\\printbibliography\n\n', '')

# 7) Rodrigues dedup
text = text.replace('rRODRIGUES2026', 'rRODRIGUES')

out.write_text(text, encoding='utf-8')
print('Gerado:', out)
print('Linhas:', text.count('\n')+1)
print('natbib?', 'natbib' in text)
print('abntex2-alf?', 'abntex2-alf' in text)
print('bibliography?', '\\bibliography{' in text)
