#!/usr/bin/env python3
"""店铺经营日报命令 — CLI 入口"""

COMMAND_NAME = "shop_daily"
COMMAND_DESC = "店铺经营日报"

import argparse
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..")))

from _auth import get_ak_from_env
from _output import print_error, print_output
from capabilities.shop_daily.service import fetch_shop_daily


def main():
    parser = argparse.ArgumentParser(description="店铺经营日报")
    parser.parse_args()

    ak_id, _ = get_ak_from_env()
    if not ak_id:
        print_output(
            False,
            "❌ AK 未配置，无法生成店铺经营日报。\n\n运行: `cli.py configure YOUR_AK`",
            {"channels": [], "opportunity": {}, "raw": {}},
        )
        return

    try:
        result = fetch_shop_daily()
        print_output(True, result["markdown"], result["data"])
    except Exception as e:
        print_error(e, {"channels": [], "opportunity": {}, "raw": {}})


if __name__ == "__main__":
    main()
