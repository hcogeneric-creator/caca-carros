"""Acrescenta ao data.json do site os carros novos e os que saíram, vindos da tarefa diária.
Uso (no PC, na pasta do repositório): python tools/merge_novos.py hoje.json
hoje.json = {"novos": [ {...carro...}, ... ], "saiu": ["id", ...]}"""
import json, sys, re, datetime
PHONE = re.compile(r'(\(?\d{2}\)?[\s.-]*)?9?[\s.]*\d{4}[\s.-]?\d{4}')
d = json.load(open('data.json', encoding='utf-8'))
h = json.load(open(sys.argv[1], encoding='utf-8'))
have = {str(c['id']) for c in d['cars']} | {str(c['id']) for c in d.get('novos', [])}
add = 0
for c in h.get('novos', []):
    if str(c['id']) in have: continue
    c['desc'] = PHONE.sub('[telefone no anúncio]', c.get('desc') or '')
    c.setdefault('added', datetime.datetime.now().astimezone().isoformat(timespec='minutes'))  # para o filtro Últimas 48h
    d.setdefault('novos', []).append(c); add += 1
    have.add(str(c['id']))  # o mesmo id repetido no próprio hoje.json não entra duas vezes
d['saiu'] = sorted(set(map(str, d.get('saiu', []))) | set(map(str, h.get('saiu', []))))
d['lastRun'] = datetime.date.today().isoformat()
json.dump(d, open('data.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'{add} novos acrescentados; {len(d["saiu"])} marcados como vendidos/removidos')
