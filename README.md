# Caça-Carros Norte PR

Página pública com carros usados de R$ 12 a 20 mil (ano 2001+) em Maringá, Sarandi, Marialva, Londrina, Santo Antônio da Platina, Jacarezinho e Ourinhos, coletados da OLX e do Facebook Marketplace, com FIPE, ficha técnica, defeitos crônicos e ranking ajustável.

Atualizada todo dia por uma tarefa agendada do Claude:
- `data.json` — anúncios (gerado por `tools/build_data.py`)
- `index.html` — página (gerada por `tools/make_site.py` a partir do painel)
- `fotos/` — fotos dos anúncios, enviadas do PC por `atualizar-fotos.ps1`
