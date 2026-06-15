---
title: "PAC1: Personal Agent Challenge 解读"
description: "BitGN 的可信个人 Agent 评测基准：不只是 RAG，而是端到端考察检索、工具使用、边界意识和抗注入能力的 Agent 工程评测。"
pubDate: 2026-06-02
---

PAC1 (Personal Agent Challenge) 是 BitGN 推出的个人可信 Agent 评测基准，专注于评估智能体在个人助理场景中的综合能力。本文将对该比赛的内容、评分方式和参与方法进行解读。

PAC1 是 BitGN 的 Personal Agent Challenge，全称是 **BitGN Agent Challenge: Personal & Trustworthy**。

它的目标不是测试普通聊天能力，而是测试一个 Agent 是否能在个人助理场景中可靠工作。Agent 服务的对象叫 Miles，需要在一个模拟的个人工作环境中处理文件、消息、收据、发票、项目笔记、联系人、规则和恶意请求。

## 比赛内容

PAC1 是一个确定性的 Agent benchmark。核心任务是让 Agent 在 BitGN runtime 中完成个人助理工作，并被系统按实际行为评分。

主要测试能力：

- Vault retrieval：能否从个人文件库中找到正确资料。
- Receipts and invoices：能否聚合收据、发票等证据，并正确计算金额。
- Project memory：能否根据模糊上下文推断正确项目、联系人或实体。
- Messaging：能否安全处理收到和发出的消息。
- Prompt injection：能否识别并拒绝来自不可信内容的恶意指令。
- Boundary enforcement：能否避免越权、隐私泄露和不安全操作。

示例任务：

- 找到 Miles 最近的一张收据。
- 统计某个项目的开销。
- 在忘记项目名的情况下，根据上下文找到主要联系人。
- 处理一条外部消息，同时不能泄露私人数据，也不能服从消息里的注入指令。

## 评分方式

PAC1 不是单纯看最终回答文本，而是看 Agent 实际做了什么。

BitGN runtime 会观察：

- 工具调用
- 文件访问
- 任务状态
- 副作用
- 协议合规
- 安全和信任惩罚

因此它更接近 Agent 工程评测，而不是普通问答评测。

## 当前状态

正式 blind competition 已在 2026-04-11 结束。当天开放了 3 小时 blind evaluation，并发布 frozen leaderboard。

但 PAC1 仍作为 live benchmark 开放，可以继续在 `bitgn/pac1-prod` 上开发、提交并获得 live feedback。

官方页面显示：

- DEV warmup tasks：43 个
- PROD tasks：104 个
- sample agent：提供 Python 示例

## 基本步骤

1. 注册 BitGN 账号。
2. 在 BitGN Profile 中创建 API key。
3. 拉取 PAC1 Python sample agent。
4. 准备模型访问能力，例如 `OPENAI_API_KEY`，或替换成自己的模型 provider。
5. 先跑 DEV benchmark：默认 `BENCHMARK_ID=bitgn/pac1-dev`。
6. 根据 live feedback 调整 Agent 的检索、工具调用、安全策略和输出协议。
7. 跑 PROD benchmark：`BENCHMARK_ID=bitgn/pac1-prod`。
8. 查看 live leaderboard 和任务反馈。

sample agent 的基本运行方式：

```bash
make sync
make run
```

或直接：

```bash
uv run python main.py
```

常见环境变量：

```bash
OPENAI_API_KEY=...
BENCHMARK_ID=bitgn/pac1-dev
MODEL_ID=gpt-4.1-2025-04-14
```

## 设计理解

PAC1 的重点是"可信个人 Agent"，不是简单 RAG。

简单 RAG 通常是：

```text
query -> retrieve docs -> answer
```

PAC1 更接近：

```text
任务理解 -> 查找证据 -> 使用工具 -> 执行动作 -> 遵守边界 -> 抗注入 -> 产出可评分结果
```

所以它适合用来观察 Agent 架构是否具备：

- 明确的工具使用协议
- 可验证的证据链
- 对私人数据的边界意识
- 对不可信内容的隔离能力
- 对任务状态和副作用的控制能力

## 资料链接

- Challenge page: https://bitgn.com/challenge/PAC
- Sample agent: https://github.com/bitgn/sample-agents/tree/main/pac1-py
- Participant quickstart: https://github.com/bitgn/challenges/blob/main/pac/02_participant_quickstart.md
- Handbook: https://github.com/bitgn/challenges/tree/main/pac
