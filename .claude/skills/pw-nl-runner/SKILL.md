---
name: pw-nl-runner
description: 从指定Git仓库读取自然语言Markdown测试用例，翻译成结构化执行计划plans/TCxxx.json；调用run_all.py批量执行playwright-cli，每条步骤自动截图存入独立run报告目录/attachment，日志保存自然语言步骤与执行命令对应关系，自动生成报告。用户要求批量运行自然语言UI用例时启用。
---

# pw-nl-runner 自然语言测试用例批量执行器

## 输入参数
- git_repo: 用例Git仓库地址（本地路径/https/ssh）
- filter: 可选，用例过滤 TC001 / TC001-TC003 / all
- work_root: 执行本 Skill 时的当前工作目录；开始时通过 `pwd` 获取并作为工程根目录，后续路径均相对该目录解析

## 执行流程
1. **拉取/更新用例仓库**
    - 本地不存在：git clone 到 `cases-repo`
    - 已存在：git pull 更新最新用例
2. **确定要执行的用例**
    - 按 `filter` 找到对应的 `cases/TCxxx.md`
    - 按用例 ID 排序形成本次待运行清单
3. **逐用例生成并执行计划**
    - 对清单中的每个用例，依次解析其frontmatter、前置条件、自然语言步骤和期望结果；只生成当前用例的 `plans/TCxxx.json`，并立即执行，完成后才开始翻译下一条用例。禁止先为全部用例生成计划再批量执行
    - 单用例：`python3 cases-repo/runner/run-all.py --config config.json --case TCxxx`
    - 多用例/all：第一条计划执行时不传 `--run-dir`，记录 runner 输出的报告目录；后续每条计划执行时传入该目录，追加到同一份报告：`python3 cases-repo/runner/run-all.py --config config.json --case TCyyy --run-dir reports/run-YYYYMMDD_HHMMSS`
    - 每次 runner 调用必须显式指定当前 `--case`，避免 plans 目录中的旧计划导致额外用例被执行；每条用例失败后也继续处理清单中的下一条
    - 每个计划步骤翻译成playwright-cli命令，必须对照官方skill确认语法
    - 计划中的命令使用参数数组，避免空格、引号被拆坏；runner保留自然语言步骤与实际命令的对应关系
    - 元素定位优先使用有实际页面依据的语义 locator（role、label、text）；先在该用例的正式浏览器会话中 snapshot/find 探查页面，不要臆造定位器
    - snapshot ref（如 `e8`）是会话内临时引用，禁止从探查会话复制到计划供另一会话复用；仅在同一会话内即时探查和操作时使用
4. **收尾并汇总整批结果**
    - 每个用例执行完，报告及截图会追加到同一个 `reports/run-YYYYMMDD_HHMMSS/` 目录；runner自动刷新`report.json`、`report.md`和`report.html`
    - 自动新建 `reports/run-YYYYMMDD_HHMMSS/`，包含`attachment`文件夹
    - **每一条命令，无论成功失败，自动截图保存到本次run的attachment目录**
    - 审计日志 `logs/commands.jsonl` 保存【原始自然语言步骤 ↔ 真实执行命令】一一对应关系
    - 执行结束**自动调用summarize.py生成report.md和report.html**，不需要手动执行
5. **结果输出**
    - 汇总PASS/FAIL统计
    - 输出本次报告目录路径，Markdown/HTML报告+截图附件全部在该目录内
    - 失败用例保留所有步骤截图用于排查

## 强制约束
1. 每个用例使用独立浏览器session，状态隔离；如需复用登录态，使用storage-state保存/加载
2. 截图命令标记为optional：截图失败不判定用例失败，仅留证据
3. 日志必须记录nl_step（原始自然语言文本）与执行cmd，保持一一对应
4. 禁止修改plans目录以外的业务代码；产物只写入logs/、reports/目录
5. 翻译阶段如页面元素描述模糊，优先执行snapshot探查页面，不要臆造定位器

## 返回给用户的内容
- 用例执行汇总表
- 报告文件夹完整路径
- 失败用例简要原因
