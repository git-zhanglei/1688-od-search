# 🛒 1688-shopkeeper

1688 AI店长 —— 帮你从 1688 找到好货，一键铺到抖店、拼多多、小红书、淘宝等下游店铺。

## 能做什么

- **选品找货**：告诉 AI 你想卖什么，自动从 1688 搜索并推荐优质货源
- **商品详情**：按商品 ID 查看标题、价格、类目、SKU、属性与商家信息
- **一键铺货**：选好商品后直接铺到你的店铺，支持抖店、拼多多、小红书、淘宝
- **店铺管理**：查看已绑定的店铺状态和授权情况
- **商机与趋势**：即时商机热榜；按关键词看类目/行业趋势与价格分布
- **经营日报**：生成店铺经营日报与主营商品选品建议
- **经营问答**：定价策略、运费模板、选品避坑、新店起步等常见问题都能问

## 安装

在 Claw 对话框里直接输入下面这段话，让 OpenClaw 帮你自动安装：

```text
请帮我安装这个 skill：https://github.com/next-1688/1688-shopkeeper.git
```

## 使用前准备

1. 下载 [**1688 AI版 APP**](https://air.1688.com/kapp/1688-ai-app/pages/home?from=1688-shopkeeper)
2. 打开 APP 首页，点击「一键部署开店Claw，全自动化赚钱🦞」
3. 进入页面复制你的 AK（Access Key）
4. 对 AI 说："我的AK是 xxx"

配置完成后就可以开始选品铺货了。

## 快速上手

直接用自然语言和 AI 对话即可：

- "帮我找一些夏季连衣裙，适合抖店卖的"
- "把刚才搜到的商品铺到我的店铺"
- "查一下我绑定了哪些店铺"
- "新手开店应该怎么选品"
- "最近有什么热门商机"
- "大码女装在 1688 上的趋势怎么样"
- "给我一份今天的店铺经营日报"

## 命令行（CLI）

本仓库提供统一入口 `cli.py`，需本机已安装 **Python 3**。环境变量 `ALI_1688_AK` 或由命令 `configure` 写入的配置需与 1688 AI 版 APP 中 AK 一致。

```bash
python3 cli.py <command> [options]
```

| 命令 | 说明 | 示例 |
|------|------|------|
| `search` | 搜商品 | `python3 cli.py search --query "夏季连衣裙" --channel douyin` |
| `prod_detail` | 商品详情 | `python3 cli.py prod_detail --item-ids "991122553819,894138137003"` |
| `shops` | 查绑定店铺 | `python3 cli.py shops` |
| `publish` | 铺货 | `python3 cli.py publish --shop-code CODE --data-id ID` |
| `opportunities` | 商机热榜 | `python3 cli.py opportunities` |
| `trend` | 趋势洞察 | `python3 cli.py trend --query "大码女装"` |
| `shop_daily` | 店铺经营日报 | `python3 cli.py shop_daily` |
| `configure` | 配置 AK | `python3 cli.py configure YOUR_AK` |
| `check` | 检查配置 | `python3 cli.py check` |

所有命令 stdout 为 JSON：`{"success": bool, "markdown": str, "data": {...}}`。人类可读说明一般在 `markdown` 字段。**Agent / Skill 编排约定**见根目录 [`SKILL.md`](./SKILL.md)（含安全规则、异常处理与各能力参考文档路径）。

## 支持平台

| 平台 | 选品 | 铺货 |
|------|------|------|
| 抖店 | ✅ | ✅ |
| 拼多多 | ✅ | ✅ |
| 小红书 | ✅ | ✅ |
| 淘宝 | ✅ | ✅ |

## 常见问题

**Q: AK 是什么？怎么获取？**
AK 是你访问 1688 平台的身份凭证。在 1688 AI版 APP 中获取，具体步骤见上方「使用前准备」。

**Q: 收费吗？**
选品和铺货功能限时免费，具体费用以 1688 平台规则为准。

**Q: 支持哪些店铺类型？**
支持通过 1688 AI版 APP 绑定的抖店、拼多多、小红书、淘宝店铺。

## 反馈与支持

使用中遇到问题，可以在 1688 AI版 APP 中联系客服。
