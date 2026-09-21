# 本地操作与数据格式

以下命令从项目根目录执行。PowerShell 可设置路径变量（没有修改系统环境）：

```powershell
$thScript = '.agents/skills/term-history/scripts/term_history.py'
python -X utf8 $thScript --help
python -X utf8 $thScript init '高松灯' --meaning '动漫角色“高松灯”的起源与最早公开记录；排除同名对象'
```

init 输出 JSON 中的 `path` 是调查文件绝对路径。后续把它设为 `$runPath`；下面的 JSON 文件由执行调查的 Agent 根据实际观察创建，不能原样当作真实证据。

```powershell
python -X utf8 $thScript status $runPath
python -X utf8 $thScript record $runPath --kind log --input logs.json
python -X utf8 $thScript record $runPath --kind evidence --input evidence.json
python -X utf8 $thScript record $runPath --kind conclusion --input conclusion.json
python -X utf8 $thScript finish $runPath --reason '本轮预算已达到，保留候选等待续查'
python -X utf8 $thScript render $runPath
python -X utf8 $thScript resume $runPath
```

JSON 使用 UTF-8，接受单个对象或非空对象数组；一批数据中有错误则整批不保存。错误退出码为2，成功输出结构化 JSON。工具不会自动进行搜索或证明来源真伪。

## 日志

```json
[
  {"kind":"search","query":"实际执行的查询","outcome":"实际返回情况"},
  {"kind":"page","url":"https://example.org/source","outcome":"原文不可访问，仅有搜索摘要"}
]
```

可提供实际 `accessed_at`，否则使用保存时刻。请及时保存，避免把事后补录时间误写成实时查询时间。每个新会话独立计预算，全部历史日志保留；状态达到上限仍可记录已经发生的访问、保存证据及结论。

## 证据

```json
{
  "url":"https://example.org/source",
  "title":"候选网页标题",
  "excerpt":"实际读取到的相关短句",
  "date":"2020-05",
  "date_kind":"published",
  "date_basis":"网页自报日期，旧版内容尚不能核实",
  "accessed_at":"2026-09-21T10:00:00+08:00",
  "meaning":"与调查含义相同的文本",
  "meaning_match":true,
  "status":"candidate",
  "kind":"original",
  "date_verified":false,
  "verification_note":"已打开原文；未找到同期版本，不能证明首发"
}
```

编号 E001 等由脚本分配。对原有候选的新核验追加一条记录，并在说明中关联旧编号，不手改已保存的历史。请读取 JSON 获取实际编号后再记录结论。

## 结论

```json
{
  "summary":"目前只有候选出处，最早可验证记录尚未确定。",
  "earliest_ids":[],
  "timeline":[
    {"date":"2020-05","text":"候选页面记录了相关用法，日期待核实","evidence_ids":["E001"]}
  ],
  "limitations":["部分原始网页已失效"],
  "unresolved":["查找候选页面的同期存档"]
}
```

省略 earliest_ids 时使用现有已核验记录计算可能最早集合；显式 [] 表示证据不足、不下结论。非空集合必须包含现有所有可能最早记录，不能只挑想要的一个。时间线每个节点至少关联一条词义匹配的证据，正文须说明候选或转述性质。首次结论 version=1，以后递增保留。

## 趋势

```powershell
python -X utf8 $thScript import-trends $runPath '趋势.csv' --format google --metadata metadata.json
python -X utf8 $thScript render $runPath
```

通用格式用 `--format generic`，内容是 `date,value` 两列。日／周日期用 YYYY-MM-DD，周日期表示该周起点；月度用 YYYY-MM。接受明确的日期区间。Google CSV 支持文件前言、BOM、中英日期表头。

```json
{
  "term":"高松灯",
  "source":"Google Trends",
  "source_url":"https://trends.google.com/trends/explore",
  "metric":"所选查询范围内的相对搜索兴趣（0—100）",
  "region":"全球",
  "start":"2020-01-01",
  "end":"2025-12-31",
  "granularity":"month"
}
```

必须按实际文件填写查询范围、地域、粒度；网址优先保留能重现查询的完整链接。多数值列时增加 `column`，精确写导出文件中的列名。记录系列内部使用 `metadata` 对象保存以上元信息，`points` 保存分箱和原始值，`peak` 保存最大值及所有并列区间。原始 CSV 按字节保留。

所有输出保存在该调查目录。完整位于指定范围外的分箱会被过滤；与范围部分相交的周／月分箱会报错，请把范围扩展到完整分箱或导出匹配范围的数据。不能保留整周数值却将日期缩短成几天。不同查询范围不重新归一化或拼接。导入与生成报告不改变原有证据或结论版本，不需要开启新会话。

低于阈值的记录不按精确数值绘图。若其阈值上界高于已观测的精确最大值，无法确认真正最大值所在区间，会返回数据不足；原始值和说明仍然保留。
