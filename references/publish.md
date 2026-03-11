# 铺货详细说明

## CLI 调用

```bash
# 方式一：用选品 data_id（推荐）
python3 {baseDir}/cli.py publish --shop-code "260391138" --data-id "20260305_143022"

# 方式二：直接指定商品 ID
python3 {baseDir}/cli.py publish --shop-code "260391138" --item-ids "123456,789012"
```

| 参数 | 说明 |
|------|------|
| `--shop-code` | 必填，目标店铺代码（从 `cli.py shops` 获取） |
| `--data-id` | 本地选品快照 ID（与 `--item-ids` 二选一，非平台全局ID） |
| `--item-ids` | 逗号分隔的商品 ID 列表（最多 20 个）|
| `--dry-run` | 可选，仅预检查不执行实际铺货 |

## 输出字段

上游 API 响应（最新）：

```json
{
  "success": true,
  "model": {
    "data": {
      "failCount": 0,
      "successCount": 1,
      "allCount": 1
    }
  }
}
```

失败响应统一看顶层 `success=false`，并读取 `msgCode/msgInfo`（`401/429/400/500`）。

CLI 标准输出（本 skill 对外）：

```json
{
  "success": true,
  "markdown": "## 铺货结果\n\n✅ **成功铺货 12 个商品**...",
  "data": {
    "success": true,
    "origin_count": 28,
    "submitted_count": 20,
    "success_count": 12,
    "fail_count": 8,
    "dry_run": false
  }
}
```

## data_id / item-ids 决策规则

- `data_id` = 历史选品结果的本地快照ID
- `item-ids` = 实际铺货要提交的商品ID列表
- Agent 可以：
  - 用 `data_id` 读取本地快照，再提取 `item-ids`
  - 直接按用户指定ID构造 `item-ids`
- 两者都没有：先执行 `search`
- 两者都传：CLI 拒绝执行（参数互斥）

## 铺货流程规范（Agent 执行）

```
1. 确认商品来源（data_id 或 item-ids）
2. 运行 cli.py shops 获取 shop_code
   └─ 单店铺 → 自动选
   └─ 多店铺 → 列出让用户选择
   └─ 授权过期 → 提示在 1688 AI版 APP 重新授权
3. 铺货前向用户确认：
   "确认铺货信息：
   - 商品：X个
   - 目标店铺：[平台]店铺名
   确认执行吗？"
4. 若用户希望先看影响范围：先执行 `--dry-run` 预检查
5. 执行正式铺货
6. 展示结果：原样输出 markdown，根据 success 引导下一步
```

## 限制

- 单次最多 20 个商品
- 超出 20 个时仅提交前 20 个，并在结果中明确提示
- 店铺必须授权有效
- API 调用频率受 1688 平台限制
