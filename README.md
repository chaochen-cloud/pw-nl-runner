# pw-nl-runner — 自然语言 Playwright 用例批量执行器

从 Git 仓库读取**自然语言描述**的 playwright 用例（Markdown），让编码 agent（Claude Code / Copilot）逐个理解、翻译成 `playwright-cli` 命令执行，按期望结果判定 PASS/FAIL，并记录**完整命令审计日志**。

## 架构

```
用户一句话触发
   ↓
自定义 skill（.claude/skills/pw-nl-runner）——编排层：拉仓库、循环、翻译、断言、汇总
   ↓ 命令必须经过日志包装器
cases-repo/runner/pw-cli-log.py —— 记录每条命令到 logs/commands.jsonl
   ↓
playwright-cli（官方 skill 提供命令语法）——执行层
   ↓
logs/ 审计日志 → summarize.py → reports/run-<时间戳>.md 汇总报告
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
│   │   └── TC003.md                 # 自然语言用例：复用登录态发 POST
│   └── runner/
│       ├── pw-cli-log.py            # 【核心】命令日志包装器
│       └── summarize.py             # 日志 → 汇总报告
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

所有 playwright-cli 调用**必须**经过 `pw-cli-log.py`，SKILL.md 已强制此规则。计划命令使用 argv 数组，以原样传递含空格的定位器和文本：

```bash
python3 cases-repo/runner/pw-cli-log.py --case TC002 --nl '在待办输入框中输入 Buy groceries 并回车' --log-file logs/commands.jsonl -- \
  playwright-cli -s=tc002 fill "getByRole('textbox', { name: 'What needs to be done?' })" "Buy groceries"
```

计划 JSON 中的 `command` 是参数数组，例如：

```json
{"nl":"在待办输入框中输入 Buy groceries 并回车","command":["playwright-cli","-s=tc002","fill","getByRole('textbox', { name: 'What needs to be done?' })","Buy groceries"]}
```

`logs/commands.jsonl` 每个步骤一行，记录原始 `nl_step`、实际 `cmd` 参数数组、退出码和输出。每次运行结束后，runner 会调用 `summarize.py` 写出本次报告的 `report.md`：

```bash
python3 cases-repo/runner/run-all.py --config config.json
```

## 新增用例

在 `cases-repo/cases/` 下新建 `TC00N.md`，按 frontmatter + 三段式编写（见 `cases/TC001.md` 示例）：

- frontmatter：`id` / `title` / `priority` / `tags` / `session`（会话名，用于隔离）
- 前置条件：agent 判断是否满足
- 操作步骤：自然语言描述
- 期望结果：断言依据

## 注意事项

- **agent 是翻译器**：自然语言 → 命令的转换发生在执行时（LLM 理解），写用例零成本
- **元素定位**：先用 `snapshot` / `find` 探查正式会话中的真实页面语义；优先使用 role、label、text locator。快照 ref 是会话临时引用，不能跨会话写入计划复用
- **会话隔离**：每个用例独立 `-s=<session>`，避免状态串扰
- **失败即停**：任一步失败立即停止该用例，记录原因，继续下一个
