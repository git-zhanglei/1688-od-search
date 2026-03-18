#!/usr/bin/env python3
"""AK 配置服务 — 校验、写入、状态查询"""

import json
import os
import sys
from pathlib import Path
from typing import Tuple

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..')))
from _const import OPENCLAW_CONFIG_PATH as CONFIG_PATH

SKILL_NAME = "1688-shopkeeper"


def validate_ak(ak: str) -> Tuple[bool, str]:
    """校验明文 AK 格式，返回 (is_valid, error_msg)"""
    if not ak:
        return False, "AK 不能为空"
    if len(ak) < 32:
        return False, f"AK 长度不足（当前 {len(ak)}，需要至少 32 位）"
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-=")
    if not all(c in allowed for c in ak):
        return False, "AK 包含非法字符"
    return True, ""


def configure_via_gateway(api_key: str) -> bool:
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
                    "apiKey": api_key
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


def configure_via_file(api_key: str) -> bool:
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
        skill_entry = config["skills"]["entries"][SKILL_NAME]
        # apiKey 作为唯一写入目标，并移除旧格式 env.ALI_1688_AK 避免误导
        skill_entry["apiKey"] = api_key
        if "env" in skill_entry and isinstance(skill_entry["env"], dict):
            skill_entry["env"].pop("ALI_1688_AK", None)
            if not skill_entry["env"]:
                del skill_entry["env"]

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
        skill_entry = entries.get(SKILL_NAME, {})
        api_key = skill_entry.get("apiKey")
        if isinstance(api_key, str) and api_key:
            return True, api_key
        # 兼容旧格式：env.ALI_1688_AK
        legacy = skill_entry.get("env", {}).get("ALI_1688_AK", "")
        if legacy:
            return True, legacy
        return False, ""
    except Exception:
        return False, ""
