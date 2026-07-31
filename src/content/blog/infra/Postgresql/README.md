---
title: "PostgreSQL：SQL 核心知识复习"
description: "PostgreSQL 环境下的 SQL 基础知识回顾：查询、连接、聚合、子查询、索引、事务与常见性能优化"
pubDate: 2026-07-21
section: infra
---

# PostgreSQL：SQL 核心知识复习

## DDL 与 DML 基础

### 建表（CREATE TABLE）与约束

### 增删改（INSERT / UPDATE / DELETE / TRUNCATE）

### 基础查询（SELECT / WHERE / ORDER BY / LIMIT）

## 连接（JOIN）

### INNER JOIN / LEFT JOIN / RIGHT JOIN / FULL JOIN / CROSS JOIN

### 自连接（Self Join）

### 多表连接与执行顺序

## 聚合与分组

### GROUP BY 与聚合函数（COUNT / SUM / AVG / MAX / MIN）

### HAVING 过滤

### DISTINCT 与 DISTINCT ON

## 子查询

### 标量子查询 / 行子查询 / 表子查询

### EXISTS 与 NOT EXISTS

### 相关子查询 vs 非相关子查询

## CTE 与递归查询

### WITH 子句（Common Table Expression）

### 递归 CTE（WITH RECURSIVE）

## 窗口函数

### ROW_NUMBER / RANK / DENSE_RANK

### LAG / LEAD

### SUM / AVG OVER（累计与移动窗口）

### PARTITION BY 与 ORDER BY 窗口定义

## 索引

### B-tree / Hash / GIN / GiST / BRIN 索引类型

### 单列索引 vs 复合索引

### 覆盖索引（Covering Index）与部分索引（Partial Index）

### EXPLAIN ANALYZE 读查询计划

## 事务与并发

### 事务基础（BEGIN / COMMIT / ROLLBACK）

### 隔离级别（Read Committed / Repeatable Read / Serializable）

### MVCC 简介

### 锁（行锁 / 表锁 / 死锁检测）

## 常用函数与操作符

### 字符串处理 / 日期时间 / 数学函数

### 类型转换（CAST / ::）

### NULL 处理（COALESCE / NULLIF）

## PostgreSQL 特有功能

### JSON / JSONB 查询与索引

### 数组类型与操作符

### 全文检索（tsvector / tsquery）

### UPSERT（INSERT ... ON CONFLICT）

## 性能优化入门

### 常见查询反模式

### 索引优化策略

### VACUUM 与 ANALYZE

### 连接池与配置调优

## 参考
