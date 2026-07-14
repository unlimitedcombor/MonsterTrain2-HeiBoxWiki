"""
按类型组织模板调用数据，生成：
  1. 分类模板调用文件（每个类型一个 .txt）
  2. 主页面模板调用
  3. 带搜索过滤的索引页
"""

import sys
import json
import re
from pathlib import Path
from scrapy.convert import convert_to_template, fix_image_url, get_field

TYPE_NAMES = {
    "unit":      ("单位",   "怪物火车2-卡牌名片"),
    "spell":     ("法术",   "怪物火车2-法术"),
    "equipment": ("装备",   "怪物火车2-装备"),
    "room":      ("房间",   "怪物火车2-房间"),
    "enemy":     ("敌方单位", "怪物火车2-敌方单位"),
    "artifact":  ("神器",   "怪物火车2-神器"),
}

CLAN_LIST = ["Awoken", "Banished", "Hellhorned", "Lazarus League", "Luna Coven",
             "Melting Remnant", "Pyreborne", "Railforged", "Stygian Guard",
             "Umbra", "Underlegion", "Wurmkin", "Clanless"]


def main():
    if len(sys.argv) < 3:
        print("Usage: python organize.py <parsed.json> <output_dir>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        data = json.load(f)

    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)

    # 按类型分组
    groups = {}
    for item in data:
        t = item["type"]
        if t not in groups:
            groups[t] = []
        groups[t].append(item)

    # 1. 生成每类的模板调用文件
    stats = {}
    for t, items in groups.items():
        if t not in TYPE_NAMES:
            continue
        lines = []
        for item in sorted(items, key=lambda x: x["title"]):
            call = convert_to_template(item)
            lines.append(call)
            lines.append("")

        fname = outdir / f"cards_{t}.txt"
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"  [{t}] {len(items)} entries -> {fname}")

        # 统计氏族分布
        clans = set()
        for item in items:
            clan = get_field(item.get("fields", {}), "clan")
            if clan:
                clans.add(clan)

        stats[t] = {
            "count": len(items),
            "clans": sorted(clans)
        }

    # 2. 生成主页面模板调用
    main_params = {
        "unit_count": stats.get("unit", {}).get("count", 0),
        "unit_clans": "、".join(stats.get("unit", {}).get("clans", [])),
        "spell_count": stats.get("spell", {}).get("count", 0),
        "spell_clans": "、".join(stats.get("spell", {}).get("clans", [])),
        "equip_count": stats.get("equipment", {}).get("count", 0),
        "equip_clans": "、".join(stats.get("equipment", {}).get("clans", [])),
        "room_count": stats.get("room", {}).get("count", 0),
        "room_clans": "、".join(stats.get("room", {}).get("clans", [])),
        "enemy_count": stats.get("enemy", {}).get("count", 0),
        "enemy_rings": "Rings 1-8",
        "artifact_count": stats.get("artifact", {}).get("count", 0),
        "artifact_clans": "、".join(stats.get("artifact", {}).get("clans", [])),
        "clans": CLAN_LIST,
        "last_updated": "2026-06-22",
    }

    main_call = format_main_call("怪物火车2-主页面", main_params)
    with open(outdir / "main_page.txt", "w", encoding="utf-8") as f:
        f.write(main_call)
    print(f"\n  [main] 主页面 -> {outdir / 'main_page.txt'}")

    # 3. 生成全数据 JSON（给搜索用）
    search_data = []
    for item in data:
        if item["type"] not in TYPE_NAMES:
            continue
        fields = item.get("fields", {})
        entry = {
            "name": item["title"],
            "type": item["type"],
            "clan": get_field(fields, "clan"),
            "cost": get_field(fields, "cost"),
            "rarity": get_field(fields, "rarity"),
        }
        if item["type"] == "unit":
            entry["subtype"] = get_field(fields, "type")
            entry["ability"] = get_field(fields, "ability")
        else:
            entry["effect"] = get_field(fields, "effect")
        search_data.append(entry)

    with open(outdir / "search_data.json", "w", encoding="utf-8") as f:
        json.dump(search_data, f, ensure_ascii=False, indent=2)
    print(f"  [data] 搜索数据集 ({len(search_data)} 条) -> {outdir / 'search_data.json'}")

    print(f"\n总计: {sum(s['count'] for s in stats.values())} 条数据")


def format_main_call(tmpl, params):
    lines = [f"{{{{{tmpl}"]
    for k, v in params.items():
        if isinstance(v, list):
            # 列表参数: 每个元素单独一行
            for item in v:
                val = str(item)
                lines.append(f"|{k}={val}")
        elif v:
            val = str(v).replace("|", "&#124;")
            lines.append(f"|{k}={val}")
    lines.append("}}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
