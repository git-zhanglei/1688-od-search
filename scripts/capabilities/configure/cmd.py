#!/usr/bin/env python3
"""AK 配置命令 — CLI 入口"""

COMMAND_NAME = "configure"
COMMAND_DESC = "配置 AK"

import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..')))

from _output import print_output, print_error
from capabilities.configure.service import (
    validate_ak, configure_via_gateway, configure_via_file, check_existing_config,
)


def _mask_ak(ak: str) -> str:
    if len(ak) >= 8:
        return f"{ak[:4]}****{ak[-4:]}"
    return "****"


def main():
    try:
        has_existing, existing_ak = check_existing_config()

        # 无参数 → 查看状态
        if len(sys.argv) < 2:
            if has_existing:
                src = ("环境变量（已生效）" if os.environ.get("ALI_1688_AK")
                       else "OpenClaw 配置（新会话/重载后生效）")
                md = f"✅ AK 已配置: `{_mask_ak(existing_ak)}`（来源: {src}）"
            else:
                md = "❌ 尚未配置 AK\n\n运行: `cli.py configure YOUR_AK`"
            print_output(has_existing, md, {"configured": has_existing})
            return

        ak = sys.argv[1].strip()
        is_valid, error_msg = validate_ak(ak)
        if not is_valid:
            print_output(False, f"❌ {error_msg}", {"configured": False})
            return

        write_ok = configure_via_gateway(ak) or configure_via_file(ak)
        if not write_ok:
            print_output(False,
                         "❌ AK 写入失败（Gateway 不可用且 fallback 被拒绝/失败），请检查 Gateway 状态或文件权限",
                         {"configured": False})
            return

        md = (
            f"✅ AK 已保存: `{_mask_ak(ak)}`\n\n"
            "后续由 OpenClaw 配置注入生效（以配置为准，不使用本地会话缓存）。\n\n"
            "若当前会话仍提示 AK未配置或AK无效，请新开会话或执行：`openclaw secrets reload`（或 `openclaw gateway restart`）"
        )
        print_output(True, md, {"configured": True})
    except Exception as e:
        print_error(e, {"configured": False})


if __name__ == "__main__":
    main()
