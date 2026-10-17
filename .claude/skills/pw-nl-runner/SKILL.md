---
name: pw-nl-runner
description: 从指定Git仓库读取自然语言Markdown测试用例，逐步观察当前页面、生成并立即执行下一条Playwright操作，自动记录日志、截图并生成报告。
---

# pw-nl-runner 自然语言 Playwright 用例执行器

## 输入参数
- `git_repo`：用例 Git 仓库地址（本地路径/https/ssh）
- `filter`：可选，用例过滤 `TC001` / `TC001-TC003` / `all`
- `work_root`：执行本 Skill 时的当前工作目录；开始时通过 `pwd` 获取并作为工程根目录

## 执行流程
1. **更新用例仓库**
   - 本地不存在：克隆到 `cases-repo`
   - 已存在：尝试 `git pull`；如仓库没有 remote，明确说明并使用本地用例
2. **确定用例顺序**
   - 按 filter 找到 `cases/TCxxx.md`，按用例 ID 排序
   - 每个用例使用独立浏览器 session；仅在用例明确要求时使用其他 session 或 storage state
3. **逐条用例、逐条命令地执行（强制）**
   - 读取当前用例 frontmatter、前置条件、操作步骤和期望结果。**不要预先生成整份 JSON 执行计划，也不要为尚未执行的步骤臆造定位器。**
   - 将当前自然语言步骤拆成需要的浏览器命令。在执行每个动作前，根据当前真实页面快照，只生成当前这一条命令并立即执行；若同一步需要多个命令，每条命令也依次执行，必要时重新观察页面。
   - 初始页面尚未打开时，可直接根据用例明确给出的 URL 生成首次 `open` 命令。此后，在生成下一条页面相关操作前，先在**同一个正式用例 session** 中运行 `snapshot`，读取 URL、页面内容和控件；再结合当前自然语言步骤生成并执行动作。
   - 观察命令使用 runner 的 live 模式，`--phase observe`；浏览器动作及断言使用 `--phase execute`。二者都要使用命令参数数组，并保持原始自然语言步骤不变：
     ```bash
     python3 runner/run-all.py --config config.json --case TCxxx \
       --live-step --title "用例标题" --session tcxxx \
       --nl "当前用例中的原始自然语言步骤" --phase observe \
       --command-json '["playwright-cli","-s=tcxxx","snapshot"]'
     ```
   - 首条 live 命令不传 `--run-dir`；记下输出的报告目录。当前用例及后续用例的每一条 live 命令都传相同的 `--run-dir reports/run-YYYYMMDD_HHMMSS`。每次输出中的页面结果是后续生成命令的事实依据。
   - runner 会拒绝连续的 `execute` 命令；每次页面操作后，下一条操作前必须先执行一次 `observe`。
   - 对每条期望结果，在实际操作到达相应页面后，先观察当前状态，再生成明确、可验证的断言命令；断言失败即停止当前用例，不继续臆测执行。
   - 页面快照里的临时 ref 只属于当前 session 和当前页面状态。页面变化后重新 snapshot；优先用实际页面支持的 role、label、text 等语义 locator。
   - 每条命令执行后检查 runner 输出和报告状态。命令失败时用例会被标为 `FAIL`，不要再追加该用例的操作；继续执行清单中的下一用例。
   - 当前用例所有操作和断言都成功后，显式完成用例：
     ```bash
     python3 runner/run-all.py --config config.json --case TCxxx \
       --finish-live --run-dir reports/run-YYYYMMDD_HHMMSS
     ```
   - 不调用 `--finish-live` 的用例会在报告中保留 `RUNNING`，不会被误报为通过。
   - 用例成功或失败结束时，runner 会自动关闭该用例使用过的所有 `playwright-cli` sessions，包括用例声明的主 session 和命令中显式指定的其他 session；不要手动复用这些 session。
4. **报告与审计**
   - runner 在每条观察/动作命令后更新同一报告目录中的 `report.json`、`report.md` 和 `report.html`。
   - 每条命令都自动尝试截图到 `attachment/`；截图命令是 optional，截图失败不改变用例结果。
   - `logs/commands.jsonl` 记录原始自然语言步骤、命令、阶段（observe/execute/screenshot/cleanup）、退出码和输出。
   - session 关闭动作也写入审计日志和报告；关闭失败将用例标为 FAIL 并显示错误。
   - Markdown 和 HTML 报告中，每个用例的步骤表下方都附有该用例源 Markdown 的原始内容。
   - `RUNNING`、`PASS` 和 `FAIL` 状态在报告中分别显示；单个用例失败不阻止后续用例。
5. **结果输出**
   - 汇总 PASS/FAIL/RUNNING 数量
   - 提供本次报告目录、Markdown/HTML 报告和附件目录
   - 简述失败用例和失败步骤

## 强制约束
1. 每个用例使用独立浏览器 session，状态隔离；不要把一个用例的登录态或页面状态带入另一个用例。
2. 严格按当前用例步骤执行，不可跳步或自行增加用户未要求的业务操作。
3. 每条动作必须基于当前页面实际快照；页面状态变化后不可复用旧快照中的临时 ref。
4. 对动态数据、导航和分支先观察真实页面结果，再生成后续命令。
5. 不绕过 CAPTCHA、安全验证、登录授权等站点保护；遇到此类页面按失败或阻塞记录。
