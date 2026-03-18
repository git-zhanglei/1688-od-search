#!/usr/bin/env python3
"""铺货命令 — CLI 入口"""

COMMAND_NAME = "publish"
COMMAND_DESC = "铺货到下游店铺"

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..')))

import argparse
from datetime import datetime

from _output import print_output, print_error
from _const import PUBLISH_LIMIT
from capabilities.publish.service import (
    load_products_by_data_id,
    normalize_item_ids,
    publish_with_check,
    save_publish_snapshot,
)


def main():
    parser = argparse.ArgumentParser(description="1688 铺货到下游店铺")
    parser.add_argument("--shop-code", required=True, help="目标店铺代码")
    parser.add_argument("--dry-run", action="store_true", help="仅做预检查，不执行实际铺货")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item-ids", help="商品ID列表，逗号分隔")
    group.add_argument("--data-id", help="选品结果的 data_id（从 search 获取）")
    args = parser.parse_args()

    if args.data_id:
        item_ids = load_products_by_data_id(args.data_id)
        if not item_ids:
            print_output(False,
                         f"❌ 未找到 data_id=`{args.data_id}` 对应的选品结果，请重新搜索后获取新的 data_id。",
                         {"success": False})
            return
    else:
        item_ids = [x.strip() for x in args.item_ids.split(",") if x.strip()]

    item_ids = normalize_item_ids(item_ids)

    if not item_ids:
        print_output(False,
                     "❌ 没有可用的商品ID，请检查 `--item-ids` 或 `--data-id`。",
                     {"success": False})
        return

    try:
        result = publish_with_check(item_ids, args.shop_code, dry_run=args.dry_run)
        submitted_count = min(result["origin_count"], PUBLISH_LIMIT)
        data = {
            "success": result["success"],
            "origin_count": result["origin_count"],
            "submitted_count": submitted_count,
            "error_code": result["result"].error_code,
            "dry_run": args.dry_run,
            "risk_level": "write",
        }
        if args.dry_run and result["success"]:
            data["confirm_prompt"] = (
                f"确认铺货 {submitted_count} 个商品到目标店铺？"
                "去掉 --dry-run 执行正式铺货。"
            )
        if not args.dry_run:
            try:
                time = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{datetime.now().microsecond // 1000:03d}"
                save_publish_snapshot({
                    "time": time,
                    "api_request": result.get("_api_request"),
                    "api_response": result.get("_api_response"),
                    "meta": {
                        "shop_code": args.shop_code,
                        "dry_run": False,
                        "search_data_id": args.data_id or "",
                    },
                    "cli_output": {
                        "success": result["success"],
                        "markdown": result["markdown"],
                        "data": data,
                    },
                })
            except Exception:
                data.pop("time", None)
        print_output(result["success"], result["markdown"], data)
    except Exception as e:
        print_error(e, {"success": False})


if __name__ == "__main__":
    main()
