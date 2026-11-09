"""Preenche a FIPE média do modelo/ano de cada carro do data.json (campos fipe_media e fipe_ref).

Uso, na pasta do repositório:  python tools/fipe.py
  --offline lista.json   só mostra quais versões casariam (sem consultar a API e sem gravar)
  --report               imprime, para cada carro, a chave, o valor e as versões usadas
  --max-calls N          limite de consultas nesta execução (padrão 450)

Regras:
- "FIPE média do modelo" = média dos preços de todas as versões FIPE da mesma marca, modelo,
  motor e carroceria (sedan, perua, G5 etc.) no ano-modelo do carro, flex ou gasolina.
- Nunca mexe no campo "fipe" (valor citado pelo vendedor).
- Resultados ficam em data.json["fipe_cache"]; só consulta a API para combinações novas ou com
  mais de 30 dias. Consultas sem versão encontrada são repetidas depois de 7 dias.
- API: fipe.parallelum.com.br v2 (sem chave: cerca de 500 consultas por dia e 50 por minuto);
  v1 do mesmo serviço como reserva; BrasilAPI (preço pelo código FIPE) como última reserva.
- Nunca derruba a rotina diária: em qualquer falha o valor fica vazio e o script termina com 0.
"""
import json, os, re, sys, time, datetime, unicodedata, urllib.request, urllib.error
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data.json')
V2 = 'https://fipe.parallelum.com.br/api/v2/cars'
V1 = 'https://parallelum.com.br/fipe/api/v1/carros'
BRASILAPI = 'https://brasilapi.com.br/api/fipe/preco/v1/'
UA = {'User-Agent': 'caca-carros/1.0 (github.com/hcogeneric-creator/caca-carros)', 'Accept': 'application/json'}
DELAY = 1.3            # segundos entre consultas (limite de 50 por minuto)
MAX_SECONDS = 25 * 60  # tempo máximo de uma execução
REFRESH_DAYS = 30
RETRY_EMPTY_DAYS = 7
MAX_VERSIONS = 12      # acima disso, usa uma amostra espalhada das versões
TODAY = datetime.date.today()

BRANDS = {'vw': 59, 'chevrolet': 23, 'fiat': 21, 'ford': 22, 'renault': 48, 'peugeot': 44, 'citroen': 13,
          'honda': 25, 'chery': 161, 'lifan': 168, 'mercedes': 39}
# (família, marca, regex no título normalizado, regex no nome FIPE normalizado, sedan muda o modelo?)
FAMILIES = [
    ('classe a', 'mercedes', r'\bclasse a\b', r'^classe a\b', False),
    ('golf', 'vw', r'\bgolf\b', r'^golf\b', False),
    ('gol', 'vw', r'\bgol\b', r'^gol\b', False),
    ('fox', 'vw', r'\bfox\b', r'^fox\b', False),
    ('parati', 'vw', r'\bparati\b', r'^parati\b', False),
    ('voyage', 'vw', r'\bvoyage\b', r'^voyage\b', False),
    ('celta', 'chevrolet', r'\bcelta\b', r'^celta\b', False),
    ('prisma', 'chevrolet', r'\bprisma\b', r'^prisma\b', False),
    ('classic', 'chevrolet', r'\bclassic\b', r'^(classic\b|corsa sedan (classic|wind|super|sup|gl|gls)\b)', False),
    ('corsa', 'chevrolet', r'\bcorsa\b', r'^corsa\b', True),
    ('meriva', 'chevrolet', r'\bmeriva\b', r'^meriva\b', False),
    ('vectra', 'chevrolet', r'\bvectra\b', r'^vectra\b', False),
    ('astra', 'chevrolet', r'\bastra\b', r'^astra\b', True),
    ('zafira', 'chevrolet', r'\bzafira\b', r'^zafira\b', False),
    ('palio', 'fiat', r'\bpalio\b', r'^palio\b', False),
    ('uno', 'fiat', r'\buno\b', r'^uno\b', False),
    ('siena', 'fiat', r'\bsiena\b', r'^siena\b', False),
    ('idea', 'fiat', r'\bidea\b', r'^idea\b', False),
    ('linea', 'fiat', r'\blinea\b', r'^linea\b', False),
    ('stilo', 'fiat', r'\bstilo\b', r'^stilo\b', False),
    ('punto', 'fiat', r'\bpunto\b', r'^punto\b', False),
    ('brava', 'fiat', r'\bbrava\b', r'^brava\b', False),
    ('strada', 'fiat', r'\bstrada\b', r'^strada\b', False),
    ('doblo', 'fiat', r'\bdoblo\b', r'^doblo\b', False),
    ('fiesta', 'ford', r'\bfiesta\b', r'^fiesta\b', True),
    ('ka', 'ford', r'\bka\b', r'^ka\b', True),
    ('focus', 'ford', r'\bfocus\b', r'^focus\b', True),
    ('fusion', 'ford', r'\bfusion\b', r'^fusion\b', False),
    ('logan', 'renault', r'\blogan\b', r'^logan\b', False),
    ('sandero', 'renault', r'\bsandero\b', r'^sandero\b', False),
    ('clio', 'renault', r'\bclio\b', r'^clio\b', True),
    ('scenic', 'renault', r'\bscenic\b', r'^scenic\b', False),
    ('megane', 'renault', r'\bmegane\b', r'^megane\b', True),
    ('206', 'peugeot', r'\b206\b', r'^206\b', False),
    ('207', 'peugeot', r'\b207\b', r'^207\b', True),
    ('307', 'peugeot', r'\b307\b', r'^307\b', True),
    ('407', 'peugeot', r'\b407\b', r'^407\b', False),
    ('c3', 'citroen', r'\bc3\b', r'^c3\b', False),
    ('c4', 'citroen', r'\bc4\b', r'^c4\b', False),
    ('xsara', 'citroen', r'\bxsara\b', r'^xsara\b', False),
    ('civic', 'honda', r'\bcivic\b', r'^civic\b', False),
    ('accord', 'honda', r'\baccord\b', r'^accord\b', False),
    ('qq', 'chery', r'\bqq\b', r'^qq\b', False),
    ('face', 'chery', r'\bchery face\b', r'^face\b', False),
    ('320', 'lifan', r'\blifan 320\b', r'^320\b', False),
]
FAM = {f[0]: f for f in FAMILIES}
# regras extras por chave "model" do data.json
MODEL_RULES = {
    'logan10': 'logan', 'logan16': 'logan', 'sandero10': 'sandero', 'clio10': 'clio', 'clio16': 'clio',
    'scenic16': 'scenic', 'scenic20': 'scenic', 'megane16': 'megane', 'megane20at': 'megane',
    'palio10': 'palio', 'uno10': ('uno', r'\bmille\b'), 'siena10': 'siena', 'idea14': 'idea', 'linea19': 'linea',
    'stilo18': 'stilo', 'punto14': 'punto', 'golG3': 'gol', 'golf16': 'golf', 'fiestaSC': 'fiesta',
    'fire16v': (None, r'\b16v\b'), 'brava16': 'brava', 'fiesta10': 'fiesta', 'ka10': 'ka', 'focus16': 'focus',
    'focus20': 'focus', 'p206': '206', 'p207_14': '207', 'p207_16': '207', 'p407': '407', 'c3_14': 'c3',
    'c3_16': 'c3', 'c4pallas': ('c4', r'\bpallas\b'), 'xsara16': 'xsara', 'xsara20': 'xsara', 'civic17': 'civic',
    'accord20': 'accord', 'qq11': 'qq', 'celta10': 'celta', 'classic10': 'classic', 'classic16': 'classic',
    'corsa18': ('corsa', None, r'^corsa hatch\b'), 'corsa10': ('corsa', None, r'^corsa hatch\b'),
    'prisma14': 'prisma', 'meriva18': 'meriva', 'vectra20': 'vectra', 'astra20': 'astra', 'gol10': 'gol',
    'gol16': 'gol', 'golAP': 'gol', 'fox10': 'fox', 'parati16': 'parati', 'parati18': 'parati',
}
FLAG_RE = {
    'sedan': r'\bsedan\b',
    'wagon': r'\b(weekend|sw|grand tour|break|wagon|variant)\b',
    'offroad': r'\b(adventure|trekking|locker|crossover|stepway|xtreme|extreme|trail|x-line|escapade|freestyle|xtr|tryon|xingu)\b',
    'novo': r'\(novo\)|\bnovo\b|\bg[56]\b',
    'picasso': r'\bpicasso\b',
    'perf': r'\b(turbo|supercharger|gti|gsi|abarth|t-jet|tsi|tb|rs|ss)\b',
    'util': r'\b(furgao|furg|cargo|pick-up|pickup|van|cabrio|cabriolet|coupe|cc|cupe)\b',
    'aut': r'\b(aut|automatic|automatico|automatica|tiptronic|tip|dualogic|dual|dualo|easytronic|easyr|easy r|semi-aut|cvt|i motion|imotion)\b',
}
BRAND_LABEL = {'vw': 'VW', 'chevrolet': 'Chevrolet', 'fiat': 'Fiat', 'ford': 'Ford', 'renault': 'Renault', 'peugeot': 'Peugeot',
               'citroen': 'Citroën', 'honda': 'Honda', 'chery': 'Chery', 'lifan': 'Lifan', 'mercedes': 'Mercedes'}
FAM_LABEL = {'qq': 'QQ', 'classe a': 'Classe A', 'scenic': 'Scénic', 'megane': 'Mégane', 'doblo': 'Doblò', 'c3': 'C3', 'c4': 'C4'}
FLAG_LABEL = {'sedan': 'Sedan', 'wagon': 'SW', 'offroad': 'Adventure', 'novo': 'G5', 'picasso': 'Picasso', 'perf': 'Turbo', 'util': 'Utilitário', 'aut': 'Aut.'}
ENGINE_RE = r'(?<![\d.])([1-6]\.\d)(?!\d)'


def strip(s):
    return ''.join(ch for ch in unicodedata.normalize('NFD', str(s or '')) if unicodedata.category(ch) != 'Mn').lower()


def norm(s):
    s = strip(s)
    for a, b in [(r'\bsed\b\.?', ' sedan '), (r'\bhat\b\.?', ' hatch '), (r'\bweek\b\.?', ' weekend '),
                 (r'\bw\.\s*adv', ' weekend adventure'), (r'\badv(ent)?\b\.?', ' adventure '), (r'\bg\.\s*tour', ' grand tour'),
                 (r'\bpal\.', ' pallas '), (r'\bclas+\.', ' classic '), (r'\bstep\.', ' stepway '),
                 (r'\bcorsica\b', 'corsa'), (r'\bvolkswagen\b', 'vw'), (r'\bgm\b', 'chevrolet'), (r'\bmercedes-benz\b', 'mercedes')]:
        s = re.sub(a, b, s)
    return re.sub(r'\s+', ' ', s).strip()


def flags(s):
    return {k: bool(re.search(r, s)) for k, r in FLAG_RE.items()}


def engines(s):
    e = set(re.findall(ENGINE_RE, s))
    for cc in re.findall(r'\b(1000|1600|1800|2000)(?=i\b|\b)', s):   # "Gol 1000 Mi", "Gol GTi 2000"
        e.add(cc[0] + '.' + cc[1])
    return e


def spec_for(c, models):
    """Descreve o que procurar na FIPE para o carro c; None se não der para identificar."""
    t = norm(c.get('title'))
    m = re.search(r'\b(19|20)(\d\d)/(\d\d)\b', t)
    year = 2000 + int(m.group(3)) if m else c.get('year')
    if not isinstance(year, int) or year < 1990:
        return None
    rule = MODEL_RULES.get(c.get('model') or '')
    rule = (rule,) if isinstance(rule, str) else (rule or ())
    rfam, rreq, rfipe = (list(rule) + [None, None, None])[:3]
    fam = next((f[0] for f in FAMILIES if re.search(f[2], t)), None) or rfam
    if fam == 'corsa' and rfam == 'classic':   # "Corsa Sedan" que o cadastro já identificou como Classic
        fam = 'classic'
    if not fam:
        return None
    same = rfam in (None, fam) and bool(rule)
    name, brand, _, fipe_re, sedan_rel = FAM[fam]
    eng = (re.findall(ENGINE_RE, t) or [None])[0]
    if not eng and same:
        eng = (re.findall(ENGINE_RE, strip((models.get(c.get('model')) or {}).get('modelo'))) or [None])[0]
    f = flags(t)
    if fam == '207' and re.search(r'\bpassion\b', t):
        f['sedan'] = True
    if c.get('gear') == 'A':
        f['aut'] = True
    if fam != 'gol':
        f['novo'] = False
    req = rreq if same else None
    if fam == 'uno' and re.search(r'\b(vivace|way|attractive|evo|sporting|economy)\b', t) and not re.search(r'\bmille\b', t):
        req = None
    if fam == 'classe a':
        n = re.search(r'\b(160|190|200)\b', t)
        req = r'\b%s\b' % n.group(1) if n else None
    fuels = [2] if re.search(r'\b(alcool|etanol)\b', t) or c.get('model') == 'golAP' else [5, 1]
    if re.search(r'\bgasolina\b', t) or (year < 2003 and fuels != [2]):
        fuels = [1]   # flex só existe a partir de 2003
    on = [k for k in ('sedan', 'wagon', 'offroad', 'novo', 'picasso', 'perf', 'util', 'aut') if f[k] and (k != 'sedan' or sedan_rel)]
    key = '|'.join([str(BRANDS[brand]), fam + ''.join('+' + k for k in on) + ('~' + re.sub(r'\W', '', req) if req else ''),
                    eng or '*', str(year), ','.join(map(str, fuels))])
    def flag_word(k):
        w = re.search(FLAG_RE[k], t) if k in ('wagon', 'perf', 'offroad') else None
        return w.group(0).title() if w else FLAG_LABEL[k]
    label = ' '.join([BRAND_LABEL[brand], FAM_LABEL.get(fam, fam.title())] + [flag_word(k) for k in on]
                     + ([re.sub(r'\\b', '', req).title()] if req else []) + ([eng] if eng else []) + [str(year)])
    return {'key': key, 'brand': BRANDS[brand], 'fam': fam, 'fipe_re': rfipe if (same and rfipe) else fipe_re,
            'sedan_rel': sedan_rel, 'flags': f, 'engine': eng, 'req': req, 'year': year, 'fuels': fuels, 'label': label}


def matches(name, sp):
    n = norm(name)
    if not re.search(sp['fipe_re'], n):
        return False
    f = flags(n)
    for k in ('wagon', 'offroad', 'picasso', 'perf', 'util', 'aut'):
        if f[k] != sp['flags'][k]:
            return False
    if sp['sedan_rel'] and f['sedan'] != sp['flags']['sedan']:
        return False
    if sp['fam'] == 'gol' and f['novo'] != sp['flags']['novo']:
        return False
    if sp['engine']:
        if sp['engine'] not in engines(n):   # nome sem motor (versões antigas genéricas) também fica de fora
            return False
    if sp['req'] and not re.search(sp['req'], n):
        return False
    return True


class Stop(Exception):
    pass


class Api:
    def __init__(self, max_calls):
        self.max_calls, self.calls, self.t0, self.last = max_calls, 0, time.time(), 0.0
        self.down = set()    # hosts que esgotaram a cota ou caíram nesta execução
        self.memo = {}

    def get(self, url):
        host = url.split('/')[2]
        if host in self.down:
            raise Stop(host)
        if self.calls >= self.max_calls or time.time() - self.t0 > MAX_SECONDS:
            raise Stop('limite desta execução')
        for attempt in range(4):
            wait = DELAY - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.calls += 1
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                    return json.loads(r.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                if e.code in (400, 404):
                    return None
                if e.code == 429:
                    ra = e.headers.get('Retry-After') or ''
                    ra = int(ra) if ra.isdigit() else 20 * (attempt + 1)
                    if ra > 90 or attempt == 3:
                        self.down.add(host)
                        raise Stop(host + ' (cota esgotada)')
                    time.sleep(ra)
                    continue
                time.sleep(3 * (attempt + 1))
            except Exception:
                time.sleep(3 * (attempt + 1))
        self.down.add(host)
        raise Stop(host + ' (indisponível)')


def money(s):
    try:
        return int(round(float(re.sub(r'[^\d,]', '', str(s)).replace(',', '.'))))
    except ValueError:
        return None


def month(s):
    return re.sub(r'\s+de\s+', '/', str(s or '').strip()) or None


def fresh(ts, days):
    try:
        return (TODAY - datetime.date.fromisoformat(ts)).days < days
    except Exception:
        return False


def year_models(api, brand, year, fuels):
    out = []
    for fu in fuels:
        yid = '%d-%d' % (year, fu)
        k = ('y', brand, yid)
        if k not in api.memo:
            try:
                api.memo[k] = [(str(m['code']), m['name'], yid, True) for m in (api.get('%s/brands/%d/years/%s/models' % (V2, brand, yid)) or [])]
            except Stop:
                # reserva: v1 não lista por ano; usa todos os modelos da marca e deixa o preço dizer se existe
                kb = ('b', brand)
                if kb not in api.memo:
                    r = api.get('%s/marcas/%d/modelos' % (V1, brand)) or {}
                    api.memo[kb] = [(str(m['codigo']), m['nome']) for m in r.get('modelos', [])]
                api.memo[k] = [(c, n, yid, False) for c, n in api.memo[kb]]
        out += api.memo[k]
    return out


def get_price(api, cache, brand, code, yid):
    k = '%d|%s|%s' % (brand, code, yid)
    old = cache['precos'].get(k)
    if old and fresh(old.get('ts'), REFRESH_DAYS):
        return old
    r = None
    try:
        j = api.get('%s/brands/%d/models/%s/years/%s' % (V2, brand, code, yid))
        if j:
            r = {'v': money(j.get('price')), 'mes': month(j.get('referenceMonth')), 'cf': j.get('codeFipe')}
    except Stop:
        try:
            j = api.get('%s/marcas/%d/modelos/%s/anos/%s' % (V1, brand, code, yid))
            if j:
                r = {'v': money(j.get('Valor')), 'mes': month(j.get('MesReferencia')), 'cf': j.get('CodigoFipe')}
        except Stop:
            if not (old and old.get('cf')):
                raise
            lst = api.get(BRASILAPI + old['cf']) or []
            y = int(yid.split('-')[0])
            hit = next((x for x in lst if x.get('anoModelo') == y), None)
            if not hit:
                raise
            r = {'v': money(hit.get('valor')), 'mes': month(hit.get('mesReferencia')), 'cf': old['cf']}
    if not r or not r['v']:
        return None
    r['ts'] = TODAY.isoformat()
    cache['precos'][k] = r
    return r


def compute(api, cache, sp):
    cands, seen = [], set()
    for code, name, yid, sure in year_models(api, sp['brand'], sp['year'], sp['fuels']):
        if (code, yid) not in seen and matches(name, sp):
            seen.add((code, yid))
            cands.append((code, name, yid, sure))
    cands.sort(key=lambda x: x[1])
    if len(cands) > MAX_VERSIONS:
        step = len(cands) / MAX_VERSIONS
        cands = [cands[int(i * step)] for i in range(MAX_VERSIONS)]
    got = []
    for code, name, yid, sure in cands:
        p = get_price(api, cache, sp['brand'], code, yid)
        if p:
            got.append((name, p))
    res = {'ts': TODAY.isoformat(), 'label': sp['label']}
    if not got:
        res.update(valor=None, n=0)
        return res
    res.update(valor=int(round(sum(p['v'] for _, p in got) / len(got))), n=len(got),
               mes=Counter(p['mes'] for _, p in got).most_common(1)[0][0],
               versoes=sorted({n for n, _ in got}))
    return res


def load():
    with open(DATA, encoding='utf-8') as f:
        return json.load(f)


def save(d):
    tmp = DATA + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, DATA)


def apply(d, cache, specs):
    for c in d.get('cars', []) + d.get('novos', []):
        sp = specs.get(id(c))
        r = cache['combos'].get(sp['key']) if sp else None
        if r and r.get('valor'):
            c['fipe_media'] = r['valor']
            c['fipe_ref'] = {'n': r['n'], 'label': r['label'], 'mes': r.get('mes'), 'chave': sp['key']}
        elif 'fipe_media' not in c or (r and not r.get('valor')):
            c['fipe_media'] = None
            c.pop('fipe_ref', None)


def run(args):
    offline = args[args.index('--offline') + 1] if '--offline' in args else None
    max_calls = int(args[args.index('--max-calls') + 1]) if '--max-calls' in args else 450
    d = load()
    models = d.get('models') or {}
    cars = d.get('cars', []) + d.get('novos', [])
    specs = {}
    for c in cars:
        try:
            specs[id(c)] = spec_for(c, models)
        except Exception:
            specs[id(c)] = None
    if offline:
        lists = json.load(open(offline, encoding='utf-8'))['models']
        by_brand = {int(k.split()[0]): v for k, v in lists.items()}
        for c in cars:
            sp = specs[id(c)]
            names = [m['name'] for m in by_brand.get(sp['brand'], [])] if sp else []
            hit = [n for n in names if matches(n, sp)] if sp else []
            print('%s | %s | %s | %d | %s' % (c['id'], c.get('title'), sp and sp['key'], len(hit), ' ; '.join(hit[:8])))
        return
    cache = d.setdefault('fipe_cache', {})
    cache.setdefault('combos', {})
    cache.setdefault('precos', {})
    gone = set(map(str, d.get('saiu', [])))
    # prioridade: ativos sem FIPE do vendedor, depois ativos com FIPE, depois vendidos
    order = sorted(cars, key=lambda c: (str(c.get('id')) in gone or bool(c.get('sold') or c.get('removed')), c.get('fipe') is not None))
    todo, seenk = [], set()
    for c in order:
        sp = specs[id(c)]
        if not sp or sp['key'] in seenk:
            continue
        seenk.add(sp['key'])
        old = cache['combos'].get(sp['key'])
        if old and fresh(old.get('ts'), REFRESH_DAYS if old.get('valor') else RETRY_EMPTY_DAYS):
            continue
        todo.append(sp)
    api = Api(max_calls)
    done, stopped = 0, None
    for sp in todo:
        try:
            cache['combos'][sp['key']] = compute(api, cache, sp)
            done += 1
        except Stop as e:
            stopped = str(e)
            break
        except Exception as e:
            print('  erro em', sp['key'], repr(e)[:120])
        if done % 15 == 0:
            apply(d, cache, specs)
            save(d)
    apply(d, cache, specs)
    save(d)
    seller = sum(1 for c in cars if isinstance(c.get('fipe'), (int, float)))
    media = sum(1 for c in cars if c.get('fipe') is None and c.get('fipe_media'))
    none = [c for c in cars if c.get('fipe') is None and not c.get('fipe_media')]
    print('FIPE: %d combinações consultadas agora (%d consultas à API)%s' % (done, api.calls, '; parou: ' + stopped if stopped else ''))
    print('FIPE: %d carros com FIPE do vendedor, %d só com FIPE média, %d sem nenhuma; %d com FIPE média no total'
          % (seller, media, len(none), sum(1 for c in cars if c.get('fipe_media'))))
    if '--report' in args:
        for c in cars:
            sp = specs[id(c)]
            r = cache['combos'].get(sp['key']) if sp else None
            print('%s | %s | vend %s | media %s | %s | %s' % (c['id'], c.get('title'), c.get('fipe'), c.get('fipe_media'),
                                                              sp and sp['key'], r and ' ; '.join(r.get('versoes', []))))
    for c in none:
        sp = specs[id(c)]
        print('  sem FIPE: %s %s (%s)' % (c['id'], c.get('title'), sp['key'] if sp else 'modelo não reconhecido'))


def main():
    try:
        sys.stdout.reconfigure(errors='replace')
    except Exception:
        pass
    try:
        run(sys.argv[1:])
    except Exception as e:
        print('fipe.py: erro inesperado, data.json não foi alterado nesta etapa:', repr(e)[:300])
    try:
        if os.path.exists(DATA + '.tmp'):   # sobra de gravação interrompida não pode ir para o commit
            os.remove(DATA + '.tmp')
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
