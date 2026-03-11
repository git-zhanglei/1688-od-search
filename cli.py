#!/usr/bin/env python3
"""
1688-skills 统一入口

Usage:
    python3 cli.py <command> [options]

Commands:
    search      文字搜商品      python3 cli.py search --query "连衣裙" [--channel douyin]
    shops       查绑定店铺      python3 cli.py shops
    publish     铺货           python3 cli.py publish --shop-code XXX (--data-id YYY | --item-ids a,b)
    configure   配置AK         python3 cli.py configure YOUR_AK
    check       检查配置状态    python3 cli.py check

所有命令输出 JSON: {"ok": bool, "markdown": str, "data": {...}}
"""

import json
import os
import sys

# 让 scripts/ 目录可直接 import
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

COMMANDS = {
    "search":    "search",
    "shops":     "shops",
    "publish":   "publish",
    "configure": "configure",
    "check":     "cmd_check",
}


def _usage():
    print(json.dumps({
        "ok": False,
        "markdown": (
            "**1688-skills 用法**\n\n"
            "```\n"
            "python3 cli.py search    --query \"商品描述\" [--channel douyin]\n"
            "python3 cli.py shops\n"
            "python3 cli.py publish   --shop-code CODE (--data-id ID | --item-ids a,b,c)\n"
            "python3 cli.py configure YOUR_AK\n"
            "python3 cli.py check\n"
            "```"
        )
    }, ensure_ascii=False, indent=2))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        _usage()
        sys.exit(1)

    cmd = sys.argv[1]
    module_name = COMMANDS[cmd]

    # 把剩余参数还给子模块的 sys.argv
    sys.argv = [f"cli.py {cmd}"] + sys.argv[2:]

    # 动态 import 并执行子模块的 main()
    import importlib
    module = importlib.import_module(module_name)
    module.main()


if __name__ == "__main__":
    main()
