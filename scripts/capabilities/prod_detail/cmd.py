#!/usr/bin/env python3
"""商详命令 — CLI 入口"""

COMMAND_NAME = "prod_detail"
COMMAND_DESC = "商品详情"

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..')))

import argparse
from _auth import get_ak_from_env
from _output import print_output, print_error
from capabilities.prod_detail.service import (
    fetch_and_save_product_details,
    load_product_details_result,
)


def main():
    parser = argparse.ArgumentParser(description="1688 商品详情查询")
    parser.add_argument("--item-ids", help="商品ID列表，逗号分隔")
    parser.add_argument("--data-id", help="已保存商品详情的 data_id；可配合 --item-ids 按需读取")
    args = parser.parse_args()

    if not args.item_ids and not args.data_id:
        print_output(False,
                     "❌ 请提供 `--item-ids` 或 `--data-id`。",
                     {"data_id": "", "detail_count": 0, "details": {}})
        return

    item_ids = [x.strip() for x in args.item_ids.split(",") if x.strip()] if args.item_ids else []

    try:
        if args.data_id:
            result = load_product_details_result(args.data_id, item_ids=item_ids)
            print_output(result["success"], result["markdown"], {
                "data_id": result["data_id"],
                "detail_count": result["detail_count"],
                "details": result["details"],
            })
            return

        ak_id, _ = get_ak_from_env()
        if not ak_id:
            print_output(False,
                         "❌ AK 未配置，无法查询商品详情。\n\n运行: `cli.py configure YOUR_AK`",
                         {"data_id": "", "detail_count": 0, "details": {}})
            return

        result = fetch_and_save_product_details(item_ids)
        print_output(True, result["markdown"], {
            "data_id": result["data_id"],
            "detail_count": result["detail_count"],
            "details": result["details"],
        })
    except Exception as e:
        print_error(e, {"data_id": "", "detail_count": 0, "details": {}})


if __name__ == "__main__":
    main()
