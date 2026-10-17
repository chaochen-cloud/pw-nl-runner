# 用例仓库

本仓库存放**自然语言描述**的 playwright 用例，按用例 ID 编号，供 `pw-nl-runner` skill 读取执行。

## 目录

```
cases/
├── TC001.md
├── TC002.md
└── TC003.md
```

## 用例编写规范

每个用例是一个 Markdown 文件，包含 YAML frontmatter + 三段式正文：

```markdown
---
id: TC001                  # 用例 ID，文件名必须与之一致
title: 登录成功后跳转首页    # 用例标题
priority: P1               # P1/P2/P3
tags: [smoke, login]       # 标签
session: tc001             # 浏览器会话名（隔离用，每个用例唯一）
---

## 前置条件
- agent 执行前需要确认的条件

## 操作步骤
1. 自然语言描述第一步
2. 自然语言描述第二步

## 期望结果
- 断言点一
- 断言点二
```

## 编写要点

- **用白话写**，不要写 playwright 命令——翻译由 agent 执行时完成
- 元素描述用用户看得懂的说法（"用户名输入框"、"登录按钮"），不要写 CSS 选择器
- 期望结果要**可验证**（URL、可见文本、元素状态、接口状态码等）
- 需要复用登录态时，在步骤里写清"保存登录态 / 加载登录态"，agent 会用 state-save/state-load 实现

## 初始化 Git

```bash
git init && git add -A && git commit -m "init cases"
git remote add origin <你的远端地址>
git push -u origin main
```
