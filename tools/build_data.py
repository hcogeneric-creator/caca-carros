"""Monta o data.json do site.
Uso: python3 tools/build_data.py <data.json do painel> [<pasta exportada do ArtifactData>]
A pasta opcional é a que ArtifactData list grava com out_dir (subpastas novos/ e saiu/ com um JSON por documento)."""
import json, sys, os, glob, datetime, re
base = json.load(open(sys.argv[1], encoding='utf-8'))
novos, saiu = [], []
if len(sys.argv) > 2:
    d = sys.argv[2]
    for f in sorted(glob.glob(os.path.join(d, '**', 'novos', '*.json'), recursive=True)):
        doc = json.load(open(f, encoding='utf-8')); novos.append(doc.get('data', doc))
    for f in sorted(glob.glob(os.path.join(d, '**', 'saiu', '*.json'), recursive=True)):
        saiu.append(os.path.splitext(os.path.basename(f))[0])
# telefones de vendedores não vão para a página pública
PHONE = re.compile(r'(\(?\d{2}\)?[\s.-]*)?9?[\s.]*\d{4}[\s.-]?\d{4}')
def clean(c):
    c = dict(c); c['desc'] = re.sub(r'\s{2,}', ' ', PHONE.sub('[telefone no anúncio]', c.get('desc') or '')).strip(); return c
base['cars'] = [clean(c) for c in base['cars']]
novos = [clean(c) for c in novos]
base['novos'] = novos
base['saiu'] = saiu
base['lastRun'] = datetime.date.today().isoformat()
json.dump(base, open('data.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(len(base['cars']), 'carros base,', len(novos), 'novos,', len(saiu), 'saíram')
