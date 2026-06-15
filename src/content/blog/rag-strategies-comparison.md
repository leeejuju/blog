---
title: "RAG 策略对比：Basic、Graph、Grep、Structural"
description: "深入对比四种 RAG 策略——基础 HardChunk、Graph RAG、Grep RAG 与 Structural RAG，基于 Enterprise RAG Challenge 2 数据集，从检索质量、语义理解和工程代价等维度进行系统评估"
pubDate: 2025-12-22
updatedDate: 2026-05-01
---

选择合适的 RAG 策略对构建高质量的问答系统至关重要。本文基于 Enterprise RAG Challenge 2 的数据集，从检索质量、语义理解和工程代价等维度，对四种主流 RAG 方案进行了系统评估。

## 概述

RAG（检索增强生成）是目前解决 LLM 知识更新和幻觉问题的主流范式。然而，不同的 RAG 实现在检索质量、语义理解能力和工程复杂度上差异显著。本文基于 **Enterprise RAG Challenge 2**（ERC2）的真实企业年报数据集，系统对比了四种 RAG 策略：基础 HardChunk（Baseline）、Graph RAG、Grep RAG 和 Structural RAG。

### 评测数据集

数据集来源于 [Enterprise RAG Challenge 2](https://github.com/trustbit/enterprise-rag-challenge)（Round 2, Feb 2025），由 TimeToAct / Trustbit / IBM 主办。

- **7496 份公开年度报告 PDF**（约 46GB），含公司名称和文件 SHA1 哈希
- 竞赛日从中随机抽取 **100 份 PDF**，每份最长 **1000 页**
- 题目类型涵盖 `number`、`name`、`names`、`boolean` 四种

目标是在 ERC2 比赛数据集上达到 **80% 左右的准确度**。

---

## 策略一：基础 HardChunk（Baseline）

### 工作原理

HardChunk 是最原始的数据物理分块策略，纯粹根据文本内容从索引中硬切，不做任何语义分析：

1. **固定窗口切分**：严格按预设字符长度（如 `chunk_size=1000/1500`）进行切片
2. **固定重叠度**：设置固定重叠区间（如 `chunk_overlap=200/300`）以保留部分上下文
3. **无元数据注入**：不抽取公司名称、文档标题、页面索引等辅助语义信息
4. **忽略布局结构**：不考虑 PDF 中的表格、标题层级或段落完整性

### 核心发现

针对 5 份年报类复杂 PDF 的测试，HardChunk 方案暴露了以下严重问题：

#### 1. 检索范围错误
所有问题都召回到同一个文档 `e2b19d...e73`（CrossFirst Bank），无论问题实际问的是哪家公司。因为缺少公司名过滤，Milvus 全库向量检索优先匹配语义关键词而非目标公司文档。

#### 2. 语义混淆
在没有元数据注入的情况下，模型无法区分特定代称。例如当问题问 "Tradition"（指代 Tradition 公司）时，召回的内容可能只是包含 "tradition" 单词的通用描述。

#### 3. 余弦相似度偏低
Top 5 检索结果的 cosine similarity 普遍只有 **0.50 - 0.58**，属于弱相关。即使答案偶然正确（如 TSX_Y 的股票回购问题），本质上也是语义关键词碰巧匹配，而非真正的检索命中。

#### 4. 上下文断裂与混淆
固定字数切分会切断表格、分离指标名与数值、混淆高管履历与薪酬数据，导致 LLM 基于错误或不完整的上下文进行推理。

### 实验结论

> 单纯依赖固定大小的文本分块无法满足复杂金融年报的高质量问答需求。

HardChunk 仅作为基线（Baseline）参考，后续实验转向更高级的结构化方案。实验到此终止，不再进行 Precision / Recall 分析。

---

## 策略二：Structural RAG（Markdown 层级化拆分）

### 核心思路

Structural RAG 是本项目验证的核心策略，通过**结构化还原**来保留文档的语义上下文。核心流程如下：

1. **PDF 转 Markdown**：提取标题层级（H1-H4），完整还原表格结构，保留列表和段落的归属关系
2. **层级化切片（Hierarchical Splitting）**：
   - **大分块（Parent Chunk）**：保留完整章节内容，提供丰富上下文
   - **小分块（Child Chunk）**：细粒度语义点，用于高精度向量命中
3. **元数据注入**：在每个分块中显式注入公司名、章节标题、文档标识等元数据
4. **父子检索（Parent-Child Retrieval）**：命中 Child Chunk 时自动回溯其所属的 Parent Chunk

### 对比 HardChunk 的改进

在同样的 5 个测试问题上，Structural RAG 的表现：

| 问题 | HardChunk 结果 | Structural RAG 结果 | 关键改进 |
|------|---------------|-------------------|---------|
| Mercia 并购查询 | 错误回答 `true`（召回 CrossFirst 内容） | 回答 `false` ✓（chunk 标记不相关） | metadata 公司识别 |
| Tradition 营业利润率 | N/A（未召回） | **9.9%** ✓（BM25 命中第 44 页） | 关键词+向量互补 |
| TSX_Y 股票回购 | `true` ✓（但检索质量低） | `true` ✓（余弦 0.61） | 更高相似度 |
| CrossFirst 高管薪酬 | N/A | N/A ✓ | 正确排除 |
| Holley Inc. 并购 | `true`（基于错误公司信息） | 未测试 | — |

**最大改进**：
- Cosine similarity 从 **0.50-0.58 提升到 0.61-0.74**
- 不再是所有问题都召回到同一个错误文档
- Metadata 注入使 LLM 能够区分不同公司的内容

### 仍然存在的问题

1. **BM25 命中的零向量分块**：部分 BM25 命中的 chunk 向量相似度为 0，但仍被送入 LLM 并可能产生误导
2. **缺少相似度阈值过滤**（已修复）：新增了 `MIN_COSINE_SIMILARITY = 0.25` 的阈值
3. **父子回溯未完整实现**：缺少 `parent_id` 字段，真正的 Parent-Child 回溯需要进一步开发

### 下一步改进

- [ ] 实现 `extract_company` -> Milvus filter 的预过滤管线
- [ ] chunker 增加 `parent_id` 字段，实现真正父子回溯
- [ ] 区分 text 和 table 类型 chunk 的检索权重
- [ ] 跑 Recall / Precision 对比报告

---

## 策略三：Grep RAG

### 工作原理

Grep RAG 是 CC、Codex 等 Coding Agent 采用的检索方式，比较符合人类直觉：

1. 文档直接转换为 Markdown 格式
2. LLM 生成 Grep 命令或直接传关键字
3. 从文档中精确匹配目标内容，返回给 Agent

**核心特点**：无 embedding、无向量库、无语义检索。

### 适用场景

**适合**：
- 代码/配置/日志搜索——精确符号名、变量名、错误码，字面匹配就够了
- 快速原型验证
- 规则/条款/标准文档查询
- 单次/临时检索任务
- 文档量少（几百文档场景做 trade off）
- 模型足够强——用长上下文+强模型，模型能从碎片化匹配中拼出答案

**不适合**：
- 模糊语义查询
- 大规模知识库
- 跨语言检索（中文提问搜英文文档）
- 需要理解表格/图表内容的查询

### 核心逻辑

> 检索越弱，模型就得越强。

本质是把检索质量的压力转移给模型的理解能力。如果模型够强，这套性价比就很好；反之则效果差。额外一点：非常消耗 token 和上下文，感觉只适合 coding agent。

---

## 策略四：Graph RAG

Graph RAG 是一种基于知识图谱的 RAG 方案，通过构建实体关系图来增强检索能力。相较于向量检索的语义相似度匹配，Graph RAG 能够捕获实体之间的结构化关系，特别适合需要多跳推理的场景。

在本项目中，Graph RAG 作为备选方案在 `RAG-Challenge-2/graph-rag/` 目录下预留了位置，具体的实现和实验验证将在后续阶段进行。

---

## 四种策略对比总结

| 维度 | HardChunk | Structural RAG | Grep RAG | Graph RAG |
|------|-----------|---------------|---------|-----------|
| 检索方式 | 纯向量（全库） | 向量+BM25（RRF融合） | 关键词精确匹配 | 图结构+实体关系 |
| 语义理解 | 弱 | 中强 | 无（纯字面） | 强（关系推理） |
| 元数据支持 | 无 | 有（company_name等） | 依赖于文件名级 | 有（实体属性） |
| 余弦相似度 | 0.50-0.58 | 0.61-0.74 | N/A | N/A |
| 上下文完整性 | 差（硬截断） | 好（层级保留） | 好（全文扫描） | 好（图遍历） |
| 工程复杂度 | 低 | 中高 | 低 | 高 |
| Token 消耗 | 中 | 中 | 高 | 中 |
| 适合场景 | 快速验证 | 复杂长文档 | 精确检索/coding | 多跳推理 |
| 是否适合财报QA | 否 | 是 | 部分（精确值查询） | 待验证 |

---

## 核心经验总结

1. **向量检索必须辅以元数据过滤**：在年报问答等多文档场景中，直接全库检索会导致严重的张冠李戴。必须注入 `company`、`ticker`、`doc_id` 等 metadata。

2. **结构化保留是提升检索质量的关键**：将 PDF 转换为 Markdown 并保留标题层级，能使 embedding 质量从 0.5 提升到 0.7 以上。

3. **BM25 和向量检索互补**：精确关键词匹配（如 "operating margin"）可以弥补向量检索在某些细粒度查询上的不足，但需要相似度阈值来过滤噪音。

4. **Prompt 需要教会 LLM 使用检索信号**：单纯把 cosine_similarity 传给 LLM 是不够的，需要在 prompt 中明确说明如何使用这些信号来判断相关性。

5. **HardChunk 仅适合作为基线**：对于复杂长文档场景，必须采用结构化解析方案才能达到可用的检索质量。

## 参考资料

- [Enterprise RAG Challenge 2](https://github.com/trustbit/enterprise-rag-challenge) — 官方规则仓库
- [IlyaRice/RAG-Challenge-2](https://github.com/IlyaRice/RAG-Challenge-2) — 冠军方案（MIT License）
- [How I Won the Enterprise RAG Challenge](https://abdullin.com/ilya/how-to-build-best-rag/) — 冠军方案详解
- [ERC2 Leaderboards](https://www.timetoact-group.at/en/insights/erc3-leaderboards)
