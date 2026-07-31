---
title: "How to Chunk File：RAG 中的文档切分策略"
description: "从文本切分到 OCR 视觉解析，梳理 RAG 文档切分的公认方法与选型参考"
pubDate: 2026-07-15
section: memory
---

# How to Chunk File：RAG 中的文档切分策略

## 问题定义

何为 chunk ,即对于文档的内容进行拆分

## 前置问题：文档本身长什么样

### 数字原生文档（Markdown、HTML、Code）

### 扫描件/图片 PDF（需要 OCR）

### 混合布局（表格 + 正文 + 图表）

## 路线一：文本层切分（Text-Based Splitting）

### 固定字符截断（Character Splitting）

### 递归字符切分（Recursive Character Splitting）

### 换行切分（Newline / Paragraph Splitting）

### 句子感知切分（Sentence-Aware Splitting）

## 路线二：结构感知切分（Structure-Aware Splitting）

### Markdown 标题切分（Markdown Header Splitting）

### AST 感知切分（Code / JSON）

### 语义切分（Semantic / Embedding Splitting）

## 路线三：OCR + 文档布局解析

### 布局分析（Layout Detection）

### OCR 文本提取

### 结构还原（Reading Order + 标题层级）

## 父子分层 chunking（Parent-Document Retrieval）

### 小 chunk 检索 + 大 chunk 生成

### 实现方式

## 切分参数：chunk_size 与 chunk_overlap

## 各方法分块效果对比（同文档不同切法）

## 方法对比与选型

## 参考
