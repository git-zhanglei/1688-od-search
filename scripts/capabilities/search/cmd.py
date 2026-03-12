#!/usr/bin/env python3
"""选品命令 — CLI 入口"""

COMMAND_NAME = "search"
COMMAND_DESC = "搜商品"

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..')))

import argparse
from _auth import get_ak_from_env
from _output import print_output, print_error
from capabilities.search.service import search_and_save, product_to_dict


def main():
    ak_id, _ = get_ak_from_env()
    if not ak_id:
        print_output(False,
                     "❌ AK 未配置，无法搜索商品。\n\n运行: `cli.py configure YOUR_AK`",
                     {"data_id": "", "product_count": 0, "products": []})
        return

    parser = argparse.ArgumentParser(description="1688 商品搜索")
    parser.add_argument("--query", "-q", required=True, help="搜索关键词（自然语言描述）")
    parser.add_argument("--channel", "-c", default="",
                        choices=["", "douyin", "taobao", "pinduoduo", "xiaohongshu"],
                        help="下游渠道（可选；未识别渠道意图时留空）")
    args = parser.parse_args()

    try:
        result = search_and_save(args.query, args.channel)
        print_output(True, result["markdown"], {
            "data_id": result["data_id"],
            "product_count": len(result["products"]),
            "products": [product_to_dict(p) for p in result["products"]],
        })
    except Exception as e:
        print_error(e, {"data_id": "", "product_count": 0, "products": []})


if __name__ == "__main__":
    main()
