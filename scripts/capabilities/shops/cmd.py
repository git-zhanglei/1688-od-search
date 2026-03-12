#!/usr/bin/env python3
"""店铺查询命令 — CLI 入口"""

COMMAND_NAME = "shops"
COMMAND_DESC = "查绑定店铺"

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..')))

from _auth import get_ak_from_env
from _output import print_output, print_error
from capabilities.shops.service import check_shop_status


def main():
    ak_id, _ = get_ak_from_env()
    if not ak_id:
        print_output(False,
                     "❌ AK 未配置，无法查询店铺。\n\n运行: `cli.py configure YOUR_AK`",
                     {"total": 0, "valid_count": 0, "expired_count": 0, "shops": []})
        return

    try:
        status = check_shop_status()
        print_output(True, status["markdown"], {
            "total": len(status["all"]),
            "valid_count": len(status["valid"]),
            "expired_count": len(status["expired"]),
            "shops": [
                {"code": s.code, "name": s.name, "channel": s.channel,
                 "is_authorized": s.is_authorized}
                for s in status["all"]
            ],
        })
    except Exception as e:
        print_error(e, {"total": 0, "valid_count": 0, "expired_count": 0, "shops": []})


if __name__ == "__main__":
    main()
