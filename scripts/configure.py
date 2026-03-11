#!/usr/bin/env python3
"""
AK 配置助手

优先通过 OpenClaw Gateway REST API 写入配置（安全，不破坏 JSON5 格式）。
Gateway 不可用时 fallback 到直接写文件（向后兼容）。

Usage:
    python3 configure.py              # 查看当前配置状态
    python3 configure.py YOUR_AK      # 写入 AK
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
SKILL_NAME = "1688-skills"


# ── 验证 ─────────────────────────────────────────────────────────────────────

def validate_ak(ak: str) -> tuple[bool, str]:
    if not ak:
        return False, "AK 不能为空"
    if len(ak) < 32:
        return False, f"AK 长度不足（当前 {len(ak)}，需要至少 32 位）"
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-=")
    if not all(c in allowed for c in ak):
        return False, "AK 包含非法字符"
    return True, ""


# ── 方式一：Gateway API ───────────────────────────────────────────────────────

def configure_via_gateway(ak: str) -> bool:
    """
    通过 OpenClaw Gateway REST API 写入配置。
    安全：不直接读写 openclaw.json，避免破坏 JSON5 注释/格式。
    """
    try:
        import requests
    except ImportError:
        return False

    gateway_url = os.environ.get("OPENCLAW_GATEWAY_URL", "http://localhost:18789")
    token = os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")

    payload = {
        "skills": {
            "entries": {
                SKILL_NAME: {
                    "env": {"ALI_1688_AK": ak}
                }
            }
        }
    }

    try:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = requests.patch(
            f"{gateway_url}/api/config",
            headers=headers,
            json=payload,
            timeout=5,
        )
        if resp.ok:
            print(f"✅ AK 已通过 Gateway API 写入配置")
            return True
        else:
            print(f"⚠️  Gateway API 返回 {resp.status_code}，尝试直接写文件...")
            return False
    except Exception:
        return False


# ── 方式二：直接写文件（fallback）────────────────────────────────────────────

def configure_via_file(ak: str) -> bool:
    """直接写入 openclaw.json（fallback，不破坏已有结构）"""
    try:
        config: dict = {}
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        config = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"⚠️  配置文件解析失败，将创建新配置: {e}")

        config.setdefault("skills", {})
        config["skills"].setdefault("entries", {})
        config["skills"]["entries"].setdefault(SKILL_NAME, {})
        config["skills"]["entries"][SKILL_NAME].setdefault("env", {})

        old_ak = config["skills"]["entries"][SKILL_NAME]["env"].get("ALI_1688_AK", "")
        config["skills"]["entries"][SKILL_NAME]["env"]["ALI_1688_AK"] = ak

        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        tag = "更新" if old_ak else "新增"
        print(f"📝 {tag} AK（写入文件）: {ak[:4]}****{ak[-4:]}")
        print(f"📁 配置文件: {CONFIG_PATH}")
        return True

    except PermissionError:
        print(f"❌ 权限错误: 无法写入 {CONFIG_PATH}")
        return False
    except Exception as e:
        print(f"❌ 配置失败: {e}")
        return False


# ── 读取当前状态 ──────────────────────────────────────────────────────────────

def check_existing_config() -> tuple[bool, str]:
    """检查是否已有 AK（从环境变量或配置文件）"""
    # 优先检查环境变量（Gateway 注入后的状态）
    env_ak = os.environ.get("ALI_1688_AK", "")
    if env_ak:
        return True, env_ak

    if not CONFIG_PATH.exists():
        return False, ""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        ak = (config
              .get("skills", {})
              .get("entries", {})
              .get(SKILL_NAME, {})
              .get("env", {})
              .get("ALI_1688_AK", ""))
        return bool(ak), ak
    except Exception:
        return False, ""


# ── 主入口 ────────────────────────────────────────────────────────────────────

def main():
    has_existing, existing_ak = check_existing_config()

    # 无参数 → 查看状态
    if len(sys.argv) < 2:
        print("AK 配置助手")
        print("=" * 50)
        if has_existing:
            masked = f"{existing_ak[:4]}****{existing_ak[-4:]}"
            src = "环境变量（已生效）" if os.environ.get("ALI_1688_AK") else "配置文件"
            print(f"✅ 当前已配置 AK: {masked}（来源: {src}）")
        else:
            print("❌ 尚未配置 AK")
        print("\n使用方法: python3 configure.py YOUR_AK_HERE")
        sys.exit(0)

    ak = sys.argv[1].strip()

    # 验证格式
    is_valid, error_msg = validate_ak(ak)
    if not is_valid:
        print(f"❌ {error_msg}")
        sys.exit(1)

    # 写入：Gateway API 优先，fallback 写文件
    ok = configure_via_gateway(ak) or configure_via_file(ak)
    if not ok:
        sys.exit(1)

    print("\n⚠️  重要: 请重启 Gateway 使配置全局生效!")
    print("   openclaw gateway restart")
    print("\n当前会话如需立即使用，请在命令前加:")
    print(f"   ALI_1688_AK={ak[:4]}...{ak[-4:]} python3 cli.py search --query \"XXX\"")


if __name__ == "__main__":
    main()
