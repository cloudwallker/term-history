# 示例

[真实报告](live-report.md) 来自“显眼包”的有限公开网页调查，展示原始版面、较早候选和续查后的结论。这里只保留短摘录和公开来源链接，没有账号、Cookie、本地用户名或私人文件路径。它是一次调查快照，不是该词已经考证完毕的词源定论。

[趋势示例](synthetic-run/report.md) 完全使用合成数据，演示并列峰值、缺失值和 `<1`；数值没有真实统计意义。

趋势原文件为 [trend-demo.csv](trend-demo.csv)，元数据为 [trend-metadata.json](trend-metadata.json)。可初始化词条“示例词（合成数据）”后，通过 `import-trends --format generic --metadata examples/trend-metadata.json` 导入 CSV。完整参数见项目 README 和技能操作文档。

实际私人调查保存在项目 `runs/`，默认不纳入 Git。这里的示例可以随项目一起分享。
