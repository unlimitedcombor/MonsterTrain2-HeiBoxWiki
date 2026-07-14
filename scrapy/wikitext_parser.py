"""
解析 MediaWiki wikitext 格式 ({{Infobox ...}}, == Sections ==, {| wikitable |})。

wikitext 比 HTML 好解析得多，是爬虫下载的主要格式。
"""

import re
import json
from pathlib import Path


def clean(text):
    """清理空白和引号"""
    text = text.replace('\xa0', ' ')
    text = text.replace('‘', "'").replace('’', "'")
    text = text.replace('“', '"').replace('”', '"')
    return text.strip()


# ============================================================
# Infobox 模板解析
# ============================================================

def parse_infobox(wikitext):
    """
    解析页面的 Infobox 模板。
    支持 {{Infobox\n|field=value\n...}}
    和 {{UnitInfobox\n|field=value\n...}}
    """
    # 匹配模板开始: {{UnitCard, {{Infobox, {{Enemy, {{Artifact 等
    # 特征：{{模板名\n|参数=值 ...
    m = re.search(r'\{\{([A-Za-z]+)\s*\n\s*\|', wikitext)
    if not m:
        # 也可能是紧跟着 | 的格式: {{模板名|参数=值
        m = re.search(r'\{\{([A-Za-z]+)\s*\|', wikitext)

    if not m:
        return {"fields": {}, "sections": []}

    start = m.start()
    # 找到匹配的 }}
    depth = 1
    i = m.end()
    while i < len(wikitext) and depth > 0:
        if wikitext[i:i+2] == '{{':
            depth += 1
            i += 2
        elif wikitext[i:i+2] == '}}':
            depth -= 1
            if depth == 0:
                break
            i += 2
        else:
            i += 1

    template = wikitext[start+2:i]  # 去掉 {{ 和 }}

    # 去除第一行模板名
    lines = template.split('\n')
    lines = [l for l in lines if not re.match(r'^\s*(?:Unit)?Infobox\s*$', l, re.IGNORECASE)]

    fields = {}
    sections = []
    current_section = None
    current_key = None
    current_value = []

    for line in lines:
        line = line.strip()

        # 跳过空行和注释
        if not line:
            # 保存当前累积值
            if current_key and current_value:
                value = ' '.join(current_value).strip()
                field = {"value": value}
                if current_section is not None:
                    sections[-1]["fields"][current_key] = field
                else:
                    fields[current_key] = field
                current_key = None
                current_value = []
            continue

        # 检查是否是行内字段: | fieldname = value
        m = re.match(r'\|\s*([^=]+?)\s*=\s*(.*)', line)
        if m:
            # 保存上一个字段
            if current_key and current_value:
                value = ' '.join(current_value).strip()
                field = {"value": value}
                if current_section is not None:
                    sections[-1]["fields"][current_key] = field
                else:
                    fields[current_key] = field

            key = clean(m.group(1))
            val = clean(m.group(2))
            current_key = key
            current_value = [val] if val else []

            # 检查是否是 section header（值包含 {{ 模板调用如 {{Stats|...}}）
            # 对于行内模板不作特殊处理
        else:
            # 续行：追加到当前值
            if current_key and line:
                current_value.append(clean(line))

    # 保存最后一个字段
    if current_key and current_value:
        value = ' '.join(current_value).strip()
        field = {"value": value}
        if current_section is not None:
            sections[-1]["fields"][current_key] = field
        else:
            fields[current_key] = field

    return {"fields": fields, "sections": sections}


def parse_attack_health(value):
    """解析 attack/health 格式: "5 / 2", "7/14", "{{AttackHealth|5|2}}", "{{AttackHealth|3/1}}" """
    # 先尝试从 {{AttackHealth|...}} 中提取
    ah_match = re.findall(r'\{\{AttackHealth\|(\d+)[|/](\d+)\}\}', value)
    if ah_match:
        # 取第一个匹配（通常就是唯一的）
        return {"attack": int(ah_match[0][0]), "health": int(ah_match[0][1])}
    # 纯文本 "X / Y" 格式
    m = re.match(r'(\d+)\s*/\s*(\d+)', value)
    if m:
        return {"attack": int(m.group(1)), "health": int(m.group(2))}
    return None


def parse_wikitext_page(wikitext):
    """
    完整解析一个 wikitext 页面，返回结构化数据。
    与 parser.py 输出格式兼容。
    """
    # 1. Infobox
    ibox = parse_infobox(wikitext)
    fields = ibox["fields"]

    # 2. wikitable — 解析 {| ... |} 格式
    tables = []
    for table_match in re.finditer(r'\{\|\s*class="wikitable"(.*?)\|\}', wikitext, re.DOTALL):
        table_text = table_match.group(1)
        # 标准化：!! → 换行后的 !, || → 换行后的 |
        table_text = re.sub(r'(?<!\n)!!', '\n!', table_text)
        table_text = re.sub(r'(?<!\n)\|\|', '\n|', table_text)
        # 按 |- 分割行
        row_texts = re.split(r'\n\|\-', '\n' + table_text)
        rows = []
        for row_text in row_texts:
            if not row_text.strip():
                continue
            cells = []
            for cell_match in re.finditer(r'(?:^|\n)([!|])\s*(.*?)(?=\n[!|]|\n\|\-|\n\|\}|\Z)', row_text, re.DOTALL):
                cell_content = cell_match.group(2).strip()
                cell_content = ' '.join(cell_content.split())
                cells.append(clean(cell_content))
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)

    # 3. 分类 — 从 [[Category:xxx]] 提取
    categories = re.findall(r'\[\[Category:([^\]]+)\]\]', wikitext)

    # 4. 摘要 — Infobox 后的第一段文字
    m2 = re.search(r'\{\{[A-Za-z]+\s*\n', wikitext)
    if m2:
        # 找到匹配的 }}
        depth = 1
        i = m2.end()
        while i < len(wikitext) and depth > 0:
            if wikitext[i:i+2] == '{{':
                depth += 1
                i += 2
            elif wikitext[i:i+2] == '}}':
                depth -= 1
                if depth == 0:
                    break
                i += 2
            else:
                i += 1
        ibox_end = i + 2
    else:
        ibox_end = 0
    after_ibox = wikitext[ibox_end:]
    summary_m = re.match(r'\s*(.*?)(?=\n==|\n\n|\Z)', after_ibox, re.DOTALL)
    summary = clean(re.sub(r"'''?|<[^>]+>", '', summary_m.group(1))) if summary_m else ""

    # 5. 判断类型 — 优先用模板名
    tmpl_match = re.match(r'\{\{([A-Za-z]+)', wikitext)
    tmpl_name = tmpl_match.group(1) if tmpl_match else ""
    field_keys = set(fields.keys()) if fields else set()

    type_map = {
        "UnitCard": "unit",
        "SpellCard": "spell",
        "EquipmentCard": "equipment",
        "RoomCard": "room",
        "Enemy": "enemy",
        "Artifact": "artifact",
        "UnitArtifact": "artifact",
        "EnemyArtifact": "enemy",
    }
    page_type = type_map.get(tmpl_name, "unknown")

    if page_type == "unknown":
        if "cost" in field_keys:
            page_type = "unit"
        elif "ring2" in field_keys or "ring3" in field_keys or "stats0" in field_keys:
            page_type = "enemy"
        elif "effect" in field_keys:
            page_type = "artifact"

    # 6. 提取统计数据
    stats = {}
    for k, v in fields.items():
        if isinstance(v, dict):
            ah = parse_attack_health(v.get("value", ""))
            if ah:
                key = k.lower().replace(" ", "_")
                stats[key] = ah

    # 7. 提取图片
    image = fields.get("image", {}).get("value", "")

    return {
        "type": page_type,
        "title": "",
        "image": image,
        "fields": fields,
        "tables": tables,
        "stats": stats if stats else None,
        "meta": {"categories": categories},
        "summary": summary,
    }


# ============================================================
# 解析爬虫下载的 JSON 文件
# ============================================================

def parse_crawled_json(filepath):
    """
    解析 crawler.js 下载的 JSON 文件。
    格式: { "Page Title": "wikitext content", ... }
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []
    for title, wikitext in data.items():
        if not wikitext:
            print(f"  SKIP {title} (empty)", file=__import__('sys').stderr)
            continue

        try:
            parsed = parse_wikitext_page(wikitext)
            parsed["title"] = title
            parsed["source_page"] = title
            results.append(parsed)
            print(f"  OK  {title} -> {parsed['type']}", file=__import__('sys').stderr)
        except Exception as e:
            print(f"  ERR {title}: {e}", file=__import__('sys').stderr)

    return results


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python wikitext_parser.py <crawled_file.json> [output.json]", file=sys.stderr)
        sys.exit(1)

    outfile = sys.argv[2] if len(sys.argv) > 2 else None
    results = parse_crawled_json(sys.argv[1])

    json_str = json.dumps(results, ensure_ascii=False, indent=2)
    if outfile:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"\nWrote {len(results)} items to {outfile}", file=sys.stderr)
    else:
        print(json_str)
