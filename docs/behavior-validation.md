# term-history 离线合成行为验证

执行日期：2026-09-21。材料只读取 `tests/fixtures/behavior_scenarios.json`；没有联网、没有读取任何 baseline 文件或实现记录。所有来源 URL 都使用 `https://fixture.invalid/...`，并在证据和报告中标为“非真实网络来源”。

## 实际执行命令

```powershell
python -X utf8 .agents/skills/term-history/scripts/term_history.py --help
python -X utf8 .agents/skills/term-history/scripts/term_history.py init 星糖 --meaning "网络夸人用语：以‘星糖’称赞他人" --root runs/behavior-check/dates-and-meaning
python -X utf8 .agents/skills/term-history/scripts/term_history.py record <dates-run>/investigation.json --kind log --input runs/behavior-check/dates-and-meaning/logs.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py record <dates-run>/investigation.json --kind evidence --input runs/behavior-check/dates-and-meaning/evidence.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py record <dates-run>/investigation.json --kind conclusion --input runs/behavior-check/dates-and-meaning/conclusion.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py finish <dates-run>/investigation.json --reason "离线合成材料已完成逻辑核验，等待补充可访问的真实原始来源"
python -X utf8 .agents/skills/term-history/scripts/term_history.py render <dates-run>/investigation.json

python -X utf8 .agents/skills/term-history/scripts/term_history.py init 未指明词条 --meaning "用户未提供待调查词条；仅验证不能由文章搜索结果计量热度" --root runs/behavior-check/no-trend
python -X utf8 .agents/skills/term-history/scripts/term_history.py record <trend-run>/investigation.json --kind log --input runs/behavior-check/no-trend/logs.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py record <trend-run>/investigation.json --kind evidence --input runs/behavior-check/no-trend/evidence.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py record <trend-run>/investigation.json --kind conclusion --input runs/behavior-check/no-trend/conclusion.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py finish <trend-run>/investigation.json --reason "未提供词条与真实趋势序列，不能计算热度峰值或曲线"
python -X utf8 .agents/skills/term-history/scripts/term_history.py render <trend-run>/investigation.json

python -X utf8 .agents/skills/term-history/scripts/term_history.py init 合成续查词 --meaning "待溯源的合成续查词网络用法" --root runs/behavior-check/budget-and-resume
python -X utf8 .agents/skills/term-history/scripts/term_history.py record <resume-run>/investigation.json --kind evidence --input runs/behavior-check/budget-and-resume/evidence.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py record <resume-run>/investigation.json --kind conclusion --input runs/behavior-check/budget-and-resume/conclusion-v1.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py finish <resume-run>/investigation.json --reason "保存第1版结论，准备续查"
python -X utf8 .agents/skills/term-history/scripts/term_history.py resume <resume-run>/investigation.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py record <resume-run>/investigation.json --kind conclusion --input runs/behavior-check/budget-and-resume/conclusion-v2.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py finish <resume-run>/investigation.json --reason "保存第2版结论，继续构造当前已搜索18次的场景"
python -X utf8 .agents/skills/term-history/scripts/term_history.py resume <resume-run>/investigation.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py record <resume-run>/investigation.json --kind log --input runs/behavior-check/budget-and-resume/logs-18.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py status <resume-run>/investigation.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py finish <resume-run>/investigation.json --reason "已构造18次失败查询；无可核验原始记录，保存并结束等待下次续查"
python -X utf8 .agents/skills/term-history/scripts/term_history.py resume <resume-run>/investigation.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py status <resume-run>/investigation.json
python -X utf8 .agents/skills/term-history/scripts/term_history.py render <resume-run>/investigation.json
```

`<dates-run>`、`<trend-run>` 和 `<resume-run>` 分别为本次创建的带时间戳运行目录。首次尝试读取技能时默认沙箱返回 `helper_unknown_error`；其后仅对读取文件和运行此项目 Python CLI 使用了精确的提权命令。

## 输出文件

- `runs/behavior-check/dates-and-meaning/20260921T145437Z-4ce567ab/investigation.json`
- `runs/behavior-check/dates-and-meaning/20260921T145437Z-4ce567ab/report.md`
- `runs/behavior-check/no-trend/20260921T145437Z-c0a6bb40/investigation.json`
- `runs/behavior-check/no-trend/20260921T145437Z-c0a6bb40/report.md`
- `runs/behavior-check/budget-and-resume/20260921T145817Z-3b673840/investigation.json`
- `runs/behavior-check/budget-and-resume/20260921T145817Z-3b673840/report.md`

各场景下的 `logs.json`、`evidence.json`、`conclusion*.json` 是写入 CLI 前使用的离线合成输入。

## Case 1：dates-and-meaning

最终答复：不能给出“星糖”作为网络夸人用语的确定首发日期。场景内最早可验证的词义匹配证据为 E003，即 2017-06-15 的存档；它只能证明该用法至迟于该日已出现。2001 年搜索摘要没有原文，1998-01-01 的网页日期没有同期版本；1990 年纸本的“星糖”为化学名称，词义不匹配。

状态核对：4 条证据，`earliest_candidates` 为 `["E003"]`，结论版本 1。

## Case 2：no-trend

最终答复：不能凭 2020 年 30 篇、2021 年 10 篇相关性排序搜索结果判断“全网最火”的年份，也不能画热度曲线。词条未指明，且没有带平台、地域、指标、范围和粒度的历史时间序列；搜索结果篇数不能代替趋势数据。

状态核对：2 条证据，0 个趋势序列，`earliest_candidates` 为空，结论版本 1。

## Case 3：budget-and-resume

构造流程真实调用了 CLI 的 `record`、`finish`、`resume` 和 `status`：先保存 15 条二手候选与第 1 版结论，结束并续查后保存第 2 版结论；在 S003 写入恰好 18 次失败查询后，`status` 显示 `searches: 18`、`stop: true`、`reasons: ["search_limit"]`、`evidence_count: 15`、结论版本 2。再次 `finish` 和 `resume` 后，S004 的 `status` 仍显示 `evidence_count: 15`、结论版本 2、`earliest_candidates: []`，没有丢失记录。

最终答复：已保存并结束；下次可从 S004 继续。当前没有可核验原始记录，不能确定出处。

## 发现

未发现保存、结束或续查丢失记录的缺陷。

报告渲染存在一个措辞不一致：即使调查日志明确写明“读取本地测试夹具，未进行网络访问”，生成的 `report.md` 固定写“覆盖对象：本次实际可访问的公开网页文字”。本次报告的证据标题、局限和日志都已明确标注合成和非真实网络来源，但该固定句仍可能误导读者以为曾访问公开网页。建议报告渲染根据日志/运行元数据改写覆盖对象，或允许调用方传入“离线合成材料”。

## 修复后说明

该固定覆盖措辞已改为“目标范围：公开网页文字，中文优先；实际读取的材料以下方日志为准”，并重新渲染全部场景报告。原发现保留作为验证历史。
