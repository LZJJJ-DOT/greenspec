# GreenSpec 规范 RAG 项目 Vibe Coding 规格文档

> 版本：v0.1
> 
> 目标：以 GB/T 50378-2019、GB 55015-2021 构建首版知识库；GB 50189-2015 不收录独立条文，仅保留 GB 55015-2021 中的原文引用和待核验版本关系。系统面向北京地区普通办公楼方案/初步设计预审，提供可追溯的规范 RAG 能力。
> 
> 本文同时作为产品需求、数据契约、系统设计、实施计划和验收标准。Vibe Coding 实现必须以本文和 `greenspec/contracts/` 中的现有协议为约束。

## 1. 结论先行

当前四步 PRD 的方向正确，但还缺少六类决定项目能否落地的内容：

1. 统一的规范数据契约和数据质量门禁。
2. 标准版本、施行日期、废止/替代关系的权威治理模型。
3. 查询理解、过滤策略、混合检索排序和无证据回答闸门。
4. 引用、证据包和回答输出的固定接口。
5. 评测集、人工标注规则、基线和上线阈值。
6. 模型、索引、数据库、资源和运行日志的工程化配置。

两份清洗文件可以作为第一批数据输入，但不能直接当作最终索引数据：

- [清洗后 GB55015-2021](C:\Users\liang\Desktop\agent学习\gpt-researcher\规范标准\清洗后的md格式\2\清洗后GB55015-2021_建筑节能与可再生能源利用通用规范.md) 已有页级 `content_type`、表格 ID、公式 ID 和图片资源。
- [清洗后 GB/T 50378-2019](C:\Users\liang\Desktop\agent学习\gpt-researcher\规范标准\清洗后的md格式\1\清洗后GBT50378-2019_绿色建筑评价标准 .md) 已有更详细的结构化注释，包含 
ormative_table`、
ormative_formula` 等节点级元数据。
- 两份文件的字段名称和注释形态仍不完全一致，必须先经过统一解析器转为 canonical JSONL。
- 当前仓库已有 `greenspec/knowledge_base/index/clauses.jsonl`、`LocalClauseRetriever`、适用性判断、证据验证和确定性评测雏形，应在其上扩展，避免另起一套互不兼容的协议。

当前数据的具体注意事项：

- GB/T 50378 文件头部的 ppendices_detected: false 与实际结构化内容不一致，规范化阶段必须把这类声明与实际节点扫描结果比对，并在不一致时阻断索引或生成审计警告。
- GB 55015 使用页区域继承式注释，而 GB/T 50378 同时使用页级和节点级块注释；解析器应优先读取节点级元数据，再用最近的页区域元数据补全。
- 50378 的表格/公式字段已经接近 canonical 结构，55015 需要通过适配器统一命名，不能直接按文件名或标题正则写死。

第一版的产品定位：

- 输出“规范预审、适用性判断、资料缺口和风险提示”。
- 不输出具有法律效力的自动审图结论。
- 所有关键结论必须绑定标准、版本、条文号、PDF 页码和原文证据。
- 无法确认版本关系、适用条件或关键数值时，输出 
eeds_manual_review`，不能猜测。

## 2. MVP 范围

### 2.1 首批支持

- 地区：北京项目，国家标准作为基础来源。
- 建筑类型：普通办公楼/公共建筑。
- 设计阶段：方案深化、初步设计。
- 目标：二星级预审、三星级差距分析。
- 标准：GB/T 50378-2019、GB 55015-2021。GB 50189-2015 不进入独立条文索引；只有完成人工登记后，才允许扩展版本比较能力。
- 输出：适用条文清单、风险登记表、资料缺口、证据包、带引用的 Markdown 报告。

### 2.2 暂不承诺

- 全国各地区地方政策自动适配。
- 自动完成能耗、采光、声环境或碳排放计算。
- 自动判定正式竣工评价或三星级最终达标。
- 自动认定标准之间的法律替代关系；未核验的替代关系不得改变检索结果。
- 只凭一段自然语言生成无引用的合规结论。

## 3. 目标架构

```text
原始 PDF / 清洗 Markdown / 地方政策 / 项目资料
                 |
         ingestion + provenance
                 |
      canonical JSONL + quality gates
                 |
   parent/child chunk builder + manifest
                 |
      BM25 index       Vector index
           \             /
            metadata pre-filter
                    |
             RRF fusion
                    |
             BGE reranker
                    |
       applicability / version checks
                    |
       Evidence Pack + citation validator
                    |
      answer gate + report publisher
                    |
 trace / audit log / offline evaluation / feedback
```

### 3.1 模块边界

| 模块 | 责任 | 不负责 |
|---|---|---|
| `ingestion` | 读取 Markdown、PDF、图片和来源信息，生成文档清单 | 不修改规范原文 |
| 
ormalization` | 统一字段、编号、页码、节点类型和枚举 | 不猜测 OCR 内容 |
| `chunking` | 生成父节点、子节点、表格/公式节点 | 不根据 token 长度切断条文语义 |
| `indexing` | 建立 BM25、向量和过滤索引 | 不决定条文是否适用 |
| `retrieval` | 查询理解、过滤、BM25/本地 bge-base-zh-v1.5、RRF、bge-reranker-v2-m3 rerank | 不生成最终结论 |
| `governance` | 版本状态、替代关系和证据等级 | 不用相似文本自动宣布废止 |
| `applicability` | 根据项目画像判断适用状态和缺失事实 | 不替代专家审查 |
| `answering` | 只根据 Evidence Pack 生成有引用的回答 | 不补写来源之外的数字 |
| `evaluation` | 离线评测、回归、质量门禁 | 不修改人工金标准 |

## 4. 前置准备清单

### 4.1 必须先准备的资料

- GB 50189-2015 如被保留，仅作为隔离的来源/版本治理资料登记；不得抽取或索引其独立条文。
- 两份清洗 Markdown 对应的原始 PDF 和页码映射。
- 两份 Markdown 中所有图片资源及相对路径。
- 标准版本登记表：标准编号、标准名称、版本、发布日期、实施日期、当前状态、适用区域、替代/被替代关系。
- 北京地方政策和地方标准清单；每份文件必须有生效范围和有效期。
- 10～30 个真实或脱敏项目问题，用于建立第一版检索评测集。
- 由专业人员标注的条文命中、适用状态、版本状态和引用完整性金标准。

### 4.2 必须先决定的工程选项

- 向量库：固定使用 Qdrant；通过 Docker 本地运行，collection 使用 metadata payload 支持标准、版本、内容类型和适用范围过滤。
- BM25：MVP 可使用 Elasticsearch/OpenSearch、Whoosh 或 SQLite FTS；中文分词必须固定版本并纳入测试。
- Embedding：固定使用本地 `bge-base-zh-v1.5` 服务。必须记录模型版本、向量维度、归一化方式、设备、批大小和最大长度。
- Reranker：固定使用本地 `bge-reranker-v2-m3` 服务，并记录设备、最大输入长度、批大小、超时、降级和模型版本。
- LLM：回答模型、温度、最大输出、JSON/Markdown 输出约束和降级模型。
- 数据库：建议 SQLite/PostgreSQL 保存文档登记、关系、索引清单、查询日志和评测运行信息。
- 运行方式：先支持本地 CLI + API，再接入现有 FastAPI/前端工作台。

### 4.3 数据质量门禁

每次索引前必须自动检查：

- PDF 页码连续，物理页码唯一。
- `standard_id`、`standard_name`、`version_year`、`source_file` 非空。
- 可索引节点具有 `content_type` 和 `indexable`。
- 可检索条文具有 `clause_id`、`clause_no` 或明确的待确认状态。
- 表格续表能匹配到唯一主表；公式编号不重复或有明确区域前缀。
- `source_page` 与 `pdf_page` 均可追溯；原书页码为空时不能用物理页码冒充。
- 图片路径存在，图片节点有 `asset_id` 和页码。
- `verification_status=needs_manual_check` 的节点不得进入“已验证权威证据”集合。
- 不可索引内容不进入 BM25 或向量索引。
- 每条 JSONL 能通过 JSON Schema 校验，失败时索引构建必须中止。

## 5. Canonical JSONL 数据契约

建议新建 `greenspec/contracts/clause.schema.json`，所有来源最终转为一条记录一行的 JSONL。字段如下：

```json
{
  "clause_id": "GB55015-2021-normative-clause-3.2.10",
  "parent_id": "GB55015-2021-normative-section-3.2",
  "document_id": "GB55015-2021",
  "standard_id": "GB 55015-2021",
  "standard_name": "建筑节能与可再生能源利用通用规范",
  "standard_version": "2021",
  "document_status": "current",
  "content_type": "normative_clause",
  "clause_type": "requirement",
  "clause_no": "3.2.10",
  "clause_title": "电机驱动的蒸汽压缩循环冷水（热泵）机组的综合部分负荷性能系数",
  "hierarchy": {
    "part": null,
    "chapter": "3",
    "section": "3.2",
    "subsection": "3.2.10",
    "parent_titles": ["3 新建建筑节能设计", "3.2 供暖、通风与空调"]
  },
  "text": "规范原文，不总结、不改写",
  "retrieval_text": "用于检索的标题、条文号、主题、适用条件和原文拼接文本",
  "summary": null,
  "keywords": ["IPLV", "冷水机组", "部分负荷性能系数"],
  "region": ["national"],
  "building_type": ["public_building", "office"],
  "design_phase": ["scheme", "preliminary_design"],
  "green_target_scope": [],
  "applicability_rules": [],
  "requires_project_facts": ["机组类型", "名义制冷量"],
  "requires_calculation": false,
  "requires_manual_review": false,
  "risk_level_hint": "P1",
  "pdf_page_start": 35,
  "pdf_page_end": 35,
  "printed_page_start": "25",
  "printed_page_end": "25",
  "source_file": "GB55015-2021.pdf",
  "source_sha256": "...",
  "source_level": "T0",
  "verification_status": "verified",
  "indexable": true,
  "table_id": null,
  "formula_id": "GB55015-2021-normative-formula-3.2.10",
  "asset_ids": [],
  "supersession_ids": [],
  "provenance": {
    "parser_version": "clause-parser-0.1",
    "source_markdown": "...",
    "extraction_run_id": "ING-20260821-001"
  }
}
```

### 5.1 `content_type` 枚举

```text
publication_info
reference_standards
toc
normative_front_matter
normative_body
normative_clause
normative_table
normative_formula
appendix
appendix_clause
commentary_front_matter
commentary
commentary_clause
commentary_table
commentary_formula
commentary_appendix
figure
non_content
```

`content_type` 描述内容性质，`clause_type` 描述业务语义，不能混为一个字段。

### 5.2 父子切片规则

父节点保留完整上下文，子节点承担精准检索：

- 父节点：章、节、附录、条文说明章节。
- 条文子节点：一条完整条文及其款、项、注。
- 表格子节点：完整表头 + 数据，续表通过同一个 `table_id` 关联。
- 公式子节点：公式 + “式中”变量解释 + 所属条文。
- 图节点：图题、图片、页码和前后说明。
- 不可索引节点：保留在归档数据中，但不进入检索索引。

子节点不得跨越无关条文；表头、公式变量说明和适用条件不得被长度切片拆散。`retrieval_text` 可以包含父标题和相邻上下文，但 `text` 必须保留原文。

## 6. 版本和冲突治理

### 6.1 标准登记表

建立 `standard_registry`：

```json
{
  "standard_id": "GB 55015-2021",
  "standard_name": "建筑节能与可再生能源利用通用规范",
  "version_year": "2021",
  "published_date": "2021-09-08",
  "effective_date": "2022-04-01",
  "status": "current",
  "region": ["national"],
  "authority_level": "mandatory_code",
  "source_level": "T0",
  "supersedes": [],
  "superseded_by": [],
  "relation_verification_status": "verified",
  "source_refs": []
}
```

### 6.2 条文关系

建立独立的 `clause_relations.jsonl`，不要把替代关系硬编码在条文文本中：

```json
{
  "relation_id": "REL-55015-50189-001",
  "from_clause_id": "GB55015-2021-normative-clause-...",
  "to_clause_id": "GB50189-2015-reference-clause-...",
  "target_clause_indexed": false,
  "relation_type": "partially_supersedes",
  "scope": "仅替代明确列出的强制性条文/适用范围",
  "status": "verified",
  "effective_from": "2022-04-01",
  "evidence_refs": ["..."],
  "manual_reviewer": "...",
  "notes": "不能据相似主题自动推断"
}
```

允许的文档/条文状态：

```text
current
superseded
partially_superseded
repealed_candidate
not_applicable_region
pending_manual_review
```

检索时的原则：

1. `current` 不是简单按年份判断，必须结合生效日期和适用范围。
2. `partially_superseded` 只排除明确被替代的条文，其他条文仍可返回。
3. `repealed_candidate` 和缺失关系不得自动过滤为废止。
4. 回答若同时返回新旧标准，必须解释二者关系和适用范围。
5. 无法确认替代关系时，回答状态为 
eeds_manual_review`。

## 7. 混合检索设计

### 7.0 固定模型和知识范围

```text
Embedding：本地 bge-base-zh-v1.5
Reranker：本地 bge-reranker-v2-m3
Vector store：Qdrant
Commentary retrieval：disabled
GB 50189-2015 independent clauses: excluded
```

固定数据边界：

- 活动索引只包含 GB/T 50378-2019 和 GB 55015-2021 的可索引正文、附录、表格和公式。
- GB 50189-2015 不收录独立条文；GB 55015-2021 中出现的 GB 50189 引用必须原样保留，并可作为 reference_standards 归档节点，但不单独产生 GB 50189 条文证据。
- 不自动宣称 GB 50189-2015 整本废止。未核验的替代关系不得改变索引过滤、召回、排序或回答。
- 条文说明保留在原始/处理数据中，但 indexable=false，不参与任何检索通道。

### 7.1 查询结构化

将用户查询解析为：

```json
{
  "query_text": "办公楼外窗传热系数要求",
  "standard_ids": [],
  "clause_nos": [],
  "region": "beijing",
  "building_type": "office",
  "design_phase": "preliminary_design",
  "green_target_scope": "two_star_precheck",
  "as_of_date": "2026-08-21",
  "must_be_current": true,
  "include_commentary": false,
  "commentary_retrieval": "disabled",
  "top_k": 20
}
```

查询解析失败时，保留原始查询并把不确定字段置为 
ull`，不能把猜测的建筑类型或地区作为硬过滤条件。

### 7.2 过滤策略

- 硬过滤：`indexable=true`、语言、明确指定的标准编号/条文号、用户明确指定的地区和版本。
- 软过滤：建筑类型、设计阶段、绿建目标、是否需要计算、主题标签。
- 未知值：默认不排除候选，但降低排序分并进入适用性判断。
- 废止/替代：先经过版本治理，再决定是否排除。
- 条文说明不参与检索：`commentary*` 节点保留在归档数据中，但统一设置 `indexable=false`，不得进入 BM25、向量、RRF、Reranker 或 Evidence Pack。

### 7.3 召回与融合

默认流程：

1. BM25 召回 `k_bm25=50`。
2. 本地 bge-base-zh-v1.5 向量召回 `k_dense=50`。
3. 对两路结果按 `clause_id` 去重。
4. 使用 Reciprocal Rank Fusion：

```text
RRF(d) = Σ 1 / (k + rank_i(d))
k 默认 60
```

5. 保留融合前后的 rank、分数和过滤原因，便于调试。
6. 对前 30～50 个候选使用本地 `bge-reranker-v2-m3` 精排。
7. 返回前 `top_k=8～12` 个证据候选，并保留父节点上下文。

不要直接把 BM25 分数和向量余弦分数相加；两者量纲不同，必须使用 RRF 或经过验证的归一化方法。

### 7.4 证据分组

检索结果需要按以下组装 Evidence Pack：

- `primary_normative`: 当前有效的规范正文条文。
- `supporting_table_formula`: 与条文绑定的表格和公式。
- `commentary_archive`: 条文说明仅作原始资料归档，不参与检索、重排或正式回答。
- `version_relation`: 新旧标准关系证据。
- `project_facts`: 项目资料中的事实。
- `policy`: 地方政策或管理文件。

## 8. Greenspec 集成

现有代码中的 `LocalClauseRetriever` 目前是关键词评分和元数据过滤，下一步应拆成接口：

```python
class ClauseRetriever(Protocol):
    def retrieve(self, request: RetrievalRequest) -> list[RetrievedClause]: ...
```

建议新增模块：

```text
greenspec/knowledge_base/
  contracts.py              # Pydantic 数据模型
  ingest_markdown.py        # Markdown -> canonical JSONL
  validate_jsonl.py         # Schema + provenance 门禁
  chunk_builder.py          # parent/child 构建
  manifest.py               # 索引清单和版本
  bm25_index.py             # BM25 建索引/查询
  dense_index.py            # 本地 bge-base-zh-v1.5 建索引/查询
  hybrid_retriever.py       # filter + BM25 + dense + RRF
  reranker.py               # 本地 bge-reranker-v2-m3 封装
  version_governance.py     # standard registry + clause relations
  citation.py               # 引用格式和完整性校验
```

现有模块应保持兼容：

- `LocalClauseRetriever` 先作为 `KeywordRetriever` 适配器。
- `evidence_verifier` 继续验证证据等级、来源、条文号、页码和版本。
- `applicability_judge` 消费统一的 `RetrievedClause`，不再依赖某个 JSONL 的私有字段。
- `greenspec/contracts/` 现有 `applicability_results`、`risk_register`、`evidence_verification` 协议必须保持向后兼容；新增字段需要升级协议版本。

## 9. 统一检索/回答接口

### 9.1 检索接口

`POST /api/v1/retrieve`

请求：

```json
{
  "query": "办公楼外窗传热系数要求是什么？",
  "project_profile": {
    "region": "beijing",
    "building_type": "office",
    "design_phase": "preliminary_design",
    "green_target": "two_star_precheck"
  },
  "filters": {
    "standard_ids": [],
    "as_of_date": "2026-08-21",
    "must_be_current": true
  },
  "top_k": 10
}
```

响应必须包含：

```json
{
  "request_id": "REQ-...",
  "retrieval_run_id": "RET-...",
  "items": [],
  "filters_applied": [],
  "warnings": [],
  "index_manifest_id": "IDX-..."
}
```

每个 item 至少包含：`clause_id`、`parent_id`、`content_type`、`text`、`standard_id`、`standard_version`、`clause_no`、`pdf_page_start`、`pdf_page_end`、`printed_page_start`、`source_file`、`verification_status`、`document_status`、`bm25_rank`、`dense_rank`、`rrf_score`、`rerank_score`。

### 9.2 回答闸门

回答生成前执行：

- 是否至少有一个 `source_level=T0` 或明确允许的高等级证据。
- 是否存在当前版本/适用范围冲突。
- 每个事实性 claim 是否能绑定 Evidence ID。
- 每个引用是否有标准名称、编号、版本、条文号和 PDF 页码。
- 是否把 `commentary` 错当成规范正文。
- 是否有 
eeds_manual_review`、缺失项目事实或未验证表格数值。

无法通过闸门时，回答必须降级为：已知证据 + 缺失信息 + 人工核对事项，而不是继续生成确定性结论。

### 9.3 引用格式

推荐统一格式：

```text
[GB 55015-2021，第 3.2.10 条，PDF 第 35 页，原书第 25 页]
```

表格/公式引用应增加 `表号` 或 `式号`。回答正文中的每个规范性结论都必须有引用，报告末尾再输出机器可解析的 `citations` 数组。

## 10. 评测体系

### 10.1 评测数据结构

新建 `greenspec/evals/rag_cases.jsonl`，每行一个案例：

```json
{
  "case_id": "RAG-001",
  "query": "北京办公楼方案阶段外窗传热系数适用哪些要求？",
  "project_profile": {
    "region": "beijing",
    "building_type": "office",
    "design_phase": "scheme",
    "green_target": "two_star_precheck"
  },
  "gold_clause_ids": ["..."],
  "acceptable_clause_ids": ["..."],
  "gold_applicable_status": "needs_manual_review",
  "gold_version_status": "current",
  "gold_citations": [
    {"standard_id": "GB 55015-2021", "clause_no": "...", "pdf_page": 35}
  ],
  "gold_answer_points": ["..."],
  "required_manual_review": true,
  "difficulty": "medium"
}
```

至少覆盖：

- 条文号直接查询。
- 表格临界值查询。
- 公式和单位查询。
- 建筑类型/设计阶段过滤。
- 北京地方政策查询。
- 新旧标准冲突查询。
- 资料不足应返回待确认。
- 正文与条文说明区分。
- 跨页表格完整性。
- 版本日期边界。

### 10.2 指标定义

保留 RAGAS，但不能只依赖 RAGAS：

- `Faithfulness`：回答声明能否被证据支持。
- `Answer Relevancy`：回答是否回应问题。
- `Context Precision`：前排证据是否相关。
- `Context Recall`：金标准证据是否被召回。
- `Clause Hit@k`：金标准条文在前 k 的命中率。
- `Citation Accuracy`：标准/版本/条文号/页码是否准确。
- `Citation Completeness`：需要引用的 claim 中有引用的比例。
- `Applicability Accuracy`：适用/不适用/待确认状态准确率。
- `Mandatory Clause Recall`：强制性条文召回率。
- `Version Conflict Detection Rate`：版本冲突识别率。
- `Abstention Precision`：系统拒答/待确认是否真的应该拒答。
- `Table Formula Integrity`：表格、公式及其上下文是否完整返回。

RAGAS 的 LLM 评判结果必须和确定性脚本分开记录，不能用一个总分掩盖引用错误。中文问题集至少要人工抽样复核 20% 的评测结果。

### 10.3 第一版验收阈值

阈值是初始门槛，建立足够评测集后再校准：

- JSONL Schema 通过率：100%。
- 可索引节点页码和标准版本完整率：100%。
- Clause Hit@10：≥ 0.85。
- Citation Accuracy：≥ 0.95。
- Citation Completeness：≥ 0.90。
- Mandatory Clause Recall：≥ 0.95。
- Version Conflict Detection Rate：≥ 0.90。
- 不应确定回答的 
eeds_manual_review` 召回率：≥ 0.90。
- 关键引用错误为 0 个才允许发布基线版本。

## 11. 实施阶段

### Phase 0：数据和协议冻结

产出：

- `clause.schema.json`、`standard.schema.json`、`clause_relation.schema.json`。
- 两份 Markdown 的 canonical JSONL。
- 标准登记表和来源 SHA-256。
- 解析器审计报告。
- 10 个最小评测案例。

完成条件：两份文件可被同一个解析器读取，页码、条文、表格、公式和图片均可追溯。

### Phase 1：父子切片和本地检索

产出：

- parent/child chunk builder。
- BM25 索引。
- 兼容现有 `LocalClauseRetriever` 的检索接口。
- `retrieve` CLI 和单元测试。

完成条件：条文号、表号、公式号查询可返回正确条文，并能显示父级标题和来源页码。

### Phase 2：本地 Embedding、RRF 和 Reranker

产出：

- dense index manifest。
- 本地 bge-base-zh-v1.5 embedding provider。
- RRF 融合和本地 bge-reranker-v2-m3。
- 分数、排名、过滤原因可观测。

完成条件：混合检索在离线集上优于 BM25-only 和 dense-only 基线，且过滤不会丢失明确指定条文。

### Phase 3：版本治理和 Evidence Pack

产出：

- `standard_registry`。
- `clause_relations`。
- Evidence Pack schema。
- citation validator 和 answer gate。

完成条件：新旧标准问题能返回关系状态；不确定关系不会自动给出确定性替代结论。

### Phase 4：适用性和项目资料

产出：

- 项目画像 schema。
- 项目资料事实抽取和人工确认界面。
- applicability/risk/evidence 三类结构化输出。

完成条件：缺少关键项目事实时，系统输出 
eeds_manual_review` 和明确的 `missing_facts`。

### Phase 5：评测、回归和工作台

产出：

- RAGAS adapter。
- 确定性指标脚本。
- 检索/回答 trace。
- 评测报告和版本对比。
- 前端项目中心、检索结果和证据查看页。

完成条件：每次数据或模型变更都能重建索引、运行回归评测并比较结果。

## 12. Vibe Coding 任务拆分

按以下顺序生成代码，每个任务完成后运行测试，不要一次生成全部 Agent：

1. `contracts`：Pydantic 模型、JSON Schema、枚举和样例。
2. `ingest_markdown`：解析两种 Markdown 注释格式，统一成 canonical JSONL。
3. `validate_jsonl`：页码、ID、表格续表、公式、图片和 schema 门禁。
4. `chunk_builder`：父节点、条文节点、表格节点、公式节点。
5. `manifest`：数据版本、模型版本、来源哈希和索引版本。
6. `bm25_index`：中文分词、建立和查询 BM25。
7. `dense_index`：本地 bge-base-zh-v1.5 provider、批量向量化、缓存和重建。
8. `hybrid_retriever`：过滤、两路召回、RRF、结果解释。
9. `reranker`：本地 `bge-reranker-v2-m3` 批处理、超时和降级。
10. `version_governance`：标准登记、条文关系和状态过滤。
11. `evidence_pack`：统一 local clause、table、formula、policy、project fact。
12. `citation`：引用渲染、引用完整性和答案闸门。
13. `evals`：检索指标、引用指标、适用性指标、RAGAS 适配器。
14. `api`：`/ingest`、`/index/build`、`/retrieve`、`/answer`、`/evaluate`。
15. `ui`：项目画像、证据结果、版本关系、人工复核和评测页面。

每个 Vibe Coding 任务必须同时生成：实现代码、单元测试、最小样例、运行命令和失败时的错误信息。禁止先做漂亮 UI 再补数据协议。

## 13. 测试要求

### 单元测试

- Markdown 页码和节点解析。
- content_type/indexable 继承。
- 条文号、表号、公式号解析。
- 跨页表格合并。
- 中文 BM25 分词和关键词召回。
- hard/soft filter 行为。
- RRF 排名计算。
- 版本关系状态机。
- 引用完整性校验。
- JSON Schema 校验。

### 集成测试

- 两份 Markdown 从输入到 JSONL、索引、检索的完整链路。
- 指定条文号不会被版本过滤误删。
- 表格和公式返回完整上下文。
- 新旧标准冲突查询返回关系说明。
- 缺失地区/建筑类型/设计阶段时返回待确认。
- 
eeds_manual_check` 节点不作为 T0 已验证证据。

### 回归测试

固定保存：

- 数据 manifest。
- embedding/reranker 模型版本。
- 查询集。
- 召回排名。
- 最终答案和引用。
- 指标报告。

任何数据、分词器、模型或过滤规则变更，都必须生成新的 `run_id`，不能覆盖历史结果。

## 14. 运行和安全要求

- API 不接受任意文件路径，输入文件必须位于允许的数据目录。
- 原始 PDF、清洗 Markdown、JSONL 和索引使用不同目录，索引构建不覆盖原始资料。
- 所有上传文件记录 SHA-256，报告记录对应 `index_manifest_id`。
- 日志中不打印项目资料中的敏感个人信息。
- 模型和索引构建使用超时、批量限制和可取消任务。
- 向量索引和 BM25 索引必须可重建，不把索引当成唯一数据源。
- 输出报告必须记录生成时间、模型、检索配置、数据版本和人工复核状态。

## 15. 当前最重要的难点

1. **规范语义结构化**：章节、条文、款项、注、表格和公式的边界不等于 Markdown 标题边界，必须以页码和语义规则共同解析。
2. **复杂表格检索**：列头和空单元格承载条件关系，逐行展开文本不能丢失原始表头上下文。
3. **版本关系不是相似度问题**：GB 55015-2021 与 GB 50189-2015 的替代范围需要证据和人工确认，不能让 LLM 自动判定。
4. **过滤误杀**：项目画像缺字段时，硬过滤会让真正相关条文消失；安全策略是未知降权并转人工确认。
5. **混合分数不可直接比较**：BM25、向量和 reranker 必须保留原始分数并用 RRF/标定融合。
6. **引用完整性**：回答正确但页码、版本或条文号错，仍然是不可接受的规范 RAG 错误。
7. **评测集建设**：RAGAS 不能代替建筑规范专家标注，必须建立条文命中、版本冲突和适用性金标准。
8. **模型资源**：本地 bge-base-zh-v1.5 和 bge-reranker-v2-m3 需要独立模型服务、设备检查、批处理、缓存和降级方案，不能只在配置文件中写模型名。

## 16. 第一周执行清单

- [ ] 固定 canonical JSONL 字段和枚举。
- [ ] 解析两份 Markdown，输出审计报告和第一版 JSONL。
- [ ] 将 GB 50189-2015 标记为非活动标准：不抽取独立条文、不进入检索索引；保留 GB 55015-2021 中的相关原文引用。
- [ ] 建立标准登记表和来源哈希。
- [ ] 生成父子切片，抽样检查 30 条文、10 张表、全部公式。
- [ ] 用现有 `clauses.jsonl` 建立兼容适配器。
- [ ] 准备 10 个检索评测问题和金标准引用。
- [ ] 先实现 BM25-only baseline。
- [ ] 固定 Evidence Pack 和引用格式。
- [ ] 用一个查询跑通“检索 -> 证据包 -> 引用回答 -> 评测”。

## 17. Definition of Done

只有同时满足以下条件，才算第一版 RAG 完成：

- GB/T 50378-2019 和 GB 55015-2021 通过统一 Schema；GB 50189-2015 不产生独立条文索引记录。
- 任意返回条文都能追溯到标准、版本、条文号、PDF 页码和原文。
- 表格和公式切片必须保留完整上下文；条文说明只保留归档，不进入检索。
- GB 55015-2021 中关于 GB 50189-2015 的引用原文完整保留；不自动宣称 GB 50189-2015 整本废止，未核验的替代关系不得改变检索结果。
- BM25-only、dense-only、hybrid 三种基线均可复现。
- 回答没有证据时会拒答或输出资料缺口，不编造条文。
- 评测集可重复运行，指标和模型/数据版本绑定。
- 现有 `applicability_results`、`risk_register`、`evidence_verification` 协议仍能通过测试。
- 人工可以在界面中查看原文、页码、表/公式和版本关系，并确认或驳回结论。

---

## 给 Vibe Coding 的启动指令

先阅读本文、`gpt_researcher/项目背景.md`、`greenspec/contracts/` 和 `greenspec/knowledge_base/index/clauses.jsonl`。不要直接修改 Markdown 原文。第一轮只实现：

1. canonical clause Pydantic 模型和 JSON Schema；
2. 两份 Markdown 解析器；
3. 数据质量审计命令；
4. parent/child JSONL 输出；
5. BM25-only 检索和 10 个测试案例。

完成并通过测试后，再实现本地 bge-base-zh-v1.5、RRF、本地 bge-reranker-v2-m3、版本治理和回答生成。任何无法确认的 OCR、版本替代关系、适用性条件或项目事实，都必须保留为 
eeds_manual_review`，不得在代码中静默猜测。