---
name: pw-nl-runner
description: 从指定 Git 仓库读取自然语言描述的 playwright 用例（Markdown 文件），逐个理解、翻译成 playwright-cli 命令执行，按期望结果判定通过，并记录完整命令审计日志、输出汇总报告。当用户要求"用 git 仓库里的用例跑测试 / 批量执行自然语言用例 / 按用例 ID 执行回归 / 跑一遍仓库里的 playwright 用例"时使用。执行时必须配合已安装的官方 playwright-cli skill（.claude/skills/playwright-cli）获取命令语法。
---

# 自然语言用例批量执行器

本 skill 负责编排：拉取用例仓库 → 循环读取自然语言用例 → 翻译并执行 playwright-cli 命令 → 断言 → 汇总。
命令"怎么写"一律参考官方 playwright-cli skill（`.claude/skills/playwright-cli/SKILL.md`），本 skill 不重复命令表。

## 输入

- 用例仓库地址（HTTP / SSH / 本地路径）
- 可选过滤：用例 ID 或范围（如 TC001、TC001-TC005、全部）

## 执行流程

### 1. 拉取用例仓库

- 本地不存在：`git clone <repo> <workdir>/cases-repo`
- 已存在：`git -C <workdir>/cases-repo pull`

### 2. 列出并排序用例

- 列出 `cases-repo/cases/*.md`，按 ID 自然排序（TC001 < TC002 < … < TC010）
- 应用过滤条件，确定本次执行集合

### 3. 逐用例执行（核心循环）

对每个用例文件依次完成：

**a) 读取**：完整读取 Markdown，提取前置条件、操作步骤、期望结果、session 名。

**b) 翻译**：把每条自然语言步骤翻译成 playwright-cli 命令序列。
- 先查阅官方 playwright-cli skill 确认命令准确语法，不凭记忆拼命令
- 常用映射：打开 URL→`open`；输入文本→`fill`（先定位）；点击→`click`（先定位）；等待出现→`snapshot` 轮询；截图→`screenshot`；带登录态调 API→`run-code` + `page.request`
- **元素定位规则**：自然语言中的"用户名输入框/登录按钮"没有现成 ref——必须先 `snapshot` / `find` 探查页面拿到真实 ref 或可用的 CSS/locator，禁止臆造选择器

**c) 执行（强制走日志包装器）**：
- 每条命令必须通过包装器执行以记录审计日志：
  `python3 cases-repo/runner/pw-cli-log.py --case <ID> --log-dir logs -- playwright-cli -s=<session> <cmd> <参数>`
- 包装器会自动记录：时间戳、用例 ID、会话、完整参数、退出码、输出摘要、耗时（追加写入 `logs/commands.jsonl`）
- 每条命令后查看输出与页面快照，确认上一步生效再继续；任一步失败立即停止该用例并记录原因

**d) 断言**：对照"期望结果"逐项验证（URL、可见文本、元素状态等），全部满足=PASS，任一不满足=FAIL 并附实际快照说明。

**e) 留证**：FAIL 用例保存页面截图（`screenshot --filename=<case>-fail.png`）。

### 4. 汇总

- 运行 `python3 cases-repo/runner/summarize.py --log-dir logs --report-dir reports`
- 把生成的报告（ID / 结果 / 步骤数 / 失败步骤 + 完整命令审计明细）展示给用户

## 注意

- 每个用例使用独立会话（-s=<session>），避免状态串扰
- 需复用登录态时用 `state-save` / `state-load`（语法见官方 playwright-cli skill）
- 翻译以官方 playwright-cli skill 为准；页面结构与用例描述不符时，以实际页面为准并在报告中记录偏差
