#!/usr/bin/env python3
"""
1688-skills 全局常量

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
    "taobao":       "thyny",       # taobao 在 API 侧叫 thyny

    # 中文别名（用户自然语言）
    "抖音":         "douyin",
    "抖店":         "douyin",
    "拼多多":       "pinduoduo",
    "小红书":       "xiaohongshu",
    "淘宝":         "thyny",
}

# 默认渠道
DEFAULT_CHANNEL = "douyin"

# ── 数据目录（与 skill 代码解耦）──────────────────────────────────────────────
import os
DATA_DIR = os.path.join(
    os.path.expanduser("~/.openclaw/workspace-clawshop"),
    "1688-skill-data",
    "products",
)
