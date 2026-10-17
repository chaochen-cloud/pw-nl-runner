---
name: pw-nl-runner
description: 从指定Git仓库读取自然语言Markdown测试用例，翻译成结构化执行计划plans/TCxxx.json；调用run_all.py批量执行playwright-cli，每条步骤自动截图存入独立run报告目录/attachment，日志保存自然语言步骤与执行命令对应关系，自动生成报告。用户要求批量运行自然语言UI用例时启用。
---

# pw-nl-runner 自然语言测试用例批量执行器

## 输入参数
- git_repo: 用例Git仓库地址（本地路径/https/ssh）
- filter: 可选，用例过滤 TC001 / TC001-TC003 / all
- work_root: 工程根目录，固定为 `/Users/canvas/Downloads/pw-nl-runner`

## 执行流程
1. **拉取/更新用例仓库**
    - 本地不存在：git clone 到 `cases-repo`
    - 已存在：git pull 更新最新用例
2. **读取自然语言用例（cases/*.md）**
    解析frontmatter、前置条件、自然语言操作步骤、期望结果
3. **翻译生成执行计划plans**
    - 逐条把自然语言步骤翻译成playwright-cli命令，输出 `plans/TCxxx.json`
    - 必须对照playwright-cli官方skill确认命令语法
    - 元素定位规则：优先snapshot/find页面探查获取定位器，禁止硬猜选择器
4. **调用run_all.py批量执行**
    > 命令：`python3 cases-repo/runner/run_all.py --config config.json`
    - 自动新建 `reports/run-YYYYMMDD_HHMMSS/`，包含`attachment`文件夹
    - **每一条命令，无论成功失败，自动截图保存到本次run的attachment目录**
    - 审计日志 `logs/commands.jsonl` 保存【原始自然语言步骤 ↔ 真实执行命令】一一对应关系
    - 执行结束**自动调用summarize.py生成report.md**，不需要手动执行
5. **结果输出**
    - 汇总PASS/FAIL统计
    - 输出本次报告目录路径，markdown报告+截图附件全部在该目录内
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
