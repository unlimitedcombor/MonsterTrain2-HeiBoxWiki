"""
将 parser.py 输出的 JSON 转换为小黑盒百科模板调用参数。
用法: python convert.py data.json > 词条文本.txt
"""

import sys
import json


IMAGE_BASE = "https://static.wikitide.net/monstertrain2wiki"  # 实际需替换为你的 CDN

def fix_image_url(fname):
    """将文件名转为完整 URL（通过 Special:FilePath）"""
    if not fname:
        return ""
    fname = fname.strip()
    if fname.startswith("http"):
        return fname
    # 清理 wiki 标记: [[File:xxx.png|thumb]] → xxx.png
    import re
    m = re.search(r'\[\[File:([^|\]]+)', fname)
    if m:
        fname = m.group(1)
    return f"https://monstertrain2.miraheze.org/wiki/Special:FilePath/{fname}"


def get_field(fields, key, default=""):
    """安全获取字段值"""
    v = fields.get(key, {})
    if isinstance(v, dict):
        return v.get("value", default) or default
    return v or default


def convert_to_template(item):
    """将单条解析数据转换为模板调用"""
    t = item["type"]
    fields = item.get("fields", {})

    dispatch = {
        "unit":      ("怪物火车2-卡牌名片", convert_unit),
        "spell":     ("怪物火车2-法术",   convert_spell),
        "equipment": ("怪物火车2-装备",   convert_equipment),
        "room":      ("怪物火车2-房间",   convert_room),
        "enemy":     ("怪物火车2-敌方单位", convert_enemy),
        "artifact":  ("怪物火车2-神器",   convert_artifact),
    }

    if t in dispatch:
        tmpl_name, fn = dispatch[t]
        return fn(fields, item, tmpl_name)

    return f"<!-- 未知类型: {item.get('title', '')} -->"


def convert_card_common(fields, item):
    """提取法术/装备/房间共同字段"""
    return {
        "name": item["title"],
        "image": fix_image_url(item.get("image", "")),
        "clan": get_field(fields, "clan"),
        "cost": get_field(fields, "cost"),
        "rarity": get_field(fields, "rarity"),
        "effect": get_field(fields, "effect"),
        "flavor": get_field(fields, "flavor"),
        "artist": get_field(fields, "artist"),
    }


def convert_unit(fields, item, tmpl_name):
    params = convert_card_common(fields, item)
    params["type"] = get_field(fields, "type")
    params["banner"] = get_field(fields, "banner")
    params["size"] = get_field(fields, "size")
    params["ability"] = get_field(fields, "ability")
    stats = get_field(fields, "stats")
    if " / " in stats:
        parts = stats.split(" / ")
        params["attack"] = parts[0].strip()
        params["health"] = parts[1].strip()
    return format_template_call(tmpl_name, params)


def convert_spell(fields, item, tmpl_name):
    return format_template_call(tmpl_name, convert_card_common(fields, item))


def convert_equipment(fields, item, tmpl_name):
    return format_template_call(tmpl_name, convert_card_common(fields, item))


def convert_room(fields, item, tmpl_name):
    return format_template_call(tmpl_name, convert_card_common(fields, item))


def convert_enemy(fields, item, tmpl_name):
    params = {
        "name": item["title"],
        "image": fix_image_url(item.get("image", "")),
    }

    # 从 item["stats"] 使用已解析的 attack/health
    parsed_stats = item.get("stats") or {}
    if "stats0" in parsed_stats:
        params["baseline_attack"] = parsed_stats["stats0"]["attack"]
        params["baseline_health"] = parsed_stats["stats0"]["health"]
    if "stats8" in parsed_stats:
        params["covenant8_attack"] = parsed_stats["stats8"]["attack"]
        params["covenant8_health"] = parsed_stats["stats8"]["health"]

    # 出现位置 (ring1-ring9)
    for i in range(1, 10):
        rk = f"ring{i}"
        v = get_field(fields, rk)
        if v and v != "None":
            params[rk] = v

    # 能力 (ability0, ability1, ...)
    abilities = []
    for k in sorted(fields.keys()):
        if k.startswith("ability") and k != "ability":
            v = get_field(fields, k)
            if v and v != "None":
                abilities.append(v)
    if abilities:
        params["ability"] = " | ".join(abilities)

    # 背景
    for k in ["flavor", "titan", "artist"]:
        v = get_field(fields, k)
        if v:
            params[k] = v

    return format_template_call(tmpl_name, params)


def convert_artifact(fields, item, tmpl_name):
    params = {
        "name": item["title"],
        "image": fix_image_url(item.get("image", "")),
    }
    for k in ["clan", "rarity", "effect", "flavor"]:
        v = fields.get(k, {})
        if isinstance(v, dict):
            params[k] = v.get("value", "")
        else:
            params[k] = ""

    return format_template_call(tmpl_name, params)


def format_template_call(template_name, params):
    """格式化为小黑盒百科模板调用语法"""
    lines = [f"{{{{{template_name}"]
    for key, value in params.items():
        if value:
            val = str(value).replace("|", "&#124;")
            lines.append(f"|{key}={val}")
    lines.append("}}")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python convert.py data.json [output.txt]", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = []
    for item in data:
        lines.append(convert_to_template(item))
        lines.append("")

    output = "\n".join(lines)
    outfile = sys.argv[2] if len(sys.argv) > 2 else None
    if outfile:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Wrote {len(data)} templates to {outfile}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
