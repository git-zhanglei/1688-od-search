#!/usr/bin/env python3
"""AK 配置服务 — 校验、写入、状态查询"""

import json
import os
from pathlib import Path
from typing import Tuple

from _auth import save_ak_to_session  # noqa: F401 — re-exported for cmd.py

CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
SKILL_NAME = "1688-shopkeeper"


def validate_ak(ak: str) -> Tuple[bool, str]:
    """校验 AK 格式，返回 (is_valid, error_msg)"""
    if not ak:
        return False, "AK 不能为空"
    if len(ak) < 32:
        return False, f"AK 长度不足（当前 {len(ak)}，需要至少 32 位）"
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-=")
    if not all(c in allowed for c in ak):
        return False, "AK 包含非法字符"
    return True, ""


def configure_via_gateway(ak: str) -> bool:
    """通过 OpenClaw Gateway REST API 写入配置（安全，不破坏 JSON5 格式）"""
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
        resp = requests.patch(f"{gateway_url}/api/config",
                              headers=headers, json=payload, timeout=5)
        return resp.ok
    except Exception:
        return False


def configure_via_file(ak: str) -> bool:
    """直接写入 openclaw.json（fallback）"""
    try:
        config: dict = {}
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        config = json.loads(content)
            except json.JSONDecodeError:
                return False

        config.setdefault("skills", {})
        config["skills"].setdefault("entries", {})
        config["skills"]["entries"].setdefault(SKILL_NAME, {})
        config["skills"]["entries"][SKILL_NAME].setdefault("env", {})
        config["skills"]["entries"][SKILL_NAME]["env"]["ALI_1688_AK"] = ak

        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        return True
    except Exception:
        return False


def check_existing_config() -> Tuple[bool, str]:
    """检查是否已有 AK（环境变量优先，其次配置文件）"""
    env_ak = os.environ.get("ALI_1688_AK", "")
    if env_ak:
        return True, env_ak

    if not CONFIG_PATH.exists():
        return False, ""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        entries = config.get("skills", {}).get("entries", {})
        ak = entries.get(SKILL_NAME, {}).get("env", {}).get("ALI_1688_AK", "")
        return bool(ak), ak
    except Exception:
        return False, ""
