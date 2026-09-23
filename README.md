# 深度溯源 · term-history

**中文简介：** 一个中文优先的 Codex Skill，用可追溯证据调查词条的早期出处、传播时间线和指定数据源的热度峰值。支持本地报告、继续调查，以及 Google Trends 和通用 CSV 导入。

**English overview:** A Chinese-first Codex skill for investigating the earliest verifiable records of terms, their spread over time, and observed popularity peaks within a specified data source and time range. It provides source-backed local reports, resumable investigations, and Google Trends or generic CSV imports.

## 开始使用

在 Codex 中打开本项目，使用：

```text
$term-history 调查动漫角色“高松灯”的起源，核对最早公开介绍和首次登场的出处。
```

Skill 位于 `.agents/skills/term-history/`。如果没有出现在技能选择器，重新打开项目或启动新会话；也可以明确要求 Codex 读取这个目录下的 SKILL.md 执行调查。当前会话必须具有联网搜索与网页读取能力；浏览器辅助可选。

本地辅助工具只需 Python 3.9 或以上，无 pip 依赖、API 密钥、数据库和服务器。它不自行调用大模型，调查使用现有 Codex 能力与额度。

```powershell
python -X utf8 .agents/skills/term-history/scripts/term_history.py --help
```

## 结果与继续调查

每次调查保存到 `runs/<run_id>/`：`investigation.json` 是完整记录，`report.md` 是可读报告，`trends/` 保存导入 CSV 和 SVG。`runs/` 已加入 Git 忽略列表。

- **最早已知记录**：只引用已核验、词义匹配的证据，保留日期精度；存档日期表示“至迟已存在”。
- **传播节点**：显示证据编号和核验状态；不会把转载说法自动升级为首发结论。
- **热度结果**：需要真实时间序列，分别注明平台、地域、范围和指标。没有数据时明确“数据不足”。
- **继续调查**：保留此前的证据、检索日志和结论版本。补充趋势数据不必重新调查出处。

```text
$term-history 继续 runs 中上次的“高松灯”调查。
$term-history 将我提供的 Google Trends CSV 加入这份调查报告。
```

默认每轮最多18条查询、24次页面访问和600秒软时间预算；工具等待可能超过时长目标。达到任一上限即整理结果，后续可以继续。该上限由 Skill 根据日志执行，脚本仍允许保存已发生的访问。

## 热度数据

支持 Google Trends 官方图表 CSV，以及带来源元信息的 `date,value` CSV。多词 Google CSV 要指定列名。详细命令和 JSON 示例见 [操作说明](.agents/skills/term-history/references/operations.md)。

不合并不同平台指数，不用搜索结果数量代替热度。零值、缺失和 `<1` 不混同；缺失不补零，周／月数据输出区间，所有并列峰值保留。查询边界必须完整包含周／月分箱，避免给整段数值错误缩短日期。没有完整数据时不承诺全网最火日期。

百度指数当前是否可以查看某词取决于实际账号和页面；本项目不依赖它的免费 API 或自动 CSV 导出。Google 网页 CSV 能否自动下载也取决于当前浏览器访问情况，可由用户手动补充。

## 示例

- [真实调查报告](examples/live-report.md) 展示有限检索、候选与续查；[合成趋势示例](examples/synthetic-run/report.md) 展示曲线和并列峰值，两者明确分开。
- 实际联网结果保存在本地 `runs/`，不会作为项目展示资料上传。

## 数据限制

本项目输出“截至本次检索找到的最早可验证记录”，不能证明已经检索全部互联网。中文词形、外文概念与网络新义分开考证；日期冲突、删帖、访问失败和引用链缺失都保留在报告中。证据字段校验不等于来源事实已经被程序独立认证。

首版没有公开网站、持续监控和图像／视频转录。Skill 与本地数据操作已经分离，后续可在保持记录格式的基础上封装插件。
