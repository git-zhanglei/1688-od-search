# 选品指南

## CLI 调用

```bash
python3 {baseDir}/cli.py search --query "商品描述" [--channel 渠道]
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--query` | 必填 | 自然语言描述，API 自行理解语义，如 `"帮我找1688上支持一件代发包邮的露营椅，100元以内"` |
| `--channel` | `""` | 下游渠道：douyin / taobao / pinduoduo / xiaohongshu。从用户消息中识别渠道意图即可，**识别不到则传空，不要主动询问** |

最多返回 20 个商品。

## 输出结构

Agent 收到的 CLI 标准输出：

```json
{
  "success": true,
  "markdown": "找到 **18** 个商品：\n\n| # | 商品 | 价格 | 30天销量 | 好评率 | 复购率 | 铺货数 | 揽收率 |\n...",
  "data": {
    "data_id": "20260305_143022_123",
    "product_count": 18,
    "products": [
      {
        "id": "991122553819",
        "title": "夏季碎花连衣裙女收腰显瘦",
        "price": "35.8",
        "url": "https://detail.1688.com/offer/991122553819.html",
        "stats": {
          "totalSales": 89200,
          "last30DaysSales": 12680,
          "last30DaysDropShippingSales": 8900,
          "goodRates": 0.962,
          "repurchaseRate": 0.235,
          "remarkCnt": 3260,
          "collectionRate24h": 0.981,
          "downstreamOffer": 158,
          "totalOrder": 45600,
          "categoryListName": "女装/女士精品",
          "earliestListingTime": "2025-03-15"
        }
      }
    ]
  }
}
```

### markdown 与 data 的分工

- **`markdown`** — 预格式化的展示内容（标题超链接、图片、价格、部分核心指标），Agent **原样输出，不修改**
- **`data.products[].stats`** — 完整选品数据，Agent **用于深度分析**

markdown 已展示：30天销量、好评率、复购率、铺货数、累计销量、揽收率、评价数、类目。
**仅存在于 stats** 的字段：`earliestListingTime`（上架时间）、`last30DaysDropShippingSales`（代发下单量）— Agent 做选品分析时需主动读取。

## stats 字段与选品阈值参考

### 核心决策字段

| 字段 | 含义 | 推荐 | 风险 |
|------|------|------|------|
| `last30DaysSales` | 近30天销量 | ≥ 500 | < 100 |
| `goodRates` | 好评率（0~1 小数） | ≥ 0.90 | < 0.85 |
| `repurchaseRate` | 复购率（0~1 小数） | ≥ 0.10 | — |
| `downstreamOffer` | 下游铺货数 | < 200（蓝海） | > 500（红海） |
| `collectionRate24h` | 24h揽收率（0~1 小数） | ≥ 0.90 | < 0.80 |

### 辅助参考字段

| 字段 | 含义 | 用法 |
|------|------|------|
| `totalSales` | 累计销量 | 历史热度 |
| `remarkCnt` | 评价数量 | < 30 时标注"样本不足，好评率仅供参考" |
| `last30DaysDropShippingSales` | 近30天代发下单量 | 代发活跃度 |
| `totalOrder` | 累计下单笔数 | 历史规模 |
| `categoryName` / `categoryListName` | 类目 | 归属分类 |
| `earliestListingTime` | 最早上架时间 | 判断新品/老品 |

## 选品决策规则

以下为默认决策规则，Agent 应主动执行。用户有明确偏好时以用户意见为准。

**推荐铺货**（满足 3 项及以上）：
1. `last30DaysSales` ≥ 500
2. `goodRates` ≥ 0.90
3. `repurchaseRate` ≥ 0.10
4. `downstreamOffer` < 300
5. `collectionRate24h` ≥ 0.90

**标记风险**（命中任一项须在风险提示中说明）：
- `goodRates` < 0.85 或 `remarkCnt` < 30（售后风险/样本不足）
- `downstreamOffer` > 500（红海竞争激烈）
- 标题含品牌名/疑似仿品（侵权风险）
- 单价极低（< 5 元）且为日用品以外品类（质量隐患）

## 展示规范

Agent 回复必须包含以下三部分内容，格式可灵活组织：

1. **商品列表**（必须）：原样输出 `markdown` 字段
2. **选品分析**（必须）：基于 `data.products[].stats` 数据，包括：
   - 推荐铺货的商品及理由（须引用具体数据）
   - 风险提示（命中风险规则的商品及数据依据）
3. **下一步引导**（必须）：
   - "全部铺货" → Agent 用 `--data-id` 铺整批
   - "铺指定商品" → Agent 提取对应 ID，用 `--item-ids`
   - "换个词重新搜" → 重新执行 search

## 异常处理

通用 HTTP 异常（400/401/429/500）处理见 `references/common/error-handling.md`。

本能力特有异常：

| 场景 | 表现 | Agent 应对 |
|------|------|-----------|
| 搜索无结果 | `product_count: 0` | 建议：调整关键词、去掉渠道限制、换更宽泛的描述 |
| 商品缺少 stats | `stats` 为 null | 分析中注明"缺少数据指标，无法评估风险" |
| `remarkCnt` < 30 | — | 分析中注明"评价样本不足，好评率/复购率仅供参考" |
