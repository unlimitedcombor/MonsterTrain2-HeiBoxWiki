"""把 template/ 下的模板渲染为成品 HTML，输出到 dist/"""
import sys
sys.path.insert(0, '.')
from preview import render
from pathlib import Path
import os

td = Path('template')
dd = Path('dist')
dd.mkdir(exist_ok=True)

data = {
    'icon_attack': 'res/ui/Attack.png',
    'icon_health': 'res/ui/Health.png',
    'icon_ember': 'res/ui/Ember.png',
    'icon_capacity': 'res/ui/Capacity.png',
    'icon_gold': 'res/ui/Gold.png',
    'image': 'res/card.png',
    'name': '卡牌名称',
    'clan': '氏族',
    'rarity': 'Common',
    'type': '类型',
    'banner': 'Yes',
    'cost': 'X',
    'size': 'X',
    'attack': '0',
    'health': '0',
    'ability': '能力描述文本',
    'effect': '效果描述文本',
    'flavor': '风味文字',
    'artist': '画师名',
    'baseline_attack': '0',
    'baseline_health': '0',
    'covenant8_attack': '0',
    'covenant8_health': '0',
    'ring1': 'Ring 1 出现位置',
    'ring2': 'Ring 2 出现位置',
    'ring3': 'Ring 3 出现位置',
    'titan': 'Titan 名',
    'unit_count': '177',
    'spell_count': '239',
    'equip_count': '39',
    'room_count': '21',
    'enemy_count': '56',
    'artifact_count': '0',
    'last_updated': '2026-06-22',
    'unit_clans': 'Awoken / Banished / ...',
    'spell_clans': 'Awoken / Banished / ...',
    'equip_clans': 'Awoken / Banished / ...',
    'room_clans': 'Awoken / Banished / ...',
    'enemy_rings': 'Rings 1-8',
    'artifact_clans': '',
}

for fname in sorted(os.listdir(str(td))):
    if not fname.endswith('.html'):
        continue
    template = (td / fname).read_text(encoding='utf-8')
    rendered = render(template, data)
    out = dd / fname
    out.write_text(rendered, encoding='utf-8')
    print(out.name)

print(f'\nDone -> {dd}/')
