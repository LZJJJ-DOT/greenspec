# GreenSpec Eval Report

- Run directory: `outputs\run_1784977107_请针对北京普通办公楼方案_初设阶段，研究绿色建筑二星级预审与三星级差距分析所需关`
- Generated at: 2026-07-25T11:07:18.959570+00:00
- Score: **10/10**

## Results

| ID | Category | Result | Name | Details |
| --- | --- | --- | --- | --- |
| EVAL-001 | task_decomposition | PASS | Section count is reasonable | sections=4, expected=3..8 |
| EVAL-002 | task_decomposition | PASS | Sections cover core project topics | matched_groups=['green_building', 'star_gap', 'energy', 'renewable_energy', 'data_gap'], required=4 |
| EVAL-003 | clause_recall | PASS | Local clause evidence is retrieved | local_clause_count=12 |
| EVAL-004 | clause_recall | PASS | Core rating clauses are recalled | matched_clause_ids=['GBT50378-2019-003', 'GBT50378-2019-004', 'GBT50378-2019-005'] |
| EVAL-005 | web_source_level | PASS | Web source levels use allowed values | web_count=4, invalid=[] |
| EVAL-006 | web_source_level | PASS | Web evidence is classified and has URL | web_count=4, unclassified_or_missing_url=[] |
| EVAL-007 | risk_level | PASS | Risk levels are valid | risk_count=2, invalid_levels=[] |
| EVAL-008 | risk_level | PASS | Critical missing parameters create high risk | mode=not_applicable_no_critical_missing, missing=[], high_risks=[] |
| EVAL-009 | report_structure | PASS | Report contains required headings | headings=['引言：预审目的与系统边界', '目录', '绿色建筑预审分析报告（以北京某办公建筑为例）', '绿色建筑预审评估：星级差异与关键绩效指标', '建筑能效：绿建预审中的规范符合性与性能差距分析', '可再生能源利用：强制要求与计算缺口', '北京办公建筑2星与3星预评估的关键数据和文档差距', 'evidence pack summary', '结论：资料不足、待人工复核与后续专项计算提示', '参考文献'], missing_groups=[] |
| EVAL-010 | report_structure | PASS | Report is non-empty and has no placeholders | characters=25182, forbidden_found=[] |

## Failed Cases

No failed cases.
