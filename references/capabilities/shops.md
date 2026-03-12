# 店铺查询指南

## CLI 调用

```bash
python3 {baseDir}/cli.py shops
```

无参数，返回当前 AK 绑定的所有下游店铺。

## 输出结构

```json
{
  "success": true,
  "markdown": "你共绑定了 **2** 个店铺：\n\n| # | 店铺 | 平台 | 状态 | 店铺代码 |\n...",
  "data": {
    "total": 2,
    "valid_count": 1,
    "expired_count": 1,
    "shops": [
      {"code": "260391138", "name": "我的抖店", "channel": "douyin", "is_authorized": true},
      {"code": "123456789", "name": "拼多多小店", "channel": "pinduoduo", "is_authorized": false}
    ]
  }
}
```

| data 字段 | 含义 |
|-----------|------|
| `total` | 店铺总数 |
| `valid_count` | 授权有效的店铺数 |
| `expired_count` | 授权过期的店铺数 |
| `shops[].code` | 店铺代码（铺货时用作 `--shop-code`） |
| `shops[].name` | 店铺名称 |
| `shops[].channel` | 所属平台（douyin / pinduoduo / xiaohongshu / taobao） |
| `shops[].is_authorized` | 授权是否有效 |

## Agent 展示规则

| 场景 | Agent 操作 |
|------|-----------|
| 有有效店铺 | 原样输出 `markdown`（含店铺表格） |
| 0 个店铺 | 输出开店引导话术（见 SKILL.md） |
| 全部 `is_authorized: false` | 提示"店铺授权已过期，请在 [1688 AI版APP](https://air.1688.com/kapp/1688-ai-app/pages/home?from=1688-shopkeeper) 中重新授权" |

## 异常处理

通用 HTTP 异常（400/401/429/500）处理见 `references/common/error-handling.md`。
