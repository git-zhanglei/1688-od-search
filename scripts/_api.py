#!/usr/bin/env python3
"""
1688 API 封装模块（内部模块）

提供三个原子能力：
1. search_products  - 商品搜索
2. list_bound_shops - 查询绑定店铺
3. publish_items    - 铺货

认证：自动从 ALI_1688_AK 环境变量获取并签名
渠道：统一使用 _const.CHANNEL_MAP，不在本模块重复定义
"""

import json
import os
import time
import logging
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from functools import wraps

import requests
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _auth import get_auth_headers
from _const import CHANNEL_MAP, SEARCH_LIMIT, PUBLISH_LIMIT

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('1688_api')

BASE_URL = "https://ainextpre.1688.com"
MAX_RETRIES = 3
RETRY_DELAY_BASE = 1


@dataclass
class Product:
    """商品信息"""
    id: str
    title: str
    price: str
    image: str
    url: str
    stats: Optional[Dict[str, Any]] = None


@dataclass
class Shop:
    """店铺信息"""
    code: str
    name: str
    channel: str
    is_authorized: bool


@dataclass
class PublishResult:
    """铺货结果"""
    success: bool
    published_count: int
    failed_items: List[Dict[str, Any]]
    submitted_count: int = 0
    fail_count: int = 0
    all_count: int = 0


def with_retry(max_retries: int = MAX_RETRIES):
    """重试装饰器 - 仅重试 ConnectionError / Timeout，耗尽后向上抛出"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    last_exception = e
                    delay = min(RETRY_DELAY_BASE * (2 ** attempt), 10)
                    logger.warning(f"网络异常(尝试{attempt+1}/{max_retries}): {e}, {delay}s后重试")
                    if attempt < max_retries - 1:
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


def _http_error_message(e: requests.exceptions.HTTPError) -> str:
    """将常见 HTTP 错误码映射为可读错误信息"""
    status = e.response.status_code if e.response is not None else None
    if status == 401:
        return "签名无效或已过期（401 Unauthorized: Invalid or expired token）"
    if status == 429:
        return "请求被限流（429 rateLimit），请稍后重试"
    if status == 400:
        return "请求参数不合法（400 Bad Request: parameters invalid）"
    return f"HTTP错误 {status}" if status else "HTTP错误"


def _biz_error_message(result: Dict[str, Any]) -> str:
    """提取业务失败信息（即使 HTTP 200 也可能失败）"""
    msg_code = str(result.get("msgCode") or "")
    msg_info = result.get("msgInfo")
    code_match = re.search(r"\b(400|401|429|500)\b", msg_code)
    normalized_code = code_match.group(1) if code_match else ""

    if normalized_code == "401":
        return "签名无效（401 Unauthorized: Invalid or expired token）"
    if normalized_code == "429":
        return "请求被限流（429 Too Many Requests: rateLimit）"
    if normalized_code == "400":
        return "请求参数不合法（400 Bad Request: parameters invalid）"
    if normalized_code == "500":
        return "服务异常（500），请稍后重试"

    if msg_code and msg_info:
        return f"{msg_code}: {msg_info}"
    if msg_info:
        return str(msg_info)
    if msg_code:
        return str(msg_code)
    return "未知业务错误"


@with_retry()
def search_products(query: str, channel: str = "") -> List[Product]:
    """
    搜索商品

    Args:
        query:   搜索关键词（自然语言描述，API 自行理解语义）
        channel: 下游渠道，支持英文名或中文别名（见 _const.CHANNEL_MAP）

    Returns:
        Product 对象列表（含 stats 分析数据）
    """
    api_channel = CHANNEL_MAP.get(channel, channel)

    url = f"{BASE_URL}/1688claw/skill/searchoffer"
    body = json.dumps({"query": query, "channel": api_channel})

    headers = get_auth_headers("POST", "/1688claw/skill/searchoffer", body)
    if not headers:
        logger.error("AK未配置 - 请运行: python3 cli.py configure YOUR_AK")
        return []

    try:
        response = requests.post(url, headers=headers, data=body, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get("success") is False:
            logger.error(f"搜索失败 - 业务错误: {_biz_error_message(result)}")
            return []

        model = result.get("model", {})
        if not isinstance(model, dict):
            logger.error("搜索失败 - model 结构异常（期望 dict）")
            return []

        data = model.get("data", {})
        if not isinstance(data, dict):
            logger.error("搜索失败 - model.data 结构异常（期望 dict）")
            return []
        products = []
        for i, (item_id, item) in enumerate(data.items()):
            if i >= SEARCH_LIMIT:
                break
            products.append(Product(
                id=item_id,
                title=item.get("title") or "未知商品",
                price=str(item.get("price") or "-"),
                image=item.get("image") or "",
                url=f"https://detail.1688.com/offer/{item_id}.html",
                stats=item.get("stats"),
            ))

        logger.info(f"搜索成功: {query}, 返回 {len(products)} 个商品")
        return products

    except requests.exceptions.HTTPError as e:
        logger.error(f"搜索失败 - {_http_error_message(e)}")
        return []
    except (KeyError, TypeError) as e:
        logger.error(f"搜索失败 - 数据解析错误: {e}")
        return []


@with_retry()
def list_bound_shops() -> List[Shop]:
    """查询已绑定的店铺列表"""
    url = f"{BASE_URL}/1688claw/skill/searchshop"
    body = "{}"

    headers = get_auth_headers("POST", "/1688claw/skill/searchshop", body)
    if not headers:
        logger.error("AK未配置")
        return []

    try:
        response = requests.post(url, headers=headers, data=body, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get("success") is False:
            logger.error(f"查询店铺失败 - 业务错误: {_biz_error_message(result)}")
            return []

        model = result.get("model", {})
        if not isinstance(model, dict):
            logger.error("查询店铺失败 - model 结构异常（期望 dict）")
            return []

        shops_data = model.get("data", [])
        if not isinstance(shops_data, list):
            logger.error("查询店铺失败 - model.data 结构异常（期望 list）")
            return []

        shops = []
        for s in shops_data:
            tool_expired = s.get("toolExpired", False)
            shop_expired = s.get("shopExpired", False)
            shops.append(Shop(
                code=s.get("shopCode", ""),
                name=s.get("shopName", "未知店铺"),
                channel=s.get("channel") or "",
                is_authorized=not (tool_expired or shop_expired)
            ))

        logger.info(f"查询店铺成功: {len(shops)} 个")
        return shops

    except requests.exceptions.HTTPError as e:
        logger.error(f"查询店铺失败 - {_http_error_message(e)}")
        return []
    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"查询店铺失败 - 数据解析错误: {e}")
        return []


@with_retry()
def publish_items(item_ids: List[str], shop_code: str, channel: Optional[str] = None) -> PublishResult:
    """
    铺货到指定店铺

    Args:
        item_ids:  商品ID列表（最多20个）
        shop_code: 店铺代码
        channel:   下游渠道 API 值（如已知可直接传入，避免重复查询店铺）

    Returns:
        PublishResult 对象
    """
    url = f"{BASE_URL}/1688claw/skill/distributingoffer"

    if not channel:
        shops = list_bound_shops()
        target_shop = next((s for s in shops if s.code == shop_code), None)
        if not target_shop:
            return PublishResult(
                success=False,
                published_count=0,
                failed_items=[{"error": "店铺不存在"}],
                submitted_count=0,
                fail_count=0,
                all_count=0,
            )
        channel = CHANNEL_MAP.get(target_shop.channel, "douyin")

    submitted_count = len(item_ids[:PUBLISH_LIMIT])
    body = json.dumps({
        "offerIdList": ",".join(item_ids[:PUBLISH_LIMIT]),
        "channel": channel,
        "shopCode": shop_code
    })

    headers = get_auth_headers("POST", "/1688claw/skill/distributingoffer", body)
    if not headers:
        return PublishResult(
            success=False,
            published_count=0,
            failed_items=[{"error": "AK未配置"}],
            submitted_count=submitted_count,
            fail_count=submitted_count,
            all_count=submitted_count,
        )

    try:
        response = requests.post(url, headers=headers, data=body, timeout=60)
        response.raise_for_status()
        result = response.json()
        if result.get("success") is False:
            biz_msg = _biz_error_message(result)
            logger.error(f"铺货失败 - 业务错误: {biz_msg}")
            return PublishResult(
                success=False,
                published_count=0,
                failed_items=[{"error": biz_msg}],
                submitted_count=submitted_count,
                fail_count=submitted_count,
                all_count=submitted_count,
            )

        model = result.get("model", {})
        if not isinstance(model, dict):
            logger.error("铺货失败 - model 结构异常（期望 dict）")
            return PublishResult(
                success=False,
                published_count=0,
                failed_items=[{"error": "返回结构异常：model不是对象"}],
                submitted_count=submitted_count,
                fail_count=submitted_count,
                all_count=submitted_count,
            )
        success = True
        model_data = model.get("data", {})
        parsed_data = model_data if isinstance(model_data, dict) else {}

        success_count = parsed_data.get("successCount")
        fail_count = parsed_data.get("failCount")
        all_count = parsed_data.get("allCount")
        published_count = int(success_count) if success_count is not None else submitted_count

        return PublishResult(
            success=success,
            published_count=published_count,
            failed_items=[],
            submitted_count=submitted_count,
            fail_count=int(fail_count) if fail_count is not None else max(submitted_count - published_count, 0),
            all_count=int(all_count) if all_count is not None else submitted_count,
        )

    except requests.exceptions.HTTPError as e:
        mapped = _http_error_message(e)
        logger.error(f"铺货失败 - {mapped}")
        return PublishResult(
            success=False,
            published_count=0,
            failed_items=[{"error": mapped}],
            submitted_count=submitted_count,
            fail_count=submitted_count,
            all_count=submitted_count,
        )
    except (KeyError, TypeError, ValueError) as e:
        logger.error(f"铺货失败 - 数据解析错误: {e}")
        return PublishResult(
            success=False,
            published_count=0,
            failed_items=[{"error": str(e)}],
            submitted_count=submitted_count,
            fail_count=submitted_count,
            all_count=submitted_count,
        )
