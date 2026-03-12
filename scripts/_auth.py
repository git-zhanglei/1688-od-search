#!/usr/bin/env python3
"""
1688 API 认证模块

"""

import hashlib
import hmac
import base64
import time
import uuid
import os
from typing import Optional, Dict, Tuple
from urllib.parse import urlparse, parse_qs, quote
from _const import SKILL_VERSION


def extract_ak_keys(raw_input: str) -> Tuple[Optional[str], Optional[str]]:
    """
    从原始输入中提取 AccessKeyID 和 AccessKeySecret
    
    Args:
        raw_input: ALI_1688_AK 环境变量的值
    
    Returns:
        (access_key_id, access_key_secret) 或 (None, None) 如果无效
    """
    try:
        decoded = base64.urlsafe_b64decode(raw_input).decode("utf-8")
        if decoded:
            raw_input = decoded
    except Exception:
        # 当前 AK 规范并不保证一定是 base64，可回退到按长度切分
        pass

    if not raw_input or len(raw_input) < 32:
        return None, None
    
    access_key_secret = raw_input[:32]

    access_key_id = raw_input[32:]
    
    return access_key_id, access_key_secret


AK_SESSION_FILE = os.path.join(os.path.expanduser("~"), ".openclaw", ".ak_session")


def save_ak_to_session(ak: str):
    """将 AK 写入 session 文件，供当前会话后续命令自动读取"""
    try:
        os.makedirs(os.path.dirname(AK_SESSION_FILE), exist_ok=True)
        with open(AK_SESSION_FILE, "w") as f:
            f.write(ak)
    except OSError:
        pass


def _read_ak_from_session() -> Optional[str]:
    """从 session 文件读取 AK"""
    try:
        with open(AK_SESSION_FILE, "r") as f:
            ak = f.read().strip()
        return ak if ak else None
    except (OSError, IOError):
        return None


def get_ak_from_env() -> Tuple[Optional[str], Optional[str]]:
    """获取 AK：环境变量优先，其次 session 文件"""
    raw_input = os.environ.get("ALI_1688_AK")
    if not raw_input:
        raw_input = _read_ak_from_session()
    if not raw_input:
        return None, None
    return extract_ak_keys(raw_input)


def get_content_md5(body: str) -> str:
    """计算 body 的 MD5 并 Base64 编码"""
    if not body:
        return ""
    md5_obj = hashlib.md5(body.encode('utf-8'))
    return base64.b64encode(md5_obj.digest()).decode('utf-8')


def get_canonicalized_resource(uri: str) -> str:
    """
    规范化资源路径
    
    例如：/api/v1/user?name=张三&age=20
    转换为：/api/v1/user?age=20&name=%E5%BC%A0%E4%B8%89
    """
    parsed_uri = urlparse(uri)
    path = parsed_uri.path
    query = parsed_uri.query
    
    if not query:
        return path
    
    # 解析参数
    params = parse_qs(query)
    
    # 对 Key 排序
    sorted_keys = sorted(params.keys())
    
    # 重新拼接
    canonical_query = []
    for key in sorted_keys:
        values = sorted(params[key])
        for value in values:
            encoded_key = quote(key, safe='')
            encoded_val = quote(value, safe='')
            canonical_query.append(f"{encoded_key}={encoded_val}")
    
    return f"{path}?{'&'.join(canonical_query)}"


def build_signature(
    method: str,
    uri: str,
    body: str,
    content_type: str,
    ak_id: str,
    ak_secret: str
) -> Dict[str, str]:
    """
    构建带签名的请求头
    
    Args:
        method: HTTP 方法 (GET/POST)
        uri: 请求路径（包含查询参数）
        body: 请求体 JSON 字符串
        content_type: Content-Type
        ak_id: Access Key ID
        ak_secret: Access Key Secret
    
    Returns:
        完整的请求头字典
    """
    # A. 准备基础安全参数
    timestamp = str(int(time.time()))
    nonce = uuid.uuid4().hex[:8]
    content_md5 = get_content_md5(body)
    
    # B. 构造自定义 Header
    csk_headers = {
        "x-csk-ak": ak_id,
        "x-csk-time": timestamp,
        "x-csk-nonce": nonce,
        "x-csk-content-md5": content_md5,
        "x-csk-version": SKILL_VERSION,
    }
    
    # C. 生成 CanonicalizedHeaders
    sorted_csk_keys = sorted(csk_headers.keys())
    canonicalized_headers = ""
    for key in sorted_csk_keys:
        canonicalized_headers += f"{key.lower()}:{csk_headers[key].strip()}\n"
    
    # D. 构造待签名字符串
    string_to_sign = (
        method.upper() + "\n" +
        content_md5 + "\n" +
        content_type + "\n" +
        timestamp + "\n" +
        canonicalized_headers +
        get_canonicalized_resource(uri)
    )
    
    # E. 计算 HMAC-SHA256 签名
    signature = hmac.new(
        ak_secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        hashlib.sha256
    ).digest()
    sign_base64 = base64.b64encode(signature).decode('utf-8')
    
    # F. 返回最终 Headers
    headers = {
        "Content-Type": content_type,
        "x-csk-sign": sign_base64,
        **csk_headers,
    }
    
    return headers


def get_auth_headers(method: str, uri: str, body: str = "") -> Optional[Dict[str, str]]:
    """
    获取认证头（便捷函数）
    
    Args:
        method: HTTP 方法
        uri: 请求 URI（如 /1688claw/skill/searchoffer）
        body: 请求体（JSON字符串）
    
    Returns:
        请求头字典，如果 AK 未配置则返回 None
    """
    ak_id, ak_secret = get_ak_from_env()
    
    if not ak_id or not ak_secret:
        return None
    
    return build_signature(
        method=method,
        uri=uri,
        body=body,
        content_type="application/json",
        ak_id=ak_id,
        ak_secret=ak_secret,
    )


# 测试入口
if __name__ == "__main__":
    # 从环境变量获取 AK 进行测试
    import os
    test_ak = os.environ.get("ALI_1688_AK")
    
    if not test_ak:
        print("❌ 请先设置环境变量 ALI_1688_AK")
        print("示例: export ALI_1688_AK=your_ak_here")
        exit(1)
    
    ak_id, ak_secret = extract_ak_keys(test_ak)
    if not ak_id or not ak_secret:
        print("❌ AK 格式不正确")
        exit(1)
    
    print(f"✅ AK ID: {ak_id}")
    print(f"✅ Secret: {ak_secret[:8]}...")
    
    # 测试签名生成
    headers = build_signature(
        method="POST",
        uri="/1688claw/skill/searchoffer",
        body='{"query":"test","channel":"douyin"}',
        content_type="application/json",
        ak_id=ak_id,
        ak_secret=ak_secret,
    )
    
    print("\n✅ 签名生成成功！")
    print("请求头包含:")
    for k in headers.keys():
        print(f"  - {k}")