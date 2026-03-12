#!/usr/bin/env python3
"""配置状态检查命令 — CLI 入口（无 service 层，逻辑足够简单）"""

COMMAND_NAME = "check"
COMMAND_DESC = "检查配置状态"

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..')))

from pathlib import Path
from _auth import get_ak_from_env
from _output import print_output
from _const import DATA_DIR


def check_status() -> dict:
    lines = []
    ok = True

    # 1. AK（环境变量 → session 文件 fallback）
    ak_id, _ = get_ak_from_env()
    if ak_id:
        masked = f"{ak_id[:4]}****{ak_id[-4:]}" if len(ak_id) >= 8 else "****"
        lines.append(f"✅ AK 已配置: {masked}")
        ak_ok = True
    else:
        lines.append("❌ AK 未配置 — 运行: `cli.py configure YOUR_AK`")
        ak_ok = False
        ok = False

    # 2. 店铺（仅 AK 正常时查）
    shops_count = 0
    expired_count = 0
    if ak_ok:
        try:
            from capabilities.shops.service import list_bound_shops
            shops = list_bound_shops()
            shops_count = len(shops)
            expired_count = sum(1 for s in shops if not s.is_authorized)
            if shops_count == 0:
                lines.append("⚠️  店铺未绑定 — 请在 1688 AI版 APP 中绑定店铺")
            elif expired_count > 0:
                lines.append(f"⚠️  {shops_count} 个店铺，其中 {expired_count} 个授权过期")
            else:
                lines.append(f"✅ 店铺已绑定: {shops_count} 个（全部正常）")
        except Exception as e:
            lines.append(f"⚠️  店铺查询失败: {e}")

    # 3. 数据目录
    try:
        Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
        lines.append(f"✅ 数据目录: {DATA_DIR}")
    except Exception as e:
        lines.append(f"❌ 数据目录不可写: {e}")
        ok = False

    status_icon = "✅ 一切正常" if ok else "⚠️  有问题需处理"
    markdown = ("## 1688-shopkeeper 状态检查\n\n"
                + "\n".join(f"- {l}" for l in lines)
                + f"\n\n**{status_icon}**")

    return {
        "success": ok,
        "markdown": markdown,
        "data": {
            "ak_configured": ak_ok,
            "shops_count": shops_count,
            "expired_count": expired_count,
        },
    }


def main():
    result = check_status()
    print_output(result["success"], result["markdown"], result["data"])


if __name__ == "__main__":
    main()
