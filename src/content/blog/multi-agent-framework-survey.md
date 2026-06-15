---
title: "多 Agent 框架调研：DeepAgent、AgentScope、OpenManus 等"
description: "对 DeepAgent、AgentScope、Agno、OpenManus、Youtu-Agent、Deer-Flow 等多个 Agent 框架的架构分析与对比"
pubDate: 2025-10-24
updatedDate: 2026-06-09
---

本文是对多个主流多 Agent 框架的调研与架构分析笔记，涵盖 DeepAgent、AgentScope、Agno、OpenManus 等框架，重点关注各框架的核心设计思路与工程实现特点。

## DeepAgent 架构阅读笔记

这份笔记只关注 DeepAgent 系统中最核心的运行时设计，不展开太多细枝末节。

重点是理解它作为 Agent Harness 的工程组织方式：Agent 在运行前如何准备上下文，运行中如何管理状态，以及不同模型如何被约束到相对稳定的行为模式。

### 核心分层

DeepAgent 主要可以拆成三个部分：

1. `Backend`
   - 定义运行时后端能力，例如 Shell 调用、Protocol 协议、Sandbox 和 State。
   - 负责存储 Agent 运行时状态，并承载运行过程中产生的附属产物。

2. `Middleware`
   - 主要承载模型调用前后的预处理和后处理。
   - 在 LangChain 后续版本的 Agent 结构中，Middleware 是非常关键的扩展点。

3. `Profiles`
   - 面向不同模型定义 Harness 约束。
   - 不同模型的行为模式并不一致，因此需要通过 Profile 做纠偏，让 Agent 运行规则更稳定。

回到 Harness 本身，这才是 DeepAgent 的核心意义：它不是只包装一次模型调用，而是组织一套可控的 Agent 运行环境。

### 运行入口

整体入口在 `create_agent`。

这个入口会把运行时需要的模块组织起来，例如 `backend_factory`，并接入以下工具和协议：

1. 协议部分：`protocol`、`backend_protocol`
2. 文件系统：`file_system` middleware
3. 内存管理：`memory` middleware
4. 调用处理：`patch_to_calling` middleware
5. 扩展能力：`skills` middleware

这些组件共同处理 Agent 运行前需要准备的行为和上下文信息。

### Backend：状态与工作区

Backend 是这套系统里很值得关注的一层。

在 Coding Agent 中，运行时上下文会持续产生很多状态。比如使用 `ls`、`read`、`grep` 等工具时，本质上都需要围绕当前工作区维护状态、文件信息和执行结果。

DeepAgent 在架构上把状态管理做了拆分：

- Agent 本身的运行流转状态是一类信息。
- Agent 运行过程中产生的文件、命令结果、临时内容是另一类信息。
- Backend 提供统一的工作区抽象，用来承载这些可读写、可查询、可路由的运行时资源。

所以 Backend 的价值不只是"保存东西"，而是给上层 Agent 和 Middleware 提供一套通用工具，例如 `ls`、`read` 等，让不同状态机都能复用同一套运行时能力。

其中 `Composite Backend` 可以理解为一个路由型 Backend：它把不同类型的行为请求分发到不同 Backend，再完成二次路由。

### File System Middleware

File System 是 Coding Agent 中最常见的能力。

运行 Codex、Claude Code 这类工具，比较常见以下工具：

- `grep`
- `ls`
- `read`

这里有一个容易忽略的细节：列举文件时要处理 `symlink`。

`symlink` 是 symbolic link，也就是指向其他文件或目录的链接。它在文件系统里比较特殊，如果不加限制，可能导致遍历范围变得不可控。因此 DeepAgent 在文件列举阶段做了过滤，避免 Coding Agent 在文件系统访问上引入复杂风险。

另一个值得注意的方法是 `perform string replacement`。

它主要用于控制写入或替换行为中的偏差。比如字符串替换时经常会遇到：

1. 待替换目标不存在。
2. 目标字符串有细微偏差，例如末尾位置不同，或者夹杂换行、空格等控制字符。

这个方法的意义在于：让文件修改行为尽量保持确定，而不是直接交给模型自由生成整段文件内容。

### 暂不展开的部分

代码里还涉及 LangSmith。

由于 LangSmith 是 LangChain 自己的观测体系，并且商用场景会涉及收费，这里暂时不展开。当前笔记更关注 DeepAgent 自身的 Harness、Backend、Middleware 和文件系统设计。

---

## AgentScope


A concise implementation of **AgentScope**, a framework for orchestrating multi-agent systems with advanced language models.
Reference: *Agentic Design Patterns*

AgentScope 是一个多智能体系统编排框架，专注于通过高级语言模型实现复杂任务的分解与执行。
参考书籍：《Agentic Design Patterns》

### 主要特性

- **多智能体编排**：支持多智能体之间的任务分解与执行。
- **动态工作流管理**：根据实时输入动态调整工作流。
- **语言模型集成**：提供与大语言模型（LLMs）的无缝集成。
- **共享 LLM 实例**：通过在多个智能体之间共享单个 LLM 实例，确保资源高效利用。

### 使用说明

```bash
pip install -r requirements.txt
python main.py
pytest test_main.py
```

### 目录结构

```
multi_agent_framework/
└── agentscope/
    ├── README.md
    ├── main.py
    └── utils.py
```

---

## Agno 框架介绍

Agno 是一个面向 Agentic Software 的 Python 框架，重点不是只封装一次大模型调用，而是提供一套可以从原型走到服务化运行的 Agent 系统结构。

它的核心定位可以拆成两层：

1. `Agno SDK`
   - 用 Python 编写 Agent、Team 和 Workflow。
   - 负责模型、工具、记忆、知识库、状态、结构化输入输出、评测和可观测性等能力。

2. `AgentOS`
   - 把已经写好的 Agent、Team、Workflow 作为服务运行。
   - 基于 FastAPI 提供 API、会话隔离、追踪、调度、权限控制和控制台管理能力。

因此，Agno 更像是一个"Agent 应用框架 + Agent 运行时平台"，而不是单纯的 prompt 工具库。

### 核心抽象

Agno SDK 主要提供三个核心抽象。

#### Agent

`Agent` 是最基础的执行单元。

一个 Agent 通常包含：

- model：使用哪个模型。
- tools：可以调用哪些工具。
- instructions：行为约束和任务说明。
- db / storage：会话和运行状态如何持久化。
- memory：是否记录用户偏好、历史事实和长期上下文。
- knowledge：是否接入文档、URL、数据库等外部知识。

简单理解，Agent 是"一个有模型、有工具、有上下文管理能力的智能程序"。

#### Team

`Team` 用来组织多个 Agent 协作。

它适合这些场景：

- 一个任务需要多个专业角色。
- 单个 Agent 的上下文窗口不够。
- 不同子任务需要不同工具或不同模型。
- 希望把复杂系统拆成更容易维护的多个 Agent。

Agno 的 Team 不只是简单地把多个 Agent 串起来，而是强调角色、协作模式、成员调度和状态隔离。Team 里还可以嵌套子 Team，用来表达更复杂的协作结构。

#### Workflow

`Workflow` 用来表达确定性的步骤编排。

它可以把 Agent、Team、普通 Python 函数、子 Workflow 组织成流程，支持顺序、并行、循环和条件分支。

如果任务需要"可重复、可审计、步骤稳定"的执行路径，Workflow 比自由协作的 Team 更合适。

### 主要功能

#### 模型与工具

Agno 支持多个模型提供商，并提供统一的模型调用方式。工具层面内置了大量集成，也支持用户自己写工具。

常见能力包括：

- 调用搜索、文件、数据库、API 等外部工具。
- 为不同 Agent 配置不同工具集。
- 让工具和 Agent / Team 的运行上下文结合。
- 支持多模态输入输出。
- 支持 Pydantic 结构化输入输出。

#### 记忆与上下文

Agno 内置 memory、session、state、knowledge 等上下文能力。

这些能力解决的问题不同：

- `Session`：管理多轮对话历史、摘要和运行指标。
- `State`：保存 Agent 运行中可读写的状态。
- `Memory`：保存用户偏好、长期事实和跨会话信息。
- `Knowledge`：接入文档、URL、数据库等外部知识源，提供检索增强能力。
- `Context Providers`：把日历、邮件、GitHub、Slack、MCP 等实时上下文注入 Agent。

这也是 Agno 区别于轻量 Agent 封装库的重要部分：它把"上下文如何进入 Agent、如何保存、如何复用"作为框架内置能力。

#### Reasoning

Agno 对 reasoning 的支持比较突出。

它提供两类思路：

1. 使用支持原生 reasoning 的模型。
2. 使用 reasoning tools，让普通模型也能显式调用 `think()`、`analyze()` 等工具。

Reasoning tools 的关键点是：Agent 可以在执行过程中自己决定什么时候思考、什么时候调用工具、什么时候分析结果，而不是只在开头生成一次固定计划。

Agno 还提供面向不同场景的 reasoning 工具：

- `ReasoningTools`：通用推理。
- `KnowledgeTools`：围绕知识库检索进行推理。
- `MemoryTools`：围绕用户记忆进行增删改查和分析。
- `WorkflowTools`：围绕工作流执行进行推理。

#### 安全、控制与可观测性

Agno 把生产运行需要的能力也纳入框架范围：

- Guardrails：校验输入和输出。
- Hooks：运行前后插入逻辑。
- Human-in-the-loop：需要人工审批、输入或外部执行时暂停。
- Evals：评估 Agent 的准确性、性能和稳定性。
- Tracing / Observability：追踪 Agent 运行过程。
- Background execution：长任务后台执行。
- Scheduler：定时运行 Agent 或 Workflow。

这些能力说明 Agno 的目标不是只做 demo，而是支持实际 Agent 应用上线。

### AgentOS

AgentOS 是 Agno 的运行时层。

它本质上是一个 FastAPI 应用，可以把 Agent、Team 和 Workflow 作为服务暴露出来。

AgentOS 提供：

- 生产 API。
- SSE 流式响应。
- 会话存储。
- 用户、Agent、Session 之间的请求隔离。
- JWT / RBAC 权限控制。
- traces 和运行日志。
- human-in-the-loop 与审批流程。
- 调度和后台执行。
- 控制台 UI，用来测试、监控和调试 Agent 系统。

一个重要特点是：AgentOS 运行在自己的基础设施里，session、memory、knowledge、trace 等数据存储在自己的数据库中。Agno 官方控制台主要连接和管理你的运行时，而不是接管所有数据。

### 特色总结

Agno 的特色可以概括为以下几点。

#### 1. 从单 Agent 到多 Agent 再到 Workflow

很多框架只强调 Agent 或工具调用，Agno 则把三种层次都放在同一套架构中：

- 单 Agent：适合简单任务。
- Team：适合多角色协作。
- Workflow：适合稳定、可重复、可审计的流程。

这使它既能写原型，也能表达更复杂的业务系统。

#### 2. 上下文能力内置

Agno 不把 memory、session、knowledge、state 当成外部附加功能，而是作为 Agent 系统的一部分。

这对真实应用很关键，因为真实 Agent 的难点往往不是"能不能调模型"，而是：

- 历史对话如何保留。
- 用户偏好如何沉淀。
- 外部知识如何检索。
- 长会话如何压缩。
- 运行状态如何隔离。

#### 3. 强调生产化

AgentOS 让 Agno 不止停留在脚本层。

开发阶段可以直接写 Python Agent；上线阶段可以通过 AgentOS 变成 API 服务，并接入权限、追踪、调度和控制台。

#### 4. Reasoning 是一等能力

Agno 不是只依赖模型本身的推理能力，也提供显式 reasoning tools。

这让 Agent 的思考过程、工具调用过程和结果分析过程更容易被观察和控制。

#### 5. 多框架兼容

AgentOS 除了运行原生 Agno Agent，也可以服务 Claude Agent SDK、LangGraph、DSPy 等框架构建的 Agent。

这说明 Agno 的运行时目标更偏"Agent 平台层"，不是完全封闭在自己的 SDK 内。

### 和 LangChain / LangGraph 的区别

粗略理解：

- LangChain 更像 LLM 应用开发工具箱，组件生态很大。
- LangGraph 更强调图结构、状态机和可控 Agent 流程。
- Agno 更强调 Agent / Team / Workflow 的统一抽象，以及从 SDK 到 AgentOS 的生产化运行路径。

如果关注底层图调度和状态流，LangGraph 更值得细读。

如果关注"如何把 Agent 系统组织成产品级服务"，Agno 的 AgentOS 和生产运行能力更有代表性。

### 资料入口

- 官网：https://www.agno.com/
- 文档：https://docs.agno.com/
- SDK 介绍：https://docs.agno.com/sdk/introduction
- AgentOS 介绍：https://docs.agno.com/agent-os/introduction

---

## OpenManus

OpenManus 是一个开源的多 Agent 协作框架项目。待补充详细阅读笔记。

---

## Youtu-Agent

Youtu-Agent 是一个多 Agent 框架项目。待补充详细阅读笔记。

---

## Deer-Flow

Deer-Flow 是一个多 Agent 框架项目。待补充详细阅读笔记。
