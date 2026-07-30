# GreenSpec Eval Report

- Run directory: `outputs\run_1784972382_请针对北京普通办公楼方案_初设阶段，研究绿色建筑二星级预审与三星级差距分析所需关`
- Generated at: 2026-07-25T09:47:27.173713+00:00
- Score: **10/10**

## Results

| ID | Category | Result | Name | Details |
| --- | --- | --- | --- | --- |
| EVAL-001 | task_decomposition | PASS | Section count is reasonable | sections=4, expected=3..8 |
| EVAL-002 | task_decomposition | PASS | Sections cover core project topics | matched_groups=['green_building', 'star_gap', 'energy', 'renewable_energy', 'data_gap'], required=4 |
| EVAL-003 | clause_recall | PASS | Local clause evidence is retrieved | local_clause_count=12 |
| EVAL-004 | clause_recall | PASS | Core rating clauses are recalled | matched_clause_ids=['GBT50378-2019-003', 'GBT50378-2019-004', 'GBT50378-2019-005'] |
| EVAL-005 | web_source_level | PASS | Web source levels use allowed values | web_count=2, invalid=[] |
| EVAL-006 | web_source_level | PASS | Web evidence is classified and has URL | web_count=2, unclassified_or_missing_url=[] |
| EVAL-007 | risk_level | PASS | Risk levels are valid | risk_count=3, invalid_levels=[] |
| EVAL-008 | risk_level | PASS | Critical missing parameters create high risk | mode=critical_parameters_missing, missing=['has_envelope_thermal_parameters', 'has_lighting_power_density', 'has_renewable_energy_scheme'], high_risks=['RISK-001', 'RISK-002'] |
| EVAL-009 | report_structure | PASS | Report contains required headings | headings=['引言与系统边界', '目录', '绿色建筑评价标准框架与得分差距分析', '建筑能效差距与绿色建筑预审咨询分析报告（基于北京办公建筑二星/三星对标）', '可再生能源利用与政策合规——迈向近零能耗建筑的咨询预审指南', '方案设计阶段资料与文档需求分析（面向绿建预审咨询）', 'evidence pack summary', '结论与待复核项', '参考文献'], missing_groups=[] |
| EVAL-010 | report_structure | PASS | Report is non-empty and has no placeholders | characters=21614, forbidden_found=[] |

## Failed Cases

No failed cases.
