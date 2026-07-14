"""
本地预览小黑盒模板。把 {{ var }} 和 {% if var %} 渲染成可预览的 HTML。
用法: python preview.py 模板.html 数据.json > preview.html
      python preview.py 怪物火车2-卡牌.html 卡牌预览.json
"""

import sys
import json
import re
from pathlib import Path


def render(template, data):
    """简易模板引擎：{{ var }} 替换，{% if var %} ... {% endif %} 条件渲染"""

    # 1. 处理 {% if var %} ... {% endif %}
    def process_if_block(html, variables):
        result = []
        i = 0
        while i < len(html):
            m = re.search(r'\{%\s*if\s+(\w+)\s*%\}', html[i:])
            if not m:
                result.append(html[i:])
                break

            # 在 {% if %} 之前的内容
            result.append(html[i:i + m.start()])

            # 找匹配的 {% endif %}
            var_name = m.group(1)
            block_start = i + m.end()
            depth = 1
            j = block_start
            while j < len(html) and depth > 0:
                next_if = re.search(r'\{%\s*if\s+\w+\s*%\}', html[j:])
                next_endif = re.search(r'\{%\s*endif\s*%\}', html[j:])
                if not next_endif:
                    break
                if next_if and next_if.start() < next_endif.start():
                    depth += 1
                    j += next_if.end()
                else:
                    depth -= 1
                    if depth == 0:
                        # 找到匹配的 endif
                        block_content = html[block_start:j + next_endif.start()]
                        if variables.get(var_name):
                            result.append(process_if_block(block_content, variables))
                        j += next_endif.end()
                    else:
                        j += next_endif.end()

            i = j
        return ''.join(result)

    html = process_if_block(template, data)

    # 2. 替换 {{ var }}
    for key, value in data.items():
        html = html.replace('{{ ' + key + ' }}', str(value))
        html = html.replace('{{ ' + key + ' }}', str(value))
    # 处理无空格格式
    for key, value in data.items():
        html = html.replace('{{' + key + '}}', str(value))

    # 清理未替换的 {{ ... }}
    html = re.sub(r'\{\{[^}]+\}\}', '', html)
    # 清理 {% %} 标签
    html = re.sub(r'\{%[^%]*%\}', '', html)

    return html


def main():
    if len(sys.argv) < 2:
        print("Usage: python preview.py <template.html> [data.json]")
        print("       python preview.py 怪物火车2-卡牌.html 卡牌预览.json")
        sys.exit(1)

    template_path = Path(sys.argv[1])
    template = template_path.read_text(encoding='utf-8')

    # 默认数据
    data = {
        # icon paths (本地预览用相对路径)
        "icon_attack": "res/ui/Attack.png",
        "icon_health": "res/ui/Health.png",
        "icon_ember": "res/ui/Ember.png",
        "icon_capacity": "res/ui/Capacity.png",
        "icon_gold": "res/ui/Gold.png",
        "name": "Death's Dancer",
        "image": "https://static.wikitide.net/monstertrain2wiki/0/02/PLR_DeathsDancer.png",
        "clan": "Banished",
        "rarity": "Rare",
        "type": "Angel",
        "banner": "Yes",
        "cost": "1",
        "size": "2",
        "attack": "7",
        "health": "14",
        "ability": "Shift: Apply +4 Attack to friendly units.",
        "effect": "",
        "flavor": '"Dance is a poem in which each kill is a step."',
        "artist": "Loy Bouttamy",
        # enemy fields
        "baseline_attack": "5",
        "baseline_health": "2",
        "covenant8_attack": "6",
        "covenant8_health": "2",
        "ring1": "Mark of Invasion",
        "ring2": "Flagellant's March",
        "titan": "Savagery",
        "unit_count": "177",
        "unit_clans": "Awoken、Banished、Hellhorned...",
        "spell_count": "239",
        "spell_clans": "Awoken、Banished、Hellhorned...",
        "equip_count": "39",
        "equip_clans": "Awoken、Banished...",
        "room_count": "21",
        "room_clans": "Awoken、Banished...",
        "enemy_count": "56",
        "enemy_rings": "Rings 1-8",
        "artifact_count": "0",
        "artifact_clans": "",
        "last_updated": "2026-06-22",
    }

    # 加载自定义数据
    if len(sys.argv) >= 3:
        with open(sys.argv[2], 'r', encoding='utf-8') as f:
            custom = json.load(f)
        data.update(custom)

    rendered = render(template, data)

    outfile = template_path.stem + '_preview.html'
    Path(outfile).write_text(rendered, encoding='utf-8')
    print(f"Preview saved to {outfile}", file=sys.stderr)


if __name__ == '__main__':
    main()
