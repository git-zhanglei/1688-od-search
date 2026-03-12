# 1688-shopkeeper 协同开发规范

> 目标：4-5 人协同开发，持续扩展能力（商品详情、图搜同款、找商机、店铺运营等），
> 保证 skill 稳定运行、Agent 可渐进学习、开发者少踩坑。

---

## 0. 快速上手（新人必读）

```
1. 阅读 SKILL.md              → 理解 Agent 看到的全貌
2. 阅读本文档 §1-§3            → 理解架构与分层
3. 跑通: python3 cli.py check  → 验证环境（需要 ALI_1688_AK）
4. 选一个能力目录参考           → 如 capabilities/search/
5. 按 §4 模板开发新能力
```

---

## 1. 架构总原则

| 原则 | 含义 |
|------|------|
| **入口精简** | SKILL.md 只做能力路由和全局规则，不承载能力细节 |
| **能力解耦** | 每个能力独立目录，代码/文档/测试互不干扰 |
| **按需加载** | Agent 仅在命中某能力时加载对应文档，控制上下文体积 |
| **统一契约** | 所有命令输出 `{"success": bool, "markdown": str, "data": {...}}` |
| **安全分级** | 写操作必须用户确认，不做静默兜底（详见 §6） |
| **确定性下沉** | 确定性逻辑写在 Python 脚本里，不依赖 Agent 记忆（详见 §5） |

---

## 2. 目录结构与分层职责

### 2.1 目标结构

```
1688-shopkeeper/
  SKILL.md                          # Agent 入口（能力路由 + 全局规则）
  CONTRIBUTING.md                   # 本文档（开发者规范）
  cli.py                            # 统一 CLI 入口（自动发现能力）
  requirements.txt
  scripts/
    _http.py                        # 通用 HTTP 客户端（签名、重试、错误映射）
    _auth.py                        # 认证签名
    _const.py                       # 全局常量
    _errors.py                      # 统一异常类
    _output.py                      # 统一输出辅助（JSON 组装、markdown 工具函数）
    capabilities/
      search/
        cmd.py                      # CLI 入口（参数解析 + 输出组装）
        service.py                  # 业务逻辑（调 _http、规则判断）
      publish/
        cmd.py
        service.py
      shops/
        cmd.py
        service.py
      configure/
        cmd.py
        service.py
      check/
        cmd.py
      detail/                       # 新能力示例
        cmd.py
        service.py
      image_search/                 # 下划线命名，与 Python import 兼容
        cmd.py
        service.py
      opportunity/
        cmd.py
        service.py
  references/
    common/
      error-handling.md             # 通用错误处理（400/401/429/500）
      data-contracts.md             # 跨能力数据流契约
    capabilities/                   # 各能力的 Agent 行为指南
      search.md
      shops.md
      publish.md
      configure.md
      detail.md                     # 新能力文档放这里
      image_search.md
      opportunity.md
    faq/
      ...
  tests/
    conftest.py                     # 公共 fixture（mock HTTP、mock AK）
    test_search.py
    test_publish.py
    ...
```

### 2.2 分层职责

```
┌─────────────────────────────────────────────────────────┐
│ cmd.py（薄层）— "怎么进来和怎么出去"                       │
│  · 解析 CLI 参数（argparse）                              │
│  · 调用 service                                          │
│  · 组装统一输出 {success, markdown, data}                 │
│  · 捕获最外层异常，转为用户可读错误                         │
│  · 声明 COMMAND_NAME / COMMAND_DESC（供 cli.py 自动发现）  │
│  · 【禁止】放业务逻辑                                     │
├─────────────────────────────────────────────────────────┤
│ service.py（厚层）— "中间怎么做事"                         │
│  · 业务主流程（校验、调 API、结果计算、状态流转）             │
│  · 组合多个 _http 调用                                    │
│  · 输出结构化业务结果给 cmd.py                             │
│  · 【禁止】直接 print / 组装最终 JSON                      │
├─────────────────────────────────────────────────────────┤
│ _http.py（平台层）— "怎么和 1688 通信"                     │
│  · HTTP 请求发送、签名注入、重试、超时                      │
│  · HTTP / 业务错误码映射为统一异常                          │
│  · 【禁止】包含任何能力特定的业务逻辑                       │
└─────────────────────────────────────────────────────────┘
```

**关键区别**：当前 `_api.py` 混合了"通用 HTTP 能力"和"各能力的 API 调用"，
随着能力增多，所有人都要改这一个文件。拆分后各能力的 API 调用逻辑内聚到
各自的 `service.py`，只有通用 HTTP 层 (`_http.py`) 是共享的。

### 2.3 从现状迁移

采用**渐进迁移**策略，不做一次性大重构：

| 步骤 | 操作 | 影响范围 |
|------|------|---------|
| 1 | 从 `_api.py` 提取通用能力到 `_http.py`（签名、重试、错误映射） | 仅平台层 |
| 2 | 新能力（detail、image_search 等）直接在 `capabilities/` 下创建 | 无影响 |
| 3 | 现有能力在有功能变更时顺带迁入 `capabilities/`，不主动重构 | 逐个迁移 |
| 4 | `_api.py` 保留为兼容层，旧代码仍可 import，直到全部迁完后删除 | 零中断 |

**禁止**：一个 PR 里同时迁移多个能力。每次只迁一个，确保可独立回滚。

---

## 3. cli.py 自动发现机制

当前 `cli.py` 维护手动命令表，每新增能力都要改——**多人并行开发时必然冲突**。

### 3.1 能力自注册

每个 `cmd.py` 在模块顶层声明两个常量：

```python
# capabilities/detail/cmd.py
COMMAND_NAME = "detail"
COMMAND_DESC = "查商品详情"

def main():
    ...
```

`cli.py` 启动时扫描 `capabilities/*/cmd.py`，自动注册。新增能力 **零修改 cli.py**。

### 3.2 兼容过渡

迁移期间 `cli.py` 同时支持：
- 手动表中的旧命令（`search` → `scripts/search.py`）
- 自动发现的新命令（`detail` → `scripts/capabilities/detail/cmd.py`）

旧命令迁移到 `capabilities/` 后从手动表中删除。

---

## 4. 能力开发规范

### 4.1 新能力交付清单

每个新能力 **必须** 同时交付：

```
☐ capabilities/<name>/cmd.py      — CLI 入口
☐ capabilities/<name>/service.py  — 业务逻辑（简单能力可省略，cmd.py 直接调 _http）
☐ references/capabilities/<name>.md — Agent 行为指南
☐ tests/test_<name>.py            — 至少 1 个主流程测试
☐ SKILL.md 更新                    — 命令速查 +1 行、执行前置 +1 行
```

### 4.2 能力文档模板

文档是 **Agent 的行动指南**，不是技术 API 文档。

**必选段（4 段，所有能力必须）**：

```markdown
# <能力名称>

## 1. 什么时候用
一句话说明触发场景。

## 2. CLI 调用
命令格式、参数表。

## 3. 输出结构
Agent 可见的 JSON 结构（仅写 data 中 Agent 需要决策的字段）。

## 4. Agent 执行步骤
可直接照做的编号步骤，无歧义。
```

**可选段（按需添加）**：

```markdown
## 5. 关键字段解释        — 当 data 字段含义不直观时（如 search 的 stats）
## 6. 结果处理与下一步引导  — 当结果需要 Agent 做分支判断时（如 publish 的部分成功）
## 7. 业务异常处理         — 仅写本能力特有的业务异常（通用 HTTP 异常引用公共文档）
## 8. 限制与边界           — 当有数量限制、频率限制等时
```

**禁止写入能力文档的内容**：
- 通用 HTTP 错误处理（统一见 `references/common/error-handling.md`）
- 上游 API 原始响应结构
- 实现细节（重试策略、签名算法等）

### 4.3 通用错误处理（引用制）

所有能力文档的异常处理段，通用部分统一引用：

```markdown
## 7. 业务异常处理

通用 HTTP 异常（400/401/429/500）处理见 `references/common/error-handling.md`。

本能力特有异常：

| 场景 | 表现 | Agent 应对 |
|------|------|-----------|
| data_id 找不到 | "未找到 data_id=..." | 提示用户重新搜索 |
```

这样新增 10 个能力，通用错误表格只维护 **1 份**，改一处全局生效。

---

## 5. 跨能力数据流契约

能力之间不是孤立的，需要传递数据。**必须在 `references/common/data-contracts.md` 中维护**。

### 5.1 核心数据标识符

| 标识符 | 产出方 | 消费方 | 格式 | 说明 |
|--------|--------|--------|------|------|
| `data_id` | search | publish, detail | `YYYYMMDD_HHMMSS_mmm` | 搜索结果快照 ID（含毫秒） |
| `product_id` | search 的 `data.products[].id` | detail, image_search, publish | 纯数字字符串 | 1688 商品 ID |
| `shop_code` | shops 的 `data.shops[].code` | publish, opportunity | 纯数字字符串 | 下游店铺代码 |

### 5.2 数据存储约定

- 搜索快照文件路径：`{DATA_DIR}/1688_{data_id}.json`
- 文件格式：`{"query": str, "channel": str, "timestamp": str, "data_id": str, "products": {id: {...}}}`
- **新能力如需持久化**，必须在 `data-contracts.md` 中注册路径和格式，禁止私自定义

### 5.3 能力依赖图

维护一张 DAG，Agent 据此判断前置操作：

```
configure ← (所有能力都依赖 AK)
search → publish       (data_id / product_id)
search → detail        (product_id)
search → image_search  (product_id)
shops  → publish       (shop_code)
shops  → opportunity   (shop_code)
```

**新能力如有依赖，必须在此图中声明**，对应的 Agent 文档中写入前置步骤。

---

## 6. 安全分级与确认机制

### 6.1 风险分级表

| 级别 | 定义 | 示例命令 | Agent 行为 |
|------|------|---------|-----------|
| **只读** | 不改变任何状态 | search, detail, shops, check, image_search | 直接执行，无需确认 |
| **配置** | 改变本地配置，可重新配置 | configure | 提示影响范围，执行 |
| **写入** | 改变线上状态，操作可能不可逆 | publish, 下架, 采购, 改价 | **必须用户确认后才执行** |

### 6.2 代码层面强制

写入级命令的 `cmd.py` 必须在输出中声明风险级别：

```python
# 在 publish/cmd.py 中，dry-run 预检结果：
output = {
    "success": True,
    "markdown": "...",
    "data": {
        ...,
        "risk_level": "write",                    # 声明风险级别
        "confirm_prompt": "确认铺货 12 个商品到「我的抖店」？",  # 确认话术
    },
}
```

**SKILL.md 中声明**哪些命令是写入级，Agent 看到 `risk_level: "write"` 时 **禁止自动执行下一步**，必须展示 `confirm_prompt` 等待用户确认。

### 6.3 禁止的兜底模式

以下模式在 code review 中一票否决：

```python
# ❌ 未知渠道兜底到默认值
channel = CHANNEL_MAP.get(user_input, DEFAULT_CHANNEL)

# ✅ 未知渠道直接报错
channel = CHANNEL_MAP.get(user_input)
if not channel:
    raise ValueError(f"不支持的渠道: {user_input}，支持: {list(CHANNEL_MAP.keys())}")
```

```python
# ❌ API 异常静默返回空结果（调用方无法区分"无数据"和"出错了"）
except HTTPError:
    return []

# ✅ API 异常向上传播，由 cmd.py 统一处理
except HTTPError as e:
    raise ServiceError(f"搜索失败: {e}") from e
```

---

## 7. 输出与兼容性规范

### 7.1 统一输出结构

所有命令 **必须** 输出：

```json
{
  "success": true,
  "markdown": "直接展示给用户的内容",
  "data": {
    "给 Agent 做后续决策的结构化字段": "..."
  }
}
```

- `markdown`：Agent **原样输出**，不修改、不混入自己的分析
- `data`：Agent 用于判断下一步动作的结构化数据

### 7.2 字段稳定性

| 操作 | 是否允许 | 要求 |
|------|---------|------|
| 新增字段 | ✅ 允许 | 不破坏已有消费方 |
| 删除字段 | ⚠️ 需审批 | 先标记 deprecated，下个 minor 版本删除 |
| 改名字段 | ❌ 禁止 | 新增 + 旧字段 deprecated |

### 7.3 输出体积控制

脚本输出进入 Agent 上下文，**大体积输出会导致上下文爆炸和幻觉**。

| 规则 | 说明 |
|------|------|
| 列表最多 20 条 | 超出部分截断，markdown 注明总数 |
| 单商品 stats 控制在 15 个字段以内 | 不透传 API 原始响应的所有字段 |
| markdown 不超过 2000 字符 | 超长时用摘要 + "详情见 data" |

---

## 8. SKILL.md 维护规范

### 8.1 SKILL.md 必须包含

- 能力总览（命令 + 一句话说明）
- 统一输出协议
- 主流程与分支（check 分支、AK 引导）
- 执行前置（命令 → 参考文档映射）
- 固定话术（AK 引导、开店引导）
- 安全声明（哪些命令是写入级）
- FAQ 路由表

### 8.2 SKILL.md 禁止包含

- API 原始响应结构
- 参数细节 / 字段表 / 异常明细
- 与 `references/*` 重复的内容
- 能力内部实现细节

### 8.3 每次新增能力对 SKILL.md 的改动

**严格限定**，只允许改以下位置：

```
命令速查表 +1 行
执行前置   +1 行
安全声明   +1 行（如果是写入级命令）
```

**禁止**在 SKILL.md 中复制能力文档的内容。

### 8.4 能力组路由（>8 个能力时启用）

当命令超过 8 个时，命令速查表按组分类，帮助 Agent 缩小搜索范围：

```markdown
## 命令速查

### 选品组
| 命令 | 说明 |
| search | 搜商品 |
| detail | 查商品详情 |
| image_search | 图搜同款 |

### 铺货组
| 命令 | 说明 |
| shops | 查绑定店铺 |
| publish | 铺货到下游 |

### 运营组
| 命令 | 说明 |
| opportunity | 找商机 |

### 系统组
| 命令 | 说明 |
| configure | 配置 AK |
| check | 检查状态 |
```

---

## 9. 错误处理统一规范

### 9.1 统一异常类（`_errors.py`）

```python
class SkillError(Exception):
    """所有 skill 异常的基类"""
    def __init__(self, message: str, code: int = 500, data: dict = None):
        self.message = message
        self.code = code
        self.data = data or {}

class AuthError(SkillError):       # AK 无效 / 签名失败 (401)
    pass

class ParamError(SkillError):      # 参数不合法 (400)
    pass

class RateLimitError(SkillError):  # 限流 (429)
    pass

class ServiceError(SkillError):    # 服务异常 (500) / 网络异常
    pass
```

### 9.2 错误传播路径

```
_http.py   → 抛出具体异常（AuthError / RateLimitError / ServiceError）
service.py → 可捕获并补充业务上下文后重新抛出，或直接透传
cmd.py     → 统一捕获，转为 {success: false, markdown: 用户可读, data: 机器可读}
```

**关键规则**：service 层 **禁止** 吞异常返回空结果。空结果 = 业务上确实没数据，
异常 = 出错了。调用方（cmd.py / Agent）需要区分这两种情况。

### 9.3 通用错误码语义

维护在 `references/common/error-handling.md`（Agent 和开发者共用）：

| 错误码 | 语义 | Agent 应对 |
|--------|------|-----------|
| 400 | 参数不合法 | 提示用户修正输入 |
| 401 | 鉴权无效 | 引导重新配置 AK |
| 429 | 限流 | 建议稍后重试 |
| 500 | 服务异常 | 建议稍后重试 |

---

## 10. 测试规范

### 10.1 基础设施（先建后用）

```
tests/
  conftest.py          # 公共 fixture
  test_search.py
  test_publish.py
  ...
```

`conftest.py` 提供：
- `mock_http`：mock `_http.py` 的 HTTP 请求，不依赖真实 AK
- `mock_ak`：注入测试 AK 到环境变量
- `capture_output`：捕获 cmd.py 的 JSON 输出

### 10.2 测试要求

| 类型 | 要求 | 验证什么 |
|------|------|---------|
| **契约测试** | 每个能力至少 1 个 | 输出结构包含 success / markdown / data |
| **主流程测试** | 每个能力至少 1 个 | 正常入参 → 期望输出 |
| **错误测试** | 写入级能力必须 | 异常时输出 success=false 且不崩溃 |

### 10.3 运行方式

```bash
# 全量
pytest tests/

# 单能力
pytest tests/test_search.py
```

---

## 11. 协同开发守则

### 11.1 分工

| 层 | Owner | 职责边界 |
|----|-------|---------|
| 平台层 | 指定 1 人 | `_http.py` / `_auth.py` / `_const.py` / `_errors.py` / `_output.py` / `cli.py` |
| 能力层 | 按能力目录分配 | 各自的 `capabilities/<name>/` + `references/capabilities/<name>.md` + `tests/test_<name>.py` |
| 公共文档 | 平台层 owner | `references/common/*`、SKILL.md |

**原则**：能力 owner 改自己目录内的文件不需要 review 平台层，
改平台层文件（`_http.py`、`_const.py` 等）必须平台层 owner review。

### 11.2 PR 准入清单

```
☐ 代码、文档、测试三件套齐全
☐ 输出契约未破坏（success / markdown / data 结构不变）
☐ 新能力在 SKILL.md 中注册（命令速查 + 执行前置）
☐ 写入级能力实现了确认机制（risk_level + confirm_prompt）
☐ 无静默兜底逻辑（未知输入 → 报错，不是默认值）
☐ 能力文档遵循模板（必选 4 段齐全）
☐ 跨能力数据依赖已在 data-contracts.md 注册
```

### 11.3 提交信息

```
feat(<capability>): 新增商品详情查询能力
fix(<capability>): 修复铺货时未校验店铺授权状态
refactor(platform): 从 _api.py 提取通用 HTTP 层到 _http.py
docs(<capability>): 补充图搜能力的 Agent 执行步骤
test(<capability>): 新增铺货主流程测试
```

### 11.4 分支策略

```
main ← feat/detail       （新能力）
main ← feat/image-search （新能力，可与上面并行）
main ← refactor/http     （平台层重构，需要所有人知晓）
```

多个新能力可 **并行开发**，因为各自在不同的 `capabilities/` 目录下，
只要不同时改平台层文件，就不会冲突。

---

## 12. 版本与发布

采用轻量版本管理，`_const.py` 中维护 `SKILL_VERSION`：

| 变更类型 | 版本动作 | 示例 |
|---------|---------|------|
| 新增能力 / 新增非破坏字段 | minor +1 | 1.0.0 → 1.1.0 |
| 修复 bug / 文档优化 | patch +1 | 1.1.0 → 1.1.1 |
| 删除字段 / 改变核心流程 | major +1（需全员评审） | 1.1.1 → 2.0.0 |

发布前最小验证：
1. `check` 可用
2. 新能力主流程可跑通
3. 新能力文档与输出字段一致
4. 写入级命令确认机制正常

---

## 附录 A：现有代码待清理项

在规范落地前，以下现有代码隐患需优先修复：

| 文件 | 问题 | 风险 | 修复方式 |
|------|------|------|---------|
| `_const.py:29` | `DEFAULT_CHANNEL = "douyin"` 未被使用但暗示兜底 | 新人模仿写兜底逻辑 | 删除该常量 |
| `_api.py:137` | `CHANNEL_MAP.get(channel, channel)` 透传未知渠道 | 非法渠道名直达 API | 改为无默认值 + 报错 |
| `_api.py:180-185` | API 异常吞成空列表 | 调用方无法区分"无结果"和"出错" | 改为抛异常 |
| `_api.py` 整体 | 通用 HTTP 和各能力 API 混在一起 | 多人开发冲突 | 按 §2 拆分 |

---

## 附录 B：和上一版规范的主要差异

| 变更点 | 上一版 | 本版 | 原因 |
|--------|--------|------|------|
| schema.py | 每个能力必须 | 去掉 | Python CLI 中 dataclass 已足够，额外 schema 文件增加漂移风险 |
| 文档模板 | 固定 8 段 | 必选 4 段 + 可选 4 段 | 简单能力不需要填充段落浪费 Agent 上下文 |
| 错误处理 | 各文档各写一遍 | 公共文档 + 引用制 | 10 个能力 × 同一张表 = 维护灾难 |
| cli.py | 手动命令表 | 自动发现 | 多人并行开发不冲突 |
| _api.py | 单文件包含所有 API | 拆为 _http.py + 各 service | 消除多人协作的文件冲突瓶颈 |
| 安全机制 | 原则声明 | 代码层面强制（risk_level） | 不依赖 Agent 记忆，由脚本输出驱动 |
| index.md | 新增路由索引 | 去掉，由 SKILL.md 承担 | 避免两套路由表不一致 |
| 数据契约 | 无 | 新增 data-contracts.md | 多能力组合时必须对齐数据格式 |
| 迁移路径 | 无 | 渐进迁移（§2.3） | 避免一次性大重构的风险 |
