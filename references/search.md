# 选品详细说明

## CLI 调用

```bash
python3 {baseDir}/cli.py search --query "商品描述" [--channel 渠道]
```

| 参数 | 默认 | 可选值 |
|------|------|--------|
| `--query` | 必填 | 自然语言描述，API 自行理解语义 |
| `--channel` | douyin | douyin / pinduoduo / xiaohongshu / taobao |

## 输出字段

```json
{
  "data_id": "20260305_143022",
  "product_count": 18,
  "products": [{"id": "...", "title": "...", "price": "...", "stats": {...}}],
  "markdown": "找到 18 个商品：..."
}
```

`data_id` 用于后续铺货：`cli.py publish --data-id 20260305_143022`

## stats 字段说明

| 字段 | 含义 | 选品价值 |
|------|------|---------|
| `totalSales` | 累计销量 | 商品热度 |
| `last30DaysSales` | 近30天销量 | 近期趋势 |
| `last30DaysDropShippingSales` | 近30天下单量 | 代发活跃度 |
| `repurchaseRate` | 复购率 | 产品质量 |
| `goodRates` | 好评率 | 售后风险 |
| `remarkCnt` | 评价数量 | 样本量 |
| `collectionRate24h` | 24h揽收率 | 发货速度 |
| `downstreamOffer` | 下游铺货数 | 竞争激烈度 |
| `totalOrder` | 累计下单笔数 | 历史规模 |
| `categoryName` / `categoryListName` | 类目 | 类目归属 |
| `earliestListingTime` | 最早上架时间 | 新品/老品 |
| `saleRangeList` | 面价范围趋势 | `[{date, minPrice, maxPrice}]` |
| `saleQuantityList` | 销量趋势 | `[{date, saleQuantity}]` |
| `tradePriceList` | 量价关系 | `[{date, tradeCount, minPrice, ...}]` |

## 选品分析模板（Agent 展示规范）

```
第一部分（必须）：原样输出 markdown 字段
─────────────────────────────────────
第二部分（必须）：Agent 选品分析

📊 选品分析

🌟 推荐铺货（N个）：
1. [商品标题] — ¥[价格]
   30天销量 X | 好评率 X% | 复购率 X% | 铺货数 X
   → [一句话推荐理由，必须引用具体数据]

⚠️ 风险提示：
- [商品标题]：[具体风险，引用 stats 数据]

─────────────────────────────────────
第三部分（必须）：引导下一步
```

## 选品策略

**好卖特征**
- `last30DaysSales` 高且 `saleQuantityList` 趋势向上
- `collectionRate24h` 高（发货快）
- `goodRates` + `repurchaseRate` 双高
- `downstreamOffer` 低（蓝海）

**避坑**
- ❌ `saleQuantityList` 持续下降（退潮）
- ❌ `goodRates` 低或 `remarkCnt` 极少（售后风险）
- ❌ 侵权/品牌仿品
- ❌ 过重/过大（运费成本高）
