# 证据判断

## 每条记录的含义

- `date`：此记录用于考证的日期；保留 YYYY、YYYY-MM 或 YYYY-MM-DD 原有精度，没有则 null。
- `date_kind`：published=原文发表，modified=页面修改，archived=包含该词的历史快照，reported=二手文章声称的历史事件日期，unknown=未知。
- `date_basis`：说明日期在何处、对应什么。例如“PDF 原件第1页注明刊期”“页面自报日期但无旧版本”。搜索引擎日期、网站页眉今日日期、DOI编号、入库时间均不能冒充发表日期。
- `accessed_at`：实际读取时间，ISO 8601 且含时区；不是来源发表日期。
- `kind`：original、archive、repost、search_snippet、secondary。
- `status`：verified、candidate、secondary、unavailable。
- `meaning_match`：是否符合本次研究含义；true 时 meaning 必须与调查 meaning 完全一致。
- `date_verified`：是否核实该内容在此日期已经存在。不能仅因当前页面标注旧发布日期就设为 true。
- `verification_note`：写明实际做过的核对及尚不能证明的部分；保留原文的短摘录，不复制全文。

## 状态选择

| 观察到的材料 | 可使用的状态与结论 |
| --- | --- |
| 历史快照中已含该词、含义匹配 | verified + archived；仅证明至迟在该快照日期已存在 |
| 原始刊物／固定版本的有日期文档中已含该词 | 实际核对原件、版本日期和用词后可 verified + published |
| 动态网页标注旧发布日期，无法确认旧版内容 | candidate；date_verified=false |
| 二手报道说某人某年首创 | secondary + reported；沿引用继续查原始材料 |
| 原文打不开，只有搜索摘要 | unavailable/search_snippet；不能写为已核验 |
| 同词但含义不同 | meaning_match=false；不进入本次最早记录或独立传播节点 |

脚本要求 verified 必须有原始／档案材料、对应含义以及已核验发布／存档日期。这只能防止字段误用；证据真伪、语义和日期依据由执行调查的 Agent 核对。

`status` 输出的 earliest_candidates 会保留精度重叠的记录：例如“2000年”和“2000-06-01”不能据此确定哪条在前。不得为了给一个日期而丢弃不确定候选。无证据时允许 earliest_ids=[]。

早于查询日期的搜索无结果可能来自收录遗漏、访问限制或失效页面，不能用它证明该词尚未诞生。热度也不由搜索结果条数推算。

## 参考资料

- [Arquivo.pt 日期说明](https://sobre.arquivo.pt/en/help/search-2/)：存档日期与发布日期不同。
- [Google 页面日期说明](https://developers.google.com/search/blog/2019/03/help-google-search-know-best-date-for)：搜索引擎综合多个信号判断日期。
- [Google Trends 数据说明](https://support.google.com/trends/answer/4365533?hl=en)：采样、归一化和低量数据限制。
