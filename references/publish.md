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
| `--data-id` | 选品结果 ID（与 `--item-ids` 二选一） |
| `--item-ids` | 逗号分隔的商品 ID 列表（最多 50 个）|

## 输出字段

```json
{
  "success": true,
  "markdown": "## 铺货结果\n\n✅ **成功铺货 12 个商品**..."
}
```

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
4. 执行铺货
5. 展示结果：原样输出 markdown，根据 success 引导下一步
```

## 限制

- 单次最多 50 个商品
- 店铺必须授权有效
- API 调用频率受 1688 平台限制
