# 深度溯源 v1 实施记录

用户确认：项目级 term-history Skill，中文优先，无新增付费服务，Python 3.9+ 标准库，18 次搜索／24 页原文／600 秒软预算，允许趋势 CSV。

工作区是空目录，不是现有 Git 仓库；直接在用户指定目录开发，不创建额外工作树，不提交或推送。

## 任务

- [x] 证据存储、查询日志、预算和继续调查。
- [x] 通用／Google Trends CSV、峰值、SVG。
- [x] CLI、中文报告、Skill、说明和示例。
- [x] 确定性测试、固定材料行为验证、10 词联网试用及 Agent 复核。
- [ ] 用户人工抽查关键证据（非 Agent 可代签）。

## 模块契约

所有运行时代码在 `.agents/skills/term-history/scripts/`。无第三方依赖。

`trends.py` 暴露 `parse_csv(path, format, metadata)` 和 `render_svg(series)`；format 为 `generic` 或 `google`。

metadata 必填 `term, source, source_url, metric, region, start, end, granularity`；日期范围使用 YYYY-MM-DD，granularity 为 day/week/month。Google 文件多条数值列时以 metadata 的 `column` 精确选择列；一列时自动选择。谷歌网页导出自身包含可读的时间/地域元信息，但不可推测缺失的字段。

series 返回嵌套的 `metadata` 对象，以及 `points`、`peak`、`warnings`。point: `{date,start,end,value,qualifier,raw_value}`；start/end 是时间段的闭区间，value 为有限非负数或 null；qualifier 为 exact/below_threshold/missing。peak: `{status,value,periods}`；status 为 available/insufficient，periods 为 `{start,end}` 数组。仅精确且大于零、且不小于所有低量阈值上界的最大值可形成 available；未知缺失不补零，所有并列保留，低于阈值点不可作为精确值参与峰值，绘图不可假造此类点的数值。同日期相同值去重，冲突报 ValueError。metadata 范围过滤完全无交集的分箱，对部分交集分箱报错，不截断原始统计区间。

CSV 解析和 SVG 不读写运行记录；主 CLI 拷贝原始 CSV，赋予序列 T001 等编号并将 series 追加至调查记录。图表与峰值共同消费 points。

核心记录 `schema_version=1`，包含 run_id/term/meaning/aliases/created_at/updated_at/sessions/search_log/evidence/conclusions/trends。结论是版本列表，继续调查不覆盖前次版本。报告不使用网络工具的临时引用 ID，只使用真实 URL 和稳定证据编号。

## 预检与决定

| 任务 | 共享接口 | 决定 |
| --- | --- | --- |
| 趋势与报告 | series/points/peak | 按上述契约，报告不再次计算峰值 |
| 证据与报告 | evidence/conclusions | 只有可核验且对应含义的记录可用于最早结论 |
| Skill 与 CLI | CLI 帮助及 JSON 输入 | 文件输入避免 PowerShell 中文／引号转义问题 |
| 10 词试用 | 实际联网证据 | 区分有限试用与完整历史考证，保留无法确定的结果；人工验收由用户进行，先提供代理复核记录 |

## 验证记录

详见 [验证记录](validation.md)。独立审查发现的派生日期缓存、低量阈值、重复日期写法及分箱裁剪问题均有回归用例；未把十词首轮试用冒充穷尽考证或人工验收。
