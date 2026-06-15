---
title: "Agent 记忆系统调研：Mem0、Zep、EverMemOS"
description: "调研多种 AI Agent 记忆系统方案，包括 Mem0、Zep 和 EverMemOS，分析它们在持久化记忆、混合检索和多 Agent 协等方面的架构设计与实践路径"
pubDate: 2025-12-22
updatedDate: 2026-03-31
---

## 概述

AI Agent 的长期记忆能力是构建可靠自主系统的关键基础设施。本文调研了当前主流的几个 Agent 记忆系统方案，包括 Mem0、Zep 和 EverMemOS，重点分析其架构设计、核心功能和适用场景。

---

## EverMemOS：类脑设计的记忆操作系统

EverMemOS 是由 EverMind-AI 开源的 **Memory OS**（记忆操作系统），为 AI Agent 提供持久化、可检索的长期记忆能力，同时优化 token 消耗。

### 四层架构（类脑设计）

| 层级 | 功能 | 类比脑区 |
|------|------|----------|
| Agentic Layer | 任务规划与执行 | 前额叶皮层 |
| Memory Layer | 长期存储与召回 | 皮层网络 |
| Index Layer | 关联检索、embedding、KV 搜索 | 海马体 |
| API/MCP Interface | 外部集成接口 | 感觉皮层 |

### 记忆生命周期

EverMemOS 定义了三个清晰的记忆处理阶段：

1. **Episodic Trace Formation（情景痕迹形成）** — 对话流转化为 MemCell（情景记忆单元），包含原子事实和前瞻信号
2. **Semantic Consolidation（语义巩固）** — MemCell 聚合为 MemScene（主题聚合），同时更新用户画像
3. **Reconstructive Recollection（重构回忆）** — 基于 MemScene 引导的上下文重组检索

### 核心能力

- 跨会话长期记忆持久化
- 混合检索（hybrid retrieval）：向量 + 关键词
- 支持群聊、批量操作、对话元数据控制
- LoCoMo 基准 **93% 准确率**，优于 Mem0 / Zep 等方案
- 提供 REST API，默认端口 `1995`

### 参考信息

- **仓库**: [EverMemOS](https://github.com/EverMind-AI/EverMemOS)（⭐ 3.5k）
- **论文**: [Memory Sparse Attention (MSA)](https://github.com/EverMind-AI/MSA) — 100M token 上下文框架
- **许可**: Apache-2.0

---

## Mem0

Mem0 是另一个流行的记忆层方案，专注于为 LLM 应用提供智能记忆管理。它支持跨会话记忆存储、自动提取关键信息和个性化用户体验。目前本仓库中 Mem0 相关的实践内容正在建设中。

## Zep

Zep 是一个长期记忆服务，为 AI Agent 应用提供持久化的对话记忆、实体提取和知识图谱构建能力。它支持自动总结历史对话、提取关键实体和关系，并提供了易于集成的 API 接口。目前本仓库中 Zep 相关的实践内容正在建设中。

---

## 方案对比

| 特性 | EverMemOS | Mem0 | Zep |
|------|-----------|------|-----|
| 架构层级 | 四层类脑设计 | 记忆存储层 | 记忆服务层 |
| 检索方式 | 混合检索（向量+关键词） | 向量检索 | 向量+知识图谱 |
| 基准性能 | LoCoMo 93% | — | — |
| 开源许可 | Apache-2.0 | — | — |
| 独特优势 | MemCell→MemScene 生命周期管理 | 轻量级集成 | 实体关系图谱 |

---

## 实践计划

后续工作包括：

1. 部署并运行 EverMemOS 服务
2. 实践记忆存储/检索 API 调用
3. 探索与 Agent 集成的记忆增强模式
4. 对比 Mem0、Zep 与 EverMemOS 在不同场景下的实际表现

## 状态

本模块处于 **开发中** 阶段，示例代码与实验内容将陆续补充。
