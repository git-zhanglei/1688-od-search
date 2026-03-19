# 铺货指南

## 前置

铺货前必须先通过 `shops` 命令获取目标店铺的 `shop_code`（详见 `references/capabilities/shops.md`）。

铺货是**写入级操作**。遵循 `SKILL.md` 的全局写入规则：先 dry-run；仅目标不唯一时追问；目标唯一则直接执行。

## CLI 调用

```bash
# 方式一：用选品 data_id 铺全部（整批）
python3 {baseDir}/cli.py publish --shop-code "260391138" --data-id "20260305_143022_123"

# 方式二：指定商品 ID（用户筛选后）
python3 {baseDir}/cli.py publish --shop-code "260391138" --item-ids "991122553819,894138137003"

# 加 --dry-run 仅预检查不执行
python3 {baseDir}/cli.py publish --shop-code "260391138" --data-id "20260305_143022_123" --dry-run
```

| 参数 | 说明 |
|------|------|
| `--shop-code` | 必填，目标店铺代码（从 `cli.py shops` 的 `data.shops[].code` 获取） |
| `--data-id` | 选品快照 ID（与 `--item-ids` 二选一），铺该批次全部商品 |
| `--item-ids` | 逗号分隔的商品 ID（与 `--data-id` 二选一，最多 20 个） |
| `--dry-run` | 预检查模式，不执行实际铺货。**首次铺货必须先 dry-run** |

### data-id 与 item-ids 怎么选

| 用户意图 | Agent 操作 |
|---------|-----------|
| "全部铺货" | 用 `--data-id`（明确意图，铺该批搜索结果；单次最多提交前 20 个商品） |
| "铺第 1、3 个" / "铺 xxx 这个" / "铺你推荐的几个"  | 从 search 输出的 `data.products[]` 中按序号或ID提取或按agent推荐的提取部分商品ID，用 `--item-ids` |
| 直接给了商品 ID | 用 `--item-ids` |
| 没有商品来源 | 先执行 `search` |
| 两者都传 | CLI 拒绝执行（参数互斥） |

## 输出结构

### 正常铺货输出

```json
{
  "success": true,
  "markdown": "## 铺货结果\n\n**目标店铺**: 我的抖店\n\n✅ 共 20 个商品，已全部提交成功！\n...",
  "data": {
    "success": true,
    "origin_count": 28,
    "submitted_count": 20,
    "error_code": "",
    "dry_run": false,
    "risk_level": "write"
  }
}
```

| data 字段 | 含义 |
|-----------|------|
| `origin_count` | 来源商品总数（data_id 或 item-ids 解析后） |
| `submitted_count` | 实际提交数（最多 20，受接口限制） |
| `error_code` | 铺货错误码（空字符串表示全部成功，见下方错误码表） |
| `dry_run` | 是否为预检查模式 |
| `risk_level` | 固定为 `"write"`，标识这是写入级操作 |
| `confirm_prompt` | dry-run 模式下可出现；仅在目标不唯一时用于追问用户做歧义消解 |

### dry-run 预检查输出

```json
{
  "success": true,
  "markdown": "## 铺货预检查结果\n\n✅ 店铺校验通过：我的抖店\n- 来源商品数：28\n- 实际将提交：20\n- ⚠️ 超出接口限制，仅会提交前 20 个\n\n确认后去掉 `--dry-run` 执行正式铺货。",
  "data": {
    "success": true,
    "origin_count": 28,
    "submitted_count": 20,
    "error_code": "",
    "dry_run": true,
    "risk_level": "write",
    "confirm_prompt": "确认铺货 20 个商品到目标店铺？去掉 --dry-run 执行正式铺货。"
  }
}
```

**Agent 关键行为**：当 `data.risk_level` 为 `"write"` 时，先 dry-run；若目标不唯一且存在 `confirm_prompt`，展示该提示做歧义消解；目标唯一则直接执行正式铺货。

## 铺货流程（Agent 执行步骤）

```
1. 确认商品来源
   └─ 有 data_id → 用 --data-id
   └─ 用户指定了具体商品 → 提取 ID，用 --item-ids
   └─ 都没有 → 先执行 search

2. 获取店铺
   └─ 运行 cli.py shops
   └─ 若用户已在上下文中明确了目标（如"铺到拼多多"），从结果中匹配
   └─ 若用户未指定，列出所有有效店铺让用户选择
   └─ 仅当目标不唯一（多个候选）时追问一次

3. 执行 dry-run 预检查（必须）
   └─ 若商品通过 data_id 指定：运行 cli.py publish --shop-code CODE --data-id ID --dry-run
   └─ 若商品通过 item_ids 指定：运行 cli.py publish --shop-code CODE --item-ids "a,b" --dry-run
   └─ 展示预检结果；仅在目标不唯一时展示 confirm_prompt

4. 目标判定
   └─ 目标唯一 → 去掉 --dry-run 直接执行正式铺货
   └─ 目标不唯一 → 追问一次，用户选定后执行

5. 执行正式铺货
   └─ 若商品通过 data_id 指定：运行 cli.py publish --shop-code CODE --data-id ID
   └─ 若商品通过 item_ids 指定：运行 cli.py publish --shop-code CODE --item-ids "a,b"

6. 展示结果：原样输出 markdown，然后根据结果引导下一步（见下方）
```

**禁止**：跳过 dry-run 直接执行正式铺货。

## 结果处理与下一步引导

| 结果（error_code） | Agent 应对 |
|------|-----------|
| 全部成功（`""`） | 恭喜用户，提示"登录对应平台后台查看已发布商品" |
| 部分成功（`"210"`） | 告知有部分提交失败，建议稍后重试或检查商品信息 |
| 授权失效（`"511"`） | 提示重新授权 |
| 铺货设置未完成（`"512"`） | 提示完成铺货设置 |
| 三方工具错误（`"500"`） | 提示稍后重试 |
| 全部失败（其他） | 展示失败原因（markdown 中有），按错误码引导（见下方错误处理） |
| dry-run 预检查 | 展示预检结果；目标唯一则直接正式执行，目标不唯一则追问一次后执行 |
| 店铺不存在 | 提示运行 `shops` 重新获取正确的店铺代码 |
| 店铺授权过期 | 提示在 1688 AI版 APP 中重新授权 |

## 限制

- 单次最多铺 20 个商品
- 超出 20 个时仅提交前 20 个，结果中会明确提示
- 店铺必须授权有效
- API 调用频率受 1688 平台限制

## 异常处理

通用 HTTP 异常（400/401/429/500）处理见 `references/common/error-handling.md`。

本能力特有异常：

| 场景 | 表现 | Agent 应对 |
|------|------|-----------|
| data_id 找不到 | `"未找到 data_id=... 对应的选品结果"` | 提示用户重新搜索获取新的 data_id |
| 商品 ID 为空 | `"没有可用的商品ID"` | 检查 --item-ids 或 --data-id 是否正确 |
| 部分提交成功 | `error_code: "210"` | 告知有部分提交失败，请前往【1688AI版-下游店铺-铺货成功】看明细 |
| 授权失效 | `error_code: "511"` | 提示下游店铺授权信息失效，请重新授权 |
| 铺货设置未完成 | `error_code: "512"` | 提示完成铺货设置 |
| 三方工具服务错误 | `error_code: "500"` | 提示服务异常，稍后重试 |
