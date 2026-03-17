---
name: 1688-shopkeeper
description: |
  1688选品铺货专家。用于：(1) 在1688搜索商品/选品找货源 (2) 查询已绑定的下游店铺
  (3) 将商品铺货到抖音/拼多多/小红书/淘宝等平台 (4) 配置1688 AK密钥
  (5) 生成今日运营复盘小结（搜索/推荐/铺货成功率/失败原因Top3），并附问题诊断与下一步行动建议。
  触发词：帮我找商品、在1688搜、选品、铺货、上架、查店铺、配置AK、1688找货、今日复盘、运营小结、日报。
metadata: {"openclaw": {"emoji": "🛒", "requires": {"env": ["ALI_1688_AK"], "bins": ["python3"]}, "primaryEnv": "ALI_1688_AK"}}
---

# 1688-shopkeeper

统一入口：`python3 {baseDir}/cli.py <command> [options]`

## 命令速查

| 命令 | 说明 | 示例 |
|------|------|------|
| `search` | 搜商品 | `cli.py search --query "连衣裙" --channel douyin` |
| `shops` | 查绑定店铺 | `cli.py shops` |
| `publish` | 铺货 | `cli.py publish --shop-code CODE --data-id ID` |
| `summary` | 今日运营小结 | `cli.py summary` |
| `configure` | 配置 AK | `cli.py configure YOUR_AK` |
| `check` | 检查配置状态 | `cli.py check` |

所有命令输出 JSON：`{"success": bool, "markdown": str, "data": {...}}`
**展示时直接输出 `markdown` 字段，Agent 分析追加在后面，不得混入其中。**

## 标准流程

**选品→铺货**：`check` → `search` → 用户筛选(Agent 推荐 + 用户确认) → `shops` → `publish`
**每日复盘**：完成选品/铺货后执行 `summary` 生成“运营视角小结报表”
**首次使用**：`check` → 按 data 字段分支：
- `ak_configured: false` → 先 `configure`（优先级最高，其他命令都依赖 AK）
- `shops_count: 0` → 引导开店
- `expired_count > 0` → 提示重新授权
- 全部正常 → 进入选品流程

**刚配置 AK**：当前会话命令前加 `ALI_1688_AK=xxx`，重启 Gateway 后全局生效

## 执行前置（必须）

- 执行 `search` 前：先完整阅读 `references/search.md`
- 执行 `shops` / `publish` 前：先完整阅读 `references/publish.md`
- 执行 `configure` 前：先完整阅读 `references/configure.md`

## AK 引导话术

> "需要先配置 AK。打开 [**1688 AI版 APP**](https://air.1688.com/kapp/1688-ai-app/pages/home?from=1688-shopkeeper)（没装的话点链接下载），首页点击「一键部署开店Claw，全自动化赚钱🦞」，进入页面获取 AK，然后告诉我：'我的AK是 xxx'"

## 开店引导话术

> "还没有绑定店铺。打开 [1688 AI版APP](https://air.1688.com/kapp/1688-ai-app/pages/home?from=1688-shopkeeper) → 首页「一键开店」，开好后告诉我。"

## FAQ 经营知识（按需加载）

用户问经营问题时，**先加载对应文件再回答**，不凭经验泛泛而谈。

| 用户话题 | 加载文件 |
|---------|---------|
| 选哪个平台、抖店/拼多多/淘宝 | `references/faq/platform-selection.md` |
| 选品风险、品类、节日选品 | `references/faq/product-selection.md` |
| 运费模板、定价、加价倍率 | `references/faq/listing-template.md` |
| 发货超时、中转费、偏远地区 | `references/faq/fulfillment.md` |
| 退货、仅退款、运费险、售后 | `references/faq/after-sales.md` |
| 新店破零、服务分、推广 | `references/faq/new-store.md` |
| 素材审核、白底图、标题优化 | `references/faq/content-compliance.md` |

