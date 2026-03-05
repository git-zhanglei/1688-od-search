# 1688 Skills - 选品铺货专家

1688选品与铺货一体化工具。支持自然语言搜索商品、管理AK配置、下游铺货到淘宝/拼多多/小红书/抖店。

## 核心能力

1. **AK配置** - 配置/验证1688 AI版 AK
2. **商品搜索** - 自然语言搜索1688商品
3. **下游铺货** - 一键铺货到多个平台

## 快速开始

### 前置要求

- Python 3.10+
- 1688 AI版 APP 账号
- 已开通的下游店铺（抖音/拼多多/小红书/淘宝）

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置 AK

```bash
# 设置环境变量
export ALI_1688_AK=your_ak_here
```

或使用提供的配置工具：
```bash
python scripts/configure.py your_ak_here
```

详细配置说明见 [docs/AK-CONFIG.md](docs/AK-CONFIG.md)

## 使用方式

本 skill 通过 OpenClaw 主 Agent 调用，Agent 会：

1. **理解你的需求** - "帮我找红色洗脸盆"
2. **检查配置状态** - 确认 AK 和店铺绑定
3. **执行选品** - 搜索并展示商品
4. **协助铺货** - 将选定商品发布到指定店铺

完整的使用指南和最佳实践见 [SKILL.md](SKILL.md)

## 目录结构

```
1688-skills/
├── SKILL.md              # 技能知识手册（核心文档）
├── README.md             # 项目说明（本文档）
├── requirements.txt      # Python 依赖
├── docs/
│   ├── AK-CONFIG.md      # AK 配置说明
│   ├── FAQ.md            # FAQ 索引
│   └── faq/              # 经营 FAQ（按主题拆分，Agent 按需加载）
│       ├── platform-selection.md
│       ├── product-selection.md
│       ├── listing-template.md
│       ├── fulfillment.md
│       ├── after-sales.md
│       ├── new-store.md
│       └── content-compliance.md
└── scripts/              # 核心实现（由 Agent 调用）
    ├── api.py
    ├── auth.py
    ├── configure.py
    ├── search.py
    ├── shops.py
    └── publish.py
```

## 注意事项

- 使用前需先在 1688 AI版 APP 中获取 AK
- 下游店铺需要在 APP 中完成绑定和授权
- 单次选品和铺货均限制最多 50 个商品

## License

MIT