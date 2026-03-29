# 新人开店 SOP（标准流程）

面向首次使用本工具、从零到可铺货的状态。每步完成后进入下一步；细节问答见文末链出的 FAQ。

---

## 阶段一：账号与 AK

1. 安装并打开 [**1688 AI 版 APP**](https://air.1688.com/kapp/1688-ai-app/pages/home?from=1688-shopkeeper)，按首页指引获取 **AK（Access Key）**。
2. 在本机配置 AK：执行 `cli.py configure <你的AK>`，或设置环境变量 `ALI_1688_AK`（与 APP 中一致）。
3. 可选：执行 `cli.py check`，确认 AK 与运行环境正常。

若报错「AK 未配置」「401」等，按 SKILL.md 中的 **AK 引导话术** 处理；技术项见 `references/faq/base.md`。

---

## 阶段二：下游开店与店铺绑定

1. 在目标电商平台（抖店、拼多多、小红书、淘宝等）完成开店/入驻，按各平台要求提交资质。
2. 回到 **1688 AI 版 APP**，完成与下游店铺的绑定（首页「一键开店」等入口，以 APP 当前界面为准）。
3. 执行 `cli.py shops`，确认列表中能看到目标店铺，并记下对应 **`shop_code`**（铺货必填）。

若返回 0 个店铺，按 SKILL.md **开店引导话术** 引导用户完成绑定后再查。

**选平台、各平台优劣**：见 `references/faq/platform-selection.md`。

---

## 阶段三：首单选品与铺货

1. **搜货**：`cli.py search --query "你的选品描述" --channel <目标渠道>`（如 `douyin`）。保存返回中的 **`data_id`** 与意向商品的 **`product_id`**。
2. **确认店铺**：再次 `shops`，确认 `shop_code` 与目标店一致。
3. **铺货（必须先预检）**：对 `publish` **必须先带 `--dry-run`**，预检通过后再正式铺货；仅当商品或店铺存在多个候选时，再请用户明确选择。正式命令示例：`cli.py publish --shop-code <shop_code> --data-id <data_id>`（或按能力文档使用 `--item-ids`）。

铺货安全规则与参数细节见 `references/capabilities/publish.md`；选品思路见 `references/faq/product-selection.md`。

---

## 阶段四：开业后运营（按需）

| 诉求 | 建议命令 / 说明 |
|------|-----------------|
| 看即时商机 | `cli.py opportunities` |
| 看某类目趋势与价格带 | `cli.py trend --query "关键词"` |
| 经营日报与选品建议 | `cli.py shop_daily` |
| 商品详情核对 | `cli.py prod_detail --item-ids "id1,id2"` |

破零、服务分、支付与推广等：**不要在本 SOP 展开**，见 `references/faq/new-store.md`。

---

## 与 FAQ 的分工

| 文档 | 用途 |
|------|------|
| 本文 | **按顺序做什么**（流程 SOP） |
| `new-store.md` | 新店破零、评分、投流、活动等 **问答** |
| `platform-selection.md` | 平台怎么选 |
| `product-selection.md` | 选品风险与品类 |
| `listing-template.md` | 运费模板、定价加价 |
| `base.md` | AK、铺货失败、支持平台等 **技术 FAQ** |
