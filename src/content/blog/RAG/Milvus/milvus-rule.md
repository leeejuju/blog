---
title: "Milvus 向量库理解：字段、索引、检索规则与排序因子"
description: "梳理 Milvus 中字段类型、索引类型、相似度度量、检索规则、重排序方法与关键参数，区分 VARCHAR、FLOAT_VECTOR、BM25、IVF、RRF 等概念"
pubDate: 2025-12-22
updatedDate: 2026-06-26
section: rag
---

这篇主要整理这些概念的分层，后续再结合实际检索结果测试它们对 RAG 召回质量的影响。

样本，财经+医疗+教材

## 设立的文档字段


| 字段 | 类型 | 说明 |
|------|------|------|
| `id` / `chunk_id` | `INT64` 或 `VARCHAR` | 主键 |
| `doc_id` | `VARCHAR` | 文档 ID |
| `text` | `VARCHAR` | chunk 原文 |
| `title` | `VARCHAR` | 文档标题 |
| `section` / `section_path` | `VARCHAR` | 章节路径 |
| `page` | `INT64` | 页码 |
| `embedding` | `FLOAT_VECTOR` | dense embedding |
| `sparse` | `SPARSE_FLOAT_VECTOR` | BM25 sparse vector |
| `metadata` | `JSON` | 来源、标签、额外信息 |

## 主要内容

### 1. 字段与字段类型

Milvus 的 collection schema 由字段组成，每个字段都有自己的数据类型。

字段类型：

| 类型 | 作用 | RAG 中常见用途 |
|------|------|----------------|
| `INT64` | 整数字段 | 主键、页码、时间戳 |
| `VARCHAR` | 字符串字段 | 原文、标题、文档 ID、章节名 |
| `FLOAT` / `DOUBLE` | 数值字段 | 业务分数、置信度、价格等 |
| `BOOL` | 布尔字段 | 状态标记 |
| `JSON` | 半结构化字段 | metadata |
| `ARRAY` | 数组字段 | 标签、分类、多个属性 |
| `FLOAT_VECTOR` | 稠密向量字段 | embedding 语义检索 |
| `SPARSE_FLOAT_VECTOR` | 稀疏向量字段 | BM25 / sparse 检索 |


### 2. 索引类型

索引用来加速检索，不等于排序字段。

常见向量索引：

| 索引 | 适用字段 | 说明 |
|------|----------|------|
| `FLAT` | `FLOAT_VECTOR` | 暴力精确搜索，准确但慢 |
| `IVF_FLAT` | `FLOAT_VECTOR` | 聚类分桶后搜索，常见 ANN 索引 |
| `IVF_SQ8` | `FLOAT_VECTOR` | IVF + 量化压缩 |
| `IVF_PQ` | `FLOAT_VECTOR` | IVF + PQ 压缩 |
| `HNSW` | `FLOAT_VECTOR` | 图索引，常用于高召回低延迟 |
| `DISKANN` | `FLOAT_VECTOR` | 面向更大规模数据 |
| `SPARSE_INVERTED_INDEX` | `SPARSE_FLOAT_VECTOR` | sparse / BM25 检索 |

需要重点区分：

```text
IVF_FLAT 是索引类型
COSINE / IP / L2 是相似度 metric
BM25 是 sparse 文本相关性打分
```

### 3. 检索规则与相似度度量

Milvus 搜索结果通常按 score 或 distance 返回 Top K。

常见 metric：

| metric | 适用字段 | 排序含义 |
|--------|----------|----------|
| `COSINE` | `FLOAT_VECTOR` | 余弦相似度，越相似越靠前 |
| `IP` | `FLOAT_VECTOR` / `SPARSE_FLOAT_VECTOR` | inner product，越大越靠前 |
| `L2` | `FLOAT_VECTOR` | 欧氏距离，越小越靠前 |
| `BM25` | `SPARSE_FLOAT_VECTOR` | 文本相关性，越高越靠前 |

RAG 中常见检索方式：

| 检索方式 | 使用字段 | 适合场景 |
|----------|----------|----------|
| Dense Search | `FLOAT_VECTOR` | 语义相似、问法改写、概念理解 |
| Sparse / BM25 Search | `SPARSE_FLOAT_VECTOR` | 关键词、术语、公司名、编号、表格指标 |
| Hybrid Search | dense + sparse | 同时兼顾语义和关键词 |
| Scalar Filter | 标量字段 | 按文档、时间、分类、权限过滤 |

### 4. 排序与重排序方法

Milvus 里的排序可以分为几类。

| 类型 | 例子 | 说明 |
|------|------|------|
| 向量相似度排序 | `COSINE`, `IP`, `L2` | 单路向量检索默认排序 |
| BM25 相关性排序 | `BM25` | 全文/sparse 检索排序 |
| 标量字段排序 | `created_at`, `page`, `rating` | 按 schema 里的普通字段排序 |
| 多路结果重排 | `WeightedRanker`, `RRFRanker` | hybrid search 后融合结果 |
| 应用层排序 | 自定义 score | 在业务代码里二次排序 |

常见重排方法：

| 方法 | 作用 |
|------|------|
| `WeightedRanker` | 给 dense、BM25 等多路结果分配权重后融合 |
| `RRFRanker` | Reciprocal Rank Fusion，按各路结果排名位置融合 |

区别：

```text
WeightedRanker 看分数和权重
RRFRanker 看排名位置
```

### 5. 关键因子与参数

后续测试时可以重点观察这些参数对召回和排序的影响。

#### Dense 向量索引参数

| 参数 | 常见于 | 作用 |
|------|--------|------|
| `nlist` | `IVF_FLAT` / `IVF_SQ8` / `IVF_PQ` | 建索引时分多少个聚类桶 |
| `nprobe` | IVF 查询 | 查询时搜索多少个桶 |
| `M` | `HNSW` | 图中每个节点的连接数量 |
| `efConstruction` | `HNSW` | 建图质量与建索引成本 |
| `ef` | `HNSW` 查询 | 查询时搜索候选范围 |

#### BM25 参数

| 参数 | 作用 |
|------|------|
| `bm25_k1` | 控制词频饱和程度 |
| `bm25_b` | 控制文档长度归一化强度 |
| `TF` | 词在当前文档/chunk 中出现频率 |
| `IDF` | 词在全库中的稀有程度 |

#### Hybrid / Rerank 参数

| 参数 | 常见于 | 作用 |
|------|--------|------|
| `weights` | `WeightedRanker` | 控制多路检索分数占比 |
| `norm_score` | `WeightedRanker` | 是否归一化不同路径分数 |
| `k` | `RRFRanker` | RRF 排名融合的平滑参数 |
| `limit` | search | 最终返回 Top K |
| `filter` | search/query | 标量过滤条件 |



## 测试方向

