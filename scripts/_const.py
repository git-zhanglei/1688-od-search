#!/usr/bin/env python3
"""
1688-shopkeeper 全局常量

所有模块统一从这里 import，禁止各模块自定义同名常量。
"""

# ── 渠道映射表（唯一权威来源）────────────────────────────────────────────────
# key: 对外暴露的渠道名（用户输入 / CLI 参数 / 中文别名）
# value: 1688 API 实际接受的 channel 值

CHANNEL_MAP: dict[str, str] = {
    # 英文标准名（CLI 参数直传）
    "douyin":       "douyin",
    "pinduoduo":    "pinduoduo",
    "xiaohongshu":  "xiaohongshu",
    "thyny":        "thyny",
    "taobao":       "thyny",       # taobao 在 API 侧叫 thyny

    # 中文别名（shops API 返回的 channel 可能含中文，此处做映射；CLI 不会传入中文）
    "抖音":         "douyin",
    "抖店":         "douyin",
    "拼多多":       "pinduoduo",
    "小红书":       "xiaohongshu",
    "淘宝":         "thyny",
}

# Skill 版本
SKILL_VERSION = "1.0.0"

# 接口返回/提交数量限制（按最新接口文档）
SEARCH_LIMIT = 20
PUBLISH_LIMIT = 20

# ── OpenClaw 配置文件路径（唯一权威来源）──────────────────────────────────────
import os
from pathlib import Path

# 优先读取 OPENCLAW_CONFIG_DIR 环境变量，默认 ~/.openclaw
OPENCLAW_CONFIG_PATH: Path = Path(
    os.environ.get("OPENCLAW_CONFIG_DIR", Path.home() / ".openclaw")
) / "openclaw.json"

# ── 数据目录（与 skill 代码解耦）──────────────────────────────────────────────

# 优先级：
# 1) 显式环境变量 OPENCLAW_WORKSPACE_DIR（推荐）
# 2) 历史路径（兼容老版本）
# 3) 通用默认路径（与具体 workspace 名称解耦）
_LEGACY_WORKSPACE = os.path.expanduser("~/.openclaw/workspace-clawshop")
_DEFAULT_WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
WORKSPACE_DIR = os.environ.get("OPENCLAW_WORKSPACE_DIR") or (
    _LEGACY_WORKSPACE if os.path.isdir(_LEGACY_WORKSPACE) else _DEFAULT_WORKSPACE
)

DATA_DIR = os.path.join(WORKSPACE_DIR, "1688-skill-data", "products")
PROD_DETAIL_DATA_DIR = os.path.join(WORKSPACE_DIR, "1688-skill-data", "prod_detail")
