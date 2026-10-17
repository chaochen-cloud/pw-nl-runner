# pw-nl-runner — 自然语言 Playwright 用例批量执行器

从 Git 仓库读取**自然语言描述**的 playwright 用例（Markdown），让编码 agent（Claude Code / Copilot）逐个理解、翻译成 `playwright-cli` 命令执行，按期望结果判定 PASS/FAIL，并记录**完整命令审计日志**。

## 架构

```
用户一句话触发
   ↓
自定义 skill（.claude/skills/pw-nl-runner）——逐步观察当前页面、生成并执行下一条命令
   ↓
cases-repo/runner/run-all.py —— live-step 执行、逐命令截图、报告增量更新
   ↓
pw-cli-log.py —— 记录命令和阶段 → summarize.py → reports/run-<时间戳>/{report.md,report.html}
```

## 目录结构

```
pw-nl-runner/
├── README.md                        # 本文件
├── .claude/skills/pw-nl-runner/
│   └── SKILL.md                     # 自定义 skill（复制到 ~/.claude/skills/ 或项目 .claude/skills/）
├── cases-repo/                      # 用例仓库（可独立 git init 推送）
│   ├── cases/
│   │   ├── TC001.md                 # 自然语言用例：登录
│   │   ├── TC002.md                 # 自然语言用例：TodoMVC
│   │   ├── TC003.md                 # 自然语言用例：复用登录态发 POST
│   │   └── TC004.md                 # 自然语言用例：TodoMVC 后搜索百度
│   └── runner/
│       ├── run-all.py               # 静态计划兼容执行和 live-step 执行入口
│       ├── pw-cli-log.py            # 命令日志包装器
│       └── summarize.py             # 增量报告生成
├── logs/                            # 命令审计日志（运行后生成，建议 gitignore）
└── reports/                         # 汇总报告（运行后生成，建议 gitignore）
```

## 快速开始

```bash
# 1. 安装 playwright-cli（全局）
npm install -g @playwright/cli@latest

# 2. 安装官方 playwright-cli skill（命令语法来源）
playwright-cli install --skills

# 3. 安装本自定义 skill
mkdir -p ~/.claude/skills && cp -r .claude/skills/pw-nl-runner ~/.claude/skills/

# 4. 把用例仓库初始化为 git 仓库（可选，推送到远端即可被 skill 拉取）
cd cases-repo && git init && git add -A && git commit -m "init cases"
```

## 使用

在 Claude Code 中触发：

```
用 pw-nl-runner 跑 https://github.com/your-org/cases-repo 的全部用例，
结束后给我 PASS/FAIL 汇总和命令审计日志。
```

指定范围：

```
用 pw-nl-runner 跑 <本地路径>/cases-repo，只跑 TC001 和 TC002。
```

## 命令日志机制（核心）

所有 playwright-cli 调用**必须**经过 `pw-cli-log.py`。推荐 live-step 模式：执行每条操作前先在当前 session 获取 snapshot，根据真实页面状态只生成下一条命令并立即执行，不创建整份预生成计划。观察命令也会进入同一报告和审计日志：

```bash
python3 cases-repo/runner/run-all.py --config config.json --case TC002 \
  --live-step --title "添加两条待办并勾选第一条" --session tc002 \
  --nl '在待办输入框中输入 Buy groceries 并回车' --phase observe \
  --command-json '["playwright-cli","-s=tc002","snapshot"]'
```

根据 snapshot 生成并立即执行下一条动作。首条 live-step 自动创建报告目录；后续命令传相同的 `--run-dir`：

```bash
python3 cases-repo/runner/run-all.py --config config.json --case TC002 \
  --live-step --title "添加两条待办并勾选第一条" --session tc002 \
  --nl '在待办输入框中输入 Buy groceries 并回车' --phase execute \
  --command-json '["playwright-cli","-s=tc002","fill","getByRole('\''textbox'\'', { name: '\''What needs to be done?'\'' })","Buy groceries","--submit"]' \
  --run-dir reports/run-YYYYMMDD_HHMMSS
```

最后一条操作和断言通过后显式完成用例。失败步骤会自动将用例标为 FAIL，不可再追加步骤；未完成的用例保留 RUNNING 状态：

```bash
python3 cases-repo/runner/run-all.py --config config.json --case TC002 \
  --finish-live --run-dir reports/run-YYYYMMDD_HHMMSS
```

`logs/commands.jsonl` 每个命令一行，记录原始 `nl_step`、命令参数数组、observe/execute/cleanup 阶段、退出码和输出。每条浏览器命令执行后都会尝试截图并刷新 Markdown/HTML 报告。HTML 报告中的截图以小图显示，点击可放大；原始图片保存在 `attachment/`。
runner 会要求页面动作之间至少有一次 `--phase observe`，避免在没有新页面依据时连续生成操作。
每个用例成功或失败结束时，runner 会关闭该用例实际使用的所有浏览器 session（包括多个 session 的用例），并把关闭结果写入日志和报告；关闭失败会将该用例标记为 FAIL。
每个用例的执行步骤表下方会附上原始 Markdown 用例内容，便于在报告中同时查看需求与执行结果。

兼容性：旧的 `plans/TCxxx.json` 静态计划仍可通过 `run-all.py --case TCxxx` 执行；新流程不再依赖预生成计划。按 `all` 运行时，每个用例都在前一个用例完成后才开始，并将所有结果追加到同一报告目录。

## 新增用例

在 `cases-repo/cases/` 下新建 `TC00N.md`，按 frontmatter + 三段式编写（见 `cases/TC001.md` 示例）：

- frontmatter：`id` / `title` / `priority` / `tags` / `session`（会话名，用于隔离）
- 前置条件：agent 判断是否满足
- 操作步骤：自然语言描述
- 期望结果：断言依据

## 注意事项

- **当前状态驱动**：自然语言 → 单条命令的转换发生在每步执行时；下一条命令只能依据前一步之后的页面状态生成
- **元素定位**：先用 `snapshot` / `find` 探查正式会话中的真实页面语义；优先使用 role、label、text locator。页面变化后重新观察，不复用旧快照 ref
- **会话隔离**：每个用例独立 `-s=<session>`，避免状态串扰
- **失败即停**：任一步失败立即停止该用例，记录原因，继续下一个用例；未显式完成的用例不会被报告为 PASS
- **站点防护**：遇到 CAPTCHA 或安全验证时如实记录，不尝试绕过
