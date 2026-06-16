---
title: "ECOM1: E-commerce Agent Challenge 解读"
description: "BitGN 电商智能体基准：覆盖购物、结账、退款、风控等业务域，评估 Agent 在真实业务约束下的工具调用和风险控制能力。"
pubDate: 2026-05-28
updatedDate: 2026-06-02
section: eval
---

ECOM1 (E-commerce Agent Challenge) 是 BitGN 推出的电商智能体评测基准，覆盖购物、结账、退款和风控等业务场景。本文将对该比赛的内容、业务范围和参与流程进行梳理。

ECOM1 是 BitGN Agent Challenge: E-commerce，对应 BitGN 电商智能体基准。比赛主题是让智能体在模拟电商运营环境中完成购物、结账、支付恢复、订单处理、售后支持、退款、配送调查、风控和商家运营等任务。

官方页面显示比赛日期为 2026-05-30。当前 `bitgn/ecom1-dev` 已作为开发基准开放，并有实时 DEV leaderboard；`bitgn/ecom1-prod` 是正式比赛隐藏任务集。

## 基本信息

| 项目 | 内容 |
| --- | --- |
| Challenge | BitGN Agent Challenge: E-commerce |
| Short name | ECOM1 |
| DEV benchmark | `bitgn/ecom1-dev` |
| PROD benchmark | `bitgn/ecom1-prod` |
| Competition date | 2026-05-30 |
| Lead partner | COLIBRIX ONE |
| Platform | BitGN |

## 主题范围

ECOM1 面向电商业务智能体，覆盖以下业务域：

- 商品目录、SKU、库存和仓库履约数据。
- 客户账户、偏好、购物车、订单、支付状态和客服 case。
- 商家政策，包括折扣、退货、退款、丢件、欺诈审查、支付恢复和客户沟通规则。
- 有副作用的业务操作，例如改购物车、应用优惠、完成 checkout、处理退款或升级客服流程。

重点是评估智能体在真实业务约束下的工具调用、状态跟踪、政策遵循和风险控制能力。

## 官方文档

| 文档 | 内容 |
| --- | --- |
| [Overview](https://github.com/bitgn/challenges/blob/main/ecom/01_overview.md) | ECOM1 总览、目标受众、比赛定位和环境说明 |
| [Participant Quickstart](https://github.com/bitgn/challenges/blob/main/ecom/02_participant_quickstart.md) | 注册、API key、开发基准、比赛运行路径 |
| [Competition Rules & Fair Play](https://github.com/bitgn/challenges/blob/main/ecom/03_competition_rules_fair_play.md) | 参赛规则、公平性要求和禁止行为 |
| [Scoring Penalties & Leaderboards](https://github.com/bitgn/challenges/blob/main/ecom/04_scoring_penalties_leaderboards.md) | 评分、惩罚、榜单和 Hall of Fame 规则 |
| [Trustworthiness Rubric](https://github.com/bitgn/challenges/blob/main/ecom/05_trustworthiness_rubric.md) | 电商场景下的可信行为标准 |
| [Host a Hub for ECOM1](https://github.com/bitgn/challenges/blob/main/ecom/06_hubs_program_guide.md) | 本地 hub 组织说明 |
| [Handbook](https://github.com/bitgn/challenges/blob/main/ecom/handbook.md) | 集中版参考手册 |

## Sample Agent

官方 Python 示例：

```text
https://github.com/bitgn/sample-agents/tree/main/ecom-py
```

示例运行前提：

- `BITGN_API_KEY`
- `OPENAI_API_KEY`，或替换为其他模型 provider
- Python/uv 本地运行环境

常用命令：

```bash
uv run python main.py
uv run python main.py t01
uv run python main.py t01 t04
```

默认 benchmark 为 `bitgn/ecom1-dev`，可通过 `BENCH_ID` 或 `BENCHMARK_ID` 覆盖。

## 开发关注点

- 先完成 `bitgn/ecom1-dev` 的端到端运行，再考虑正式任务。
- 工具调用必须遵守商家政策，尤其是折扣、退款、支付恢复、欺诈审查和客户隐私。
- 一次 run 内不允许人工干预；run 之间可以修改智能体和修复问题。
- 正式比赛期间隐藏任务反馈受限，DEV leaderboard 更适合日常调试。
- 需要记录工具调用、关键证据、状态变化和最终提交结果，便于复盘失败任务。

## 参考入口

- [ECOM1 Challenge Page](https://bitgn.com/challenge/ecom)
- [ECOM1 Documents](https://github.com/bitgn/challenges/tree/main/ecom)
- [ECOM Python Sample Agent](https://github.com/bitgn/sample-agents/tree/main/ecom-py)
