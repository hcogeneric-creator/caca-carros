"""Gera o index.html público (GitHub Pages) a partir do index.html do painel do Claude.
Uso: python3 tools/make_site.py <painel_index.html> <saida_index.html>"""
import re, sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()

def cut(a, b):
    """remove do início de a (inclusive) até o fim de b (inclusive)"""
    global s
    i = s.index(a); j = s.index(b, i) + len(b)
    s = s[:i] + s[j:]

# cabeçalho de documento completo (o painel recebe isso do Claude; o site precisa por conta própria)
head = '<!doctype html>\n<html lang="pt-BR"><head><meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
s = head + s.replace('<title>Caça-Carros Norte PR</title>', '<title>Caça-Carros Norte PR</title>\n<meta name="description" content="Carros usados de R$ 12 a 20 mil em Maringá, Londrina e região, com FIPE, ficha técnica, defeitos crônicos e ranking.">', 1)
s = s.replace('<style>', '<style>\n:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)} body{margin:0} img{max-width:100%} [hidden]{display:none!important}\n', 1)
s = s.replace('\n<div class="band">', '\n</head><body>\n<div class="band">', 1)

# barras de exportar/login e importação de fotos: só fazem sentido dentro do Claude
cut('  <div class="toolbar">\n    <button class="btn" id="exp"', '</div>\n  <div class="toolbar">')
cut('    <span>Facebook e Mercado Livre usam', '</span>\n  </div>\n')
cut('  <section id="fotos-sec" hidden>', '</div></section>\n')

# fotos: as do repositório (fotos/index.json) ou, na falta delas, as da própria OLX
s = s.replace("""function photoList(c){
  const p = PHOTOS[String(c.id)];
  return p && p.length ? p.map(id => '/_blob/' + id) : [];
}""", """function photoList(c){
  const p = PHOTOS[String(c.id)];
  if (p && p.length) return p.map(f => 'fotos/' + f);
  if (c.source === 'OLX') return (c.photos || []).slice(0, 3).map(u => u.replace('/images/', '/thumbs500x500/'));
  return [];
}""")
s = s.replace('<span>Fotos ainda não importadas</span>', '<span>Sem foto salva</span>')

# remove importação, exportação e login
cut('async function importPhotos(files){', "$('#pick').addEventListener('change', e => importPhotos(e.target.files));\n")
cut('async function toDataUrl(src){', "  } catch(e){ $('#login-help').hidden = false; }\n}));\n")

# inicialização: dados já vêm mesclados no data.json; fotos listadas em fotos/index.json
i = s.index("  renderAll();\n  try {\n    dbRef = await claude.use('db');")
j = s.index('})();\n</script>', i)
s = s[:i] + """  try { const f = await (await fetch('fotos/index.json', {cache: 'no-cache'})).json(); PHOTOS = {}; f.forEach(n => { const m = n.match(/^(\\d+)_\\d+\\./); if (m) (PHOTOS[m[1]] = PHOTOS[m[1]] || []).push(n); }); } catch(e) {}
  (DATA.novos || []).forEach(c => NEW[String(c.id)] = c);
  (DATA.saiu || []).forEach(id => GONE[String(id)] = true);
  renderAll();
""" + s[j:]
s = s.replace("fetch('data.json')", "fetch('data.json', {cache: 'no-cache'})")
s = s.replace("A busca roda todo dia de manhã e manda um e-mail quando entra carro novo. Mercado Livre e Facebook Marketplace só mostram anúncios para quem está logado; eles entram quando você fizer login no navegador do app Claude.",
              "Esta página é atualizada todo dia de manhã com anúncios novos da OLX e do Facebook Marketplace. Os carros marcados como Novo entraram nas últimas buscas.")
s = s.rstrip() + '\n</body></html>\n'
assert 'claude.use' not in s, 'sobrou código do painel'
open(dst, 'w', encoding='utf-8').write(s)
print('ok', len(s))
