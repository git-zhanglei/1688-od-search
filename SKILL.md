---
name: 1688-shopkeeper
description: |
  1688选品铺货 + 商机趋势专家。用于：(1) 在1688搜索商品/选品找货源 (2) 查询已绑定的下游店铺
  (3) 将商品铺货到抖音/拼多多/小红书/淘宝等平台 (4) 配置1688 AK密钥 (5) 查看即时商机热榜
  (6) 查看类目/行业趋势与价格分布 (7) 生成店铺经营日报并输出主营商品选品建议。
  触发词：帮我找商品、在1688搜、选品、铺货、上架、查店铺、配置AK、商机、热榜、排行榜、趋势、价格分布、经营日报、店铺日报、动销分析、经营分析、选品建议、1688找货。
metadata: {"openclaw": {"emoji": "🛒", "requires": {"bins": ["python3"]}, "primaryEnv": "ALI_1688_AK"}}
---

# 1688-shopkeeper

统一入口：`python3 {baseDir}/cli.py <command> [options]`

## 命令速查

| 命令 | 说明 | 示例 |
|------|------|------|
| `search` | 找商品 | `cli.py search --query "帮我找1688上支持一件代发包邮的露营椅，100元以内" --channel douyin` |
| `prod_detail` | 商品详情 | `cli.py prod_detail --item-ids "991122553819,894138137003"` |
| `shops` | 查绑定店铺 | `cli.py shops` |
| `publish` | 铺货 | `cli.py publish --shop-code CODE --data-id ID` |
| `opportunities` | 商机热榜 | `cli.py opportunities` |
| `trend` | 趋势洞察 | `cli.py trend --query "大码女装"` |
| `shop_daily` | 店铺经营日报 | `cli.py shop_daily` |
| `configure` | 配置 AK | `cli.py configure YOUR_AK` |
| `check` | 检查配置状态 | `cli.py check` |

所有命令输出 JSON：`{"success": bool, "markdown": str, "data": {...}}`
**展示时直接输出 `markdown` 字段，Agent 分析追加在后面，不得混入其中。**

## 使用流程

Agent 根据用户意图**直接执行对应命令**，无需每次先执行 `check`。
各命令在 AK 缺失、店铺异常等情况下会自行返回明确错误，Agent 按下方「异常处理」应对即可。

**选品铺货典型路径**：`search` → 用户筛选 → `shops`（确认目标店铺） → `publish`

**商品详情使用指引**：
- `prod_detail`：用户想看商品标题、价格、类目、SKU、CPV 属性、商家信息时使用。

**商机/趋势使用指引**：
- `opportunities`：用户想看“此刻/近1小时/热榜/趋势商机”。
- `trend`：用户询问某宽泛类目/行业的周期趋势、价格分布、热品概况；关键词过长或过细时先按用户原词尝试，若空结果再提示用户换更宽泛/拆分词后重试。
- `shop_daily`：用户想看“店铺经营日报/今日动销/渠道经营诊断/主营商品选品建议”。

## 安全声明

| 风险级别 | 命令 | Agent 行为 |
|---------|------|-----------|
| **只读** | search, shops, check, opportunities, trend, shop_daily | 直接执行 |
| **配置** | configure | 提示影响范围后执行 |
| **写入** | publish | **必须先 dry-run 预检查；仅当写入目标不唯一时追问，目标唯一则直接执行** |

**全局写入规则（适用于所有写操作）**：
1. 必须先执行 dry-run。
2. 仅当写入目标不唯一（商品或店铺存在多个候选）时，才向用户追问一次做歧义消解。
3. 目标唯一时，dry-run 成功后直接执行正式写入，不再二次确认。

## 异常处理

任何命令输出 `success: false` 时：

1. **先输出 `markdown` 字段**（已包含用户可读的错误描述）
2. **再根据关键词追加引导**：

| markdown 关键词 | Agent 额外动作 |
|----------------|--------------|
| "AK 未配置" 或 "签名无效"/"401" | 输出下方 **AK 引导话术** |
| "授权过期" | 提示用户在 1688 AI版 APP 中重新授权 |
| "店铺未绑定" 或 shops 返回 0 个店铺 | 输出下方 **开店引导话术** |
| "限流"/"429" | 建议用户等待 1-2 分钟后重试 |
| 其他 | 仅输出 markdown 即可 |

详细错误码说明见 `references/common/error-handling.md`。

## 执行前置（首次命中能力时必须）

- 首次执行 `search` 前：先完整阅读 `references/capabilities/search.md`
- 首次执行 `prod_detail` 前：先完整阅读 `references/capabilities/prod_detail.md`
- 首次执行 `shops` 前：先完整阅读 `references/capabilities/shops.md`
- 首次执行 `publish` 前：先完整阅读 `references/capabilities/publish.md`
- 首次执行 `configure` 前：先完整阅读 `references/capabilities/configure.md`
- 首次执行 `opportunities` 前：先完整阅读 `references/capabilities/opportunities.md`
- 首次执行 `trend` 前：先完整阅读 `references/capabilities/trend.md`
- 首次执行 `shop_daily` 前：先完整阅读 `references/capabilities/shop_daily.md`
- 同一会话内后续重复调用同一能力可复用已加载知识；仅在规则冲突或文档更新时重读。

## AK 引导话术

> "需要先配置 AK。打开 [**1688 AI版 APP**](https://air.1688.com/kapp/1688-ai-app/pages/home?from=1688-shopkeeper)（没装的话点链接下载），首页点击「一键部署开店Claw，全自动化赚钱🦞」，进入页面获取 AK，然后告诉我：'我的AK是 xxx'"

## 开店引导话术

> "还没有绑定店铺。打开 [1688 AI版APP](https://air.1688.com/kapp/1688-ai-app/pages/home?from=1688-shopkeeper) → 首页「一键开店」，开好后告诉我。"

## FAQ 知识库（按需加载）

用户问经营或技术问题时，**先加载对应文件再回答**，不凭经验泛泛而谈。

| 用户话题 | 加载文件 |
|---------|---------|
| AK 问题、铺货失败、支持平台、收费 | `references/faq/base.md` |
| 选哪个平台、抖店/拼多多/淘宝 | `references/faq/platform-selection.md` |
| 选品风险、品类、节日选品 | `references/faq/product-selection.md` |
| 运费模板、定价、加价倍率 | `references/faq/listing-template.md` |
| 发货超时、中转费、偏远地区 | `references/faq/fulfillment.md` |
| 退货、仅退款、运费险、售后 | `references/faq/after-sales.md` |
| 新店破零、服务分、推广 | `references/faq/new-store.md` |
| 素材审核、白底图、标题优化 | `references/faq/content-compliance.md` |
