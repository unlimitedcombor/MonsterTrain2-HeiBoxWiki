"""
Monster Train 2 Wiki HTML Parser
解析从 monstertrain2.miraheze.org 保存的页面，提取结构化数据为 JSON。
用法: python parser.py demo/*.html > data.json
"""

import sys
import json
import re
import html as html_mod
from pathlib import Path


def clean(text):
    """去除 HTML 实体 &nbsp; 等，压缩空白"""
    text = html_mod.unescape(text)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = text.replace('\xa0', ' ')
    text = text.replace(' ', ' ')
    # 规范化 Unicode 引号
    text = text.replace('‘', "'").replace('’', "'")
    text = text.replace('“', '"').replace('”', '"')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_infobox_data(page_html):
    """从页面 HTML 中提取 infobox 的所有数据字段。

    返回:
        {
            "title": "...",
            "image": "...",
            "groups": [
                {
                    "header": "Stats",
                    "fields": [{"source": "stats0", "label": "Baseline", "value": "5 / 2"}, ...]
                },
                ...
            ]
        }
    """
    # 定位 infobox
    m = re.search(r'<aside[^>]*portable-infobox.*?</aside>', page_html, re.DOTALL)
    if not m:
        return {"title": "", "image": "", "groups": []}

    ibox = m.group(0)

    result = {"title": "", "image": "", "groups": []}

    # 标题
    tm = re.search(r'<h2[^>]*pi-title[^>]*>(.*?)</h2>', ibox, re.DOTALL)
    if tm:
        result["title"] = clean(tm.group(1))

    # 图片 — 从 img.pi-image-thumbnail 提取，用 srcset 中的原始 URL
    # 先找到 img 标签
    img_match = re.search(r'<img[^>]*pi-image-thumbnail[^>]*>', ibox)
    if img_match:
        img_tag = img_match.group(0)
        # 从 srcset 提取 1x URL
        sm = re.search(r'srcset="[^"]*?([^\s]+)\s+1x', img_tag)
        if sm:
            url = sm.group(1)
        else:
            sm = re.search(r'src="([^"]+)"', img_tag)
            url = sm.group(1) if sm else ""
        if url:
            url = re.sub(r'\./[^/]+_files/', '', url)
            url = re.sub(r'/thumb/', '/', url)
            url = re.sub(r'/\d+px-[^/]+$', '', url)
            if url.startswith('//'):
                url = 'https:' + url
            result["image"] = url

    # 分段解析策略：
    # 1. 找到所有 data-source="xxx" 的位置
    # 2. 从该位置向后找到 pi-data-label（h3）提取 label
    # 3. 从该位置向后找到 pi-data-value 的起始 div，用括号计数找到匹配的 </div>，提取 value
    # 4. 找到所有 pi-header（h2），用于分组

    groups = []
    current_group = {"header": "", "fields": []}

    # 找所有 pi-header
    header_positions = []
    for m in re.finditer(r'<h2[^>]*pi-header[^>]*>(.*?)</h2>', ibox, re.DOTALL):
        header_positions.append((m.start(), clean(m.group(0))))

    # 找所有 data-source（只在 div 上，排除 h2/figcaption 等非数据元素）
    source_positions = []
    for m in re.finditer(r'<div[^>]*pi-data[^>]*data-source="([^"]+)"', ibox):
        source_name = m.group(1)
        # 向后查找 pi-data-label
        after = ibox[m.end():]
        label = ""
        lm = re.search(r'<h3[^>]*pi-data-label[^>]*>(.*?)</h3>', after, re.DOTALL)
        if lm:
            label = clean(lm.group(1))

        # 向后查找 pi-data-value，用括号计数获取完整值
        vm_start = re.search(r'<div[^>]*pi-data-value[^>]*>', after, re.DOTALL)
        value = ""
        if vm_start:
            vpos = vm_start.end()  # 在 after 内的偏移
            depth = 1
            i = vpos
            while i < len(after) and depth > 0:
                if after[i:i+4] == '<div':
                    depth += 1
                    i += 4
                elif after[i:i+6] == '</div>':
                    depth -= 1
                    if depth == 0:
                        value = clean(after[vpos:i])
                    i += 6
                else:
                    i += 1

        source_positions.append((m.start(), source_name, label, value))

    # 合并 header 和 source，按位置排序
    items = []
    for pos, hdr in header_positions:
        items.append(("header", pos, hdr))
    for pos, src, lbl, val in source_positions:
        items.append(("data", pos, {"source": src, "label": lbl, "value": val}))

    items.sort(key=lambda x: x[1])

    for item in items:
        kind = item[0]
        if kind == "header":
            if current_group["header"] or current_group["fields"]:
                groups.append(current_group)
            current_group = {"header": item[2], "fields": []}
        elif kind == "data":
            info = item[2]
            current_group["fields"].append(info)

    # 保存最后的 group
    if current_group["header"] or current_group["fields"]:
        groups.append(current_group)

    result["groups"] = groups
    return result


def parse_attack_health(value):
    """从 "5 / 2" 格式的值中提取 attack/health"""
    m = re.match(r'(\d+)\s*/\s*(\d+)', value)
    if m:
        return {"attack": int(m.group(1)), "health": int(m.group(2))}
    return None


def extract_all_fields(ibox_data):
    """
    将 groups 模式展平:
      - 顶层 fields (无 header 的 group 中的字段)
      - 每个有 header 的 group 分别存放
    同时解析 attack/health
    """
    result = {}
    stats = {}
    for g in ibox_data["groups"]:
        if g["header"]:
            # 命名 section
            key = g["header"].lower().replace(" ", "_")
            fields = {}
            for f in g["fields"]:
                fields[f["source"]] = {"label": f["label"], "value": f["value"]}
                # 检查是否是 attack/health 数值
                ah = parse_attack_health(f["value"])
                if ah:
                    label_key = f["label"].lower().replace(" ", "_")
                    stats[label_key] = ah
            result[key] = fields
        else:
            # 顶层字段
            for f in g["fields"]:
                result[f["source"]] = {"label": f["label"], "value": f["value"]}
                ah = parse_attack_health(f["value"])
                if ah:
                    stats[f["source"]] = ah
    return result, stats


def extract_wikitable_rows(html_content):
    """从 wikitable 表格中提取数据行"""
    tables = []
    for table_match in re.finditer(r'<table[^>]*wikitable[^>]*>(.*?)</table>', html_content, re.DOTALL):
        rows = []
        for tr in re.finditer(r'<tr>(.*?)</tr>', table_match.group(1), re.DOTALL):
            cells = []
            for cell in re.finditer(r'<(td|th)[^>]*>(.*?)</\1>', tr.group(1), re.DOTALL):
                cells.append(clean(cell.group(2)))
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def extract_meta(page_html):
    """提取页面元数据"""
    meta = {}
    m = re.search(r'"wgCategories":\[(.*?)\]', page_html)
    if m:
        meta["categories"] = re.findall(r'"([^"]+)"', m.group(1))
    m = re.search(r'<meta property="og:image" content="([^"]+)"', page_html)
    if m:
        meta["og_image"] = m.group(1)
    m = re.search(r'"wgCurRevisionId":(\d+)', page_html)
    if m:
        meta["revision_id"] = int(m.group(1))
    return meta


def classify_page(all_fields, all_sources):
    """推断页面类型"""
    if "cost" in all_sources:
        return "unit"
    if "ring2" in all_sources or "ring3" in all_sources or "stats0" in all_sources:
        return "enemy"
    if "effect" in all_sources:
        return "artifact"
    return "unknown"


def parse_page(filepath):
    """解析单个页面，返回完整结构化数据"""
    with open(filepath, "r", encoding="utf-8") as f:
        page_html = f.read()

    ibox = extract_infobox_data(page_html)
    fields, stats = extract_all_fields(ibox)

    # 获取所有 source 名
    all_sources = set()
    for v in fields.values():
        if isinstance(v, dict) and "value" in v:
            all_sources.add("dummy")  # placeholder
    for g in ibox["groups"]:
        for f in g["fields"]:
            all_sources.add(f["source"])

    data = {
        "title": ibox["title"],
        "image": ibox["image"],
        "fields": fields,
        "stats": stats if stats else None,
        "tables": extract_wikitable_rows(page_html),
        "meta": extract_meta(page_html),
    }
    data["type"] = classify_page(fields, all_sources)

    # 摘要段落
    m = re.search(r'</aside>\s*</div>\s*<p>(.*?)</p>', page_html, re.DOTALL)
    if m:
        data["summary"] = clean(m.group(1))

    return data


def main():
    if len(sys.argv) < 2:
        print("Usage: python parser.py <html_files...> [output.json]", file=sys.stderr)
        print("       python parser.py demo/ data.json", file=sys.stderr)
        sys.exit(1)

    args = sys.argv[1:]
    outfile = None
    if args and args[-1].endswith('.json'):
        outfile = args[-1]
        args = args[:-1]

    results = []
    for pattern in args:
        p = Path(pattern)
        if p.is_dir():
            files = sorted(p.glob("*.html"))
        else:
            files = [p]

        for f in files:
            try:
                data = parse_page(str(f))
                data["source_file"] = f.name
                results.append(data)
                print(f"  OK  {f.name} -> {data['type']}", file=sys.stderr)
            except Exception as e:
                print(f"  ERR {f.name}: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)

    json_str = json.dumps(results, ensure_ascii=False, indent=2)
    if outfile:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"  -> Wrote {len(results)} items to {outfile}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
