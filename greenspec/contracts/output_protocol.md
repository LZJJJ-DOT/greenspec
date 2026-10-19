# GreenSpec Output Protocol v0.1

这个文件定义 GreenSpec 第一版结构化输出格式。

你可以把它理解成两张表的“表头说明”：

- `applicability_results.json`：每条条文/证据是否适用于当前项目
- `risk_register.json`：当前项目有哪些风险，风险等级是什么

这份文档是给人看的。  
旁边的 `*.schema.json` 是给程序校验用的。

## 通用规则

第一版先保持简单：

- 两个结果文件的顶层都是 JSON 数组
- 一条数组记录代表一条业务结果
- 字段名固定使用英文小写加下划线
- 状态值固定使用英文枚举
- 没有内容的列表写成 `[]`
- `confidence` 使用 `0` 到 `1` 之间的数字
- 引用其他内容时只写 ID，不复制整段证据原文

## applicability_results.json

用途：

记录“某一条证据/条文对当前项目是否适用”。

顶层结构：

```json
[
  {
    "result_id": "APP-001"
  }
]
```

一条记录必须包含这些字段：

- `result_id`：适用性判断结果 ID，例如 `APP-001`
- `evidence_id`：对应 `evidence_pack.json` 里的证据 ID
- `clause_id`：原始条文 ID
- `clause_no`：条文号；没有就写 `null`
- `applicable_status`：适用性状态
- `confidence`：置信度，范围是 `0` 到 `1`
- `reason_codes`：判断理由代码列表
- `project_matches`：项目参数和条文适用范围的匹配情况
- `missing_facts`：当前项目缺少的事实或资料
- `manual_review_required`：是否需要人工复核

`applicable_status` 只能使用下面三个值：

- `applicable`：适用，而且当前信息足够做初步判断
- `not_applicable`：明确不适用
- `needs_manual_review`：可能适用，但缺资料、需计算或必须人工确认

`project_matches` 固定包含这四项：

```json
{
  "region": true,
  "building_type": true,
  "design_phase": true,
  "green_target_scope": true
}
```

第一版允许的 `reason_codes`：

- `PROJECT_SCOPE_MATCHED`
- `REGION_MATCHED`
- `BUILDING_TYPE_MATCHED`
- `DESIGN_PHASE_MATCHED`
- `GREEN_TARGET_SCOPE_MATCHED`
- `PROJECT_FACTS_MISSING`
- `REQUIRES_CALCULATION`
- `MANUAL_REVIEW_REQUIRED`
- `REGION_NOT_MATCHED`
- `BUILDING_TYPE_NOT_MATCHED`
- `DESIGN_PHASE_NOT_MATCHED`
- `GREEN_TARGET_SCOPE_NOT_MATCHED`

示例文件：

```text
greenspec/examples/applicability_results.example.json
```

## risk_register.json

用途：

记录“当前项目有哪些风险，以及这些风险为什么出现”。

顶层结构：

```json
[
  {
    "risk_id": "RISK-001"
  }
]
```

一条记录必须包含这些字段：

- `risk_id`：风险 ID，例如 `RISK-001`
- `risk_level`：风险等级
- `title`：风险标题
- `description`：风险说明
- `trigger_clause_ids`：触发风险的条文 ID 列表
- `trigger_gap_ids`：触发风险的缺口 ID 列表
- `impact`：这个风险会造成什么影响
- `mitigation`：建议怎么缓解或补充
- `next_action`：下一步动作
- `evidence_refs`：相关证据 ID 列表

`risk_level` 只能使用下面四个值：

- `P0`：阻断性风险，当前目标结论不能形成
- `P1`：高风险，影响主结论或核心判断
- `P2`：中风险，影响分析完整性或可信度
- `P3`：低风险，主要是提醒、引用、格式或补充复核问题

第一版建议使用的 `next_action`：

- `request_project_documents`
- `perform_manual_review`
- `perform_calculation`
- `confirm_project_parameter`
- `check_source_reference`

示例文件：

```text
greenspec/examples/risk_register.example.json
```

## evidence_verification.json

用途：

记录一次完整的证据验证过程，包括每条 claim 的验证结果和整个 run 的最终决策。

顶层结构：JSON object。

一个对象代表一次验证 run。对象中的 `items` 数组，每一条记录代表一个 claim 的验证结果。

必填顶层字段：

- `verification_id`
- `decision`
- `summary`
- `research_again_queries`
- `items`

字段说明：

- `verification_id`：本次验证 run 的唯一 ID，例如 `VER-001`
- `decision`：整个验证 run 的最终决策
- `summary`：按验证状态统计的数量
- `research_again_queries`：需要重新检索的问题列表
- `items`：每条 claim 的验证结果

允许的 `decision` 值：

- `accept`：所有关键 claim 都有足够证据支持
- `revise`：部分 claim 需要修改、补充引用或人工复核
- `research_again`：存在证据不足或来源等级不够的 claim，需要重新检索

每个 `items` 记录允许的 `status` 值：

- `supported`：证据足够支持该 claim
- `partially_supported`：证据只能部分支持该 claim
- `unsupported`：现有证据不能支持该 claim
- `needs_manual_review`：需要人工进一步确认

每个 `items` 记录允许的 `recommended_action` 值：

- `accept`：接受当前 claim
- `revise`：修改 claim、报告或补充引用
- `research_again`：重新检索证据

每个 `items` 记录允许的 `source_level_check` 值：

- `pass`：实际证据等级满足要求
- `fail`：实际证据等级低于要求或没有有效来源
- `needs_manual_review`：来源可能满足要求，但需要人工核验

`summary` 中的数量必须满足：

```text
claims_total
=
supported
+ partially_supported
+ unsupported
+ needs_manual_review


## 文件分工

这几个文件各自负责不同事情：

- `output_protocol.md`：给人看的说明书
- `applicability_results.schema.json`：给程序看的适用性结果校验规则
- `risk_register.schema.json`：给程序看的风险结果校验规则
- `examples/*.json`：给人和测试用的样例数据
- `outputs/.../*.json`：以后程序真正生成的结果

正常开发顺序：

1. 先写 `output_protocol.md`，把字段和含义说清楚
2. 再写 `examples/*.json`，用一条假数据确认格式是否直观
3. 再写 `*.schema.json`，把格式约束变成机器能检查的规则
4. 最后写业务代码，让代码严格按照这个协议输出

这样做是为了避免后续模块之间字段不一致。

比如一个模块输出 `status`，另一个模块读取 `applicable_status`，程序就会断。  
先定协议，就是先把模块之间的数据接口固定下来。

## 版本

## claim_set.json

用途：

将报告使用的每一条结论与本次 EvidencePack 的证据 ID、原文片段绑定。它是模型输出进入报告前的机器校验对象，不直接代替最终 Markdown 报告。

每条 claim 必须包含：

- `claim_id`、`claim`、`claim_use`
- `required_source_levels`
- `supporting_evidence_ids`：只能引用本次 EvidencePack 中的 ID
- `evidence_spans`：每个引用 ID 对应一段能在该证据 `content` 中精确找到的原文

Schema：`greenspec/contracts/claim_set.schema.json`。

Gate 的最低规则：ID 不存在、引用片段缺失或无法在证据中定位、来源等级不足、条文号/页码/版本缺失时，claim 不得标记为 `supported`，必须 `revise`、`research_again` 或人工复核。

当前版本：`v0.1`

如果以后要改字段名、删除字段、改变枚举值，应该升级协议版本。
