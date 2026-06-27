---
title: "Matryoshka Representation Learning"
description: "套娃表征学习：单模型产出多分辨率 embedding，精度-效率灵活取舍，在向量检索与 RAG 中的应用"
pubDate: 2026-06-27
section: engineering
---

## 概述

Matryoshka Representation Learning（MRL）通过一次训练产出支持多维度截断的 embedding，无需为不同精度需求重复训练模型。本文梳理其原理、训练策略及在向量检索场景的应用。
