---
title: "论文笔记：Is Graph All You Need?"
description: "基于图的 IR 检索 vs Grep vs 向量 RAG，在 Agent Search 场景下的效果对比，以及 Chronos 框架的设计思路。"
pubDate: 2026-05-31
---

基于图结构的检索方式在 Agent 系统中是否真的优于传统向量检索？本文记录了一篇相关论文的阅读笔记，探讨基于图的 IR 检索与 Grep、向量 RAG 在 Agent Search 场景下的效果对比。

之前做 RAG 的时候，看到一篇名为《Is Graph All You Need? How Graph-based Information Retrieval Reshapes Agent Search》的论文，就顺便看了一下。

论文中提出了一个很有意思的观点，研究了在代理搜索场景下，直接用Grep检索与使用向量 RAG 方式的对比。作者使用了一个名为 LongMemEval 的评估框架（包含 LongBench 和 Claude-Harness 等测试集）进行检索发现：

1. 在绝大多数情况下，基于 Grep 的方式往往能取得比传统向量 RAG 更好的效果
2. 然后，他自己构建了一个名为 Chronos 的框架。同时，他在上下文里边加入了一些噪声，然后去验证这个结果。通过对比，他发现了一个问题：即使在底层对话数据完全相同的情况下，最终整体效果依然非常依赖于所使用的 Agent 工具。
