#!/usr/bin/env python3
"""
AK 配置助手 - 将 AK 持久化到 OpenClaw 配置

使用方法:
    python configure.py YOUR_AK_HERE
    
示例:
    python configure.py YOUR_AK_HERE
"""

import json
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"
SKILL_NAME = "1688-skills"


def validate_ak(ak: str) -> tuple[bool, str]:
    """
    验证 AK 格式
    
    Args:
        ak: 待验证的 AK
    
    Returns:
        (是否有效, 错误信息)
    """
    if not ak:
        return False, "AK 不能为空"
    
    if len(ak) < 32:
        return False, f"AK 长度不足（当前 {len(ak)}，需要至少 32 位）"
    
    # 检查是否为合法的 base64/hex 字符
    allowed_chars = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-=")
    if not all(c in allowed_chars for c in ak):
        return False, "AK 包含非法字符"
    
    return True, ""


def configure_ak(ak: str) -> bool:
    """
    将 AK 配置到 openclaw.json 的 skills.entries 字段（符合 OpenClaw 规范）
    
    写入路径: config.skills.entries.<SKILL_NAME>.env.ALI_1688_AK
    
    Args:
        ak: 1688 AK
    
    Returns:
        是否成功
    """
    try:
        config = {}
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        config = json.loads(content)
            except json.JSONDecodeError as e:
                print(f"⚠️  配置文件解析失败，将创建新配置: {e}")
                config = {}
        
        # 按 OpenClaw 规范写入 skills.entries.<name>.env
        config.setdefault("skills", {})
        config["skills"].setdefault("entries", {})
        config["skills"]["entries"].setdefault(SKILL_NAME, {})
        config["skills"]["entries"][SKILL_NAME].setdefault("env", {})
        
        old_ak = config["skills"]["entries"][SKILL_NAME]["env"].get("ALI_1688_AK", "")
        config["skills"]["entries"][SKILL_NAME]["env"]["ALI_1688_AK"] = ak
        
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        if old_ak:
            masked_old = f"{old_ak[:4]}****{old_ak[-4:]}"
            print(f"📝 更新 AK: {masked_old} → {ak[:4]}****{ak[-4:]}")
        else:
            print(f"📝 新增 AK: {ak[:4]}****{ak[-4:]}")
        
        return True
        
    except PermissionError:
        print(f"❌ 权限错误: 无法写入 {CONFIG_PATH}")
        print("   请检查文件权限")
        return False
    except Exception as e:
        print(f"❌ 配置失败: {e}")
        return False


def check_existing_config() -> tuple[bool, str]:
    """
    检查是否已有 AK 配置
    
    Returns:
        (是否已配置, AK 或空字符串)
    """
    if not CONFIG_PATH.exists():
        return False, ""
    
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
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


def main():
    # 检查现有配置
    has_existing, existing_ak = check_existing_config()
    
    if len(sys.argv) < 2:
        print("AK 配置助手")
        print("=" * 50)
        
        if has_existing:
            masked = f"{existing_ak[:4]}****{existing_ak[-4:]}"
            print(f"✅ 当前已配置 AK: {masked}")
            print(f"📁 配置文件: {CONFIG_PATH}")
        else:
            print("❌ 尚未配置 AK")
        
        print("\n使用方法:")
        print("  python configure.py YOUR_AK_HERE")
        print("\n示例:")
        print("  python configure.py YOUR_AK_HERE")
        
        if has_existing:
            print("\n⚠️  如需更换 AK，直接运行上述命令即可")
        
        sys.exit(0)
    
    ak = sys.argv[1].strip()
    
    # 验证 AK
    is_valid, error_msg = validate_ak(ak)
    if not is_valid:
        print(f"❌ {error_msg}")
        sys.exit(1)
    
    # 配置 AK
    if configure_ak(ak):
        print(f"✅ AK 已保存到: {CONFIG_PATH}")
        print("\n⚠️  重要: 请重启 Gateway 使配置生效!")
        print("\n重启方法:")
        print("  方法1: pkill openclaw-gateway && openclaw gateway")
        print("  方法2: openclaw gateway restart")
        print("\n重启后，所有会话均可使用此 AK")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()