---
title: "LangChain Agent Middleware 目录"
description: "LangChain Agent 内置中间件详细参考，涵盖 HIL、模型调用控制、工具管理、安全审计、上下文压缩等 14 个中间件的设计原理与实现细节。"
pubDate: 2025-12-22
updatedDate: 2026-06-10
---

本文是对 LangChain Agent 内置 Middleware 系统的详细梳理，逐一分析每个中间件的设计原理、核心参数与实现细节，涵盖 HIL、模型调用控制、工具管理、安全审计、上下文压缩等 14 个内置中间件。

## 概述

LangChain Agent 的 Middleware 系统是 2025 年 10 月大改版后的核心特性。它将模型的前后处理、Agent 执行前后、Tool 执行前后以及 Model 周期内的行为进行了封装，行为类似于 Java 里的 AOP。LangChain 提供了丰富的内置 Middleware，以下逐一介绍。

## 一、Human In The Loop（人工审批）

**文件：** `human_in_the_loop.py`

人在回路中间件，提供人工审批介入流程，拦截并挂起敏感工具调用，支持人工批准、修改或拒绝。主要用于保证敏感或高危操作（如转账、写操作）的安全控制。

![HIL example](/images/HIL_eg.png)

### 核心参数

`HumanInTheLoopMiddleware` 提供了一个 `interrupt_on` 参数，类型为 `dict[str, bool]` 以及 `dict[str, InterruptOnConfig]`。对于需要被拦截的工具，提供了三个选项：`approve`（批准）、`edit`（修改）、`reject`（拒绝）。

`InterruptOnConfig` 则包含了 `allowed_decisions` 和 `description`。

### 核心机制：interrupt

HIL 的最核心机制是 LangGraph 的 `interrupt` 函数。该函数通过抛出 `GraphInterrupt` 异常来暂停 Graph 执行，并将值暴露给客户端。

```python
def interrupt(value: Any) -> Any:
    """Interrupt the graph with a resumable exception from within a node."""
```

`interrupt` 可以接受任意类型，即存在多种不同的打断方式。

**使用条件**：必须启用 checkpointer（检查点机制），因为 interrupt 依赖于持久化 Graph 状态。

**执行流程**：
1. Graph 在某个节点执行时调用 `interrupt`，抛出 `GraphInterrupt` 异常，暂停执行。
2. 客户端获得中断值后进行处理（如等待用户审批）。
3. 客户端通过 `Command(resume=...)` 恢复 Graph 执行。
4. Graph 从节点开始处重新执行所有逻辑。

## 二、Model Call Limit（模型调用限制）

**文件：** `model_call_limit.py`

监控并限制大模型在单次运行或单个会话中的调用次数，防止 Agent 因规划错误陷入自我纠错的死循环，控制 Token 成本。

### 状态定义

```python
class ModelCallLimitState(AgentState[ResponseT]):
    thread_model_call_count: NotRequired[Annotated[int, PrivateStateAttr]] 
    run_model_call_count: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
```

- `thread_model_call_count`：单个 thread（会话）的模型调用次数
- `run_model_call_count`：单次 run 的模型调用次数

### 参数配置

```python
def __init__(
    self,
    *,
    thread_limit: int | None = None,
    run_limit: int | None = None,
    exit_behavior: Literal["end", "error"] = "end",
)
```

- `thread_limit`：会话级别的模型调用上限
- `run_limit`：单次运行级别的模型调用上限
- `exit_behavior`：达到上限后的行为——`"end"`（正常结束）或 `"error"`（抛出异常）

### 实现逻辑

`before_model` 钩子函数在每次模型调用前检查计数。超过限制时，根据 `exit_behavior` 配置要么抛出 `ModelCallLimitExceededError` 异常，要么通过 `jump_to: "end"` 跳转到结束节点并发送提示消息。

该 Middleware 还通过 `@hook_config(can_jump_to=["end"])` 装饰器声明了可跳转到 `end` 节点，遵循 Graph 构建时的退出路径约定。

## 三、Model Retry（模型重试）

**文件：** `model_retry.py`

自动重试因限流、超时等网络波动而失败的大模型请求，提高大模型 API 调用的鲁棒性与网络健壮性。

### 参数配置

```python
def __init__(
    self,
    *,
    max_retries: int = 2,
    retry_on: RetryOn = (Exception,),
    on_failure: OnFailure = "continue",
    backoff_factor: float = 2.0,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    jitter: bool = True,
)
```

### 退避机制

采用指数退避策略，每次重试的等待时间按公式增长：

```
delay = initial_delay * (backoff_factor ** retry_number)
```

- `initial_delay`：初始等待时间（默认 1 秒）
- `backoff_factor`：退避因子（默认 2.0）
- `max_delay`：最大等待时间（默认 60 秒），防止等待无限延伸

### Jitter 抖动机制

为了防止大量并发请求同时重试导致"惊群效应"，引入了 Jitter 机制：

```python
if jitter and delay > 0:
    jitter_amount = delay * 0.25  # ±25% jitter
    delay += random.uniform(-jitter_amount, jitter_amount)
    delay = max(0, delay)
```

在计算的延迟基础上增减 25% 范围内的随机值，将请求分散到多个时间窗口。

### retry_on 逻辑

`retry_on` 支持多种类型：
- **Callable**：直接调用自定义函数判断是否应重试
- **Tuple**：检查发生的异常是否在元组定义的异常类型范围内

### on_failure（重试耗尽后的行为）

| 选项 | 说明 |
| :--- | :--- |
| `continue` | 跳过并继续，如同忽略错误 |
| `raise exception` | 抛出异常 |
| `custom callable` | 自定义截断处理 |

## 四、Model Fallback（模型降级）

**文件：** `model_fallback.py`

当主模型调用持续报错时，按顺序自动降级切换至备用大模型，保证模型层的高可用性和容错能力。

```python
first_model: str | BaseChatModel,
*additional_models: str | BaseChatModel,
```

如果提供了多个 fallback 模型，系统会按顺序依次尝试，直到其中一个有效或全部失败为止。

## 五、Tool Call Limit（工具调用限制）

**文件：** `tool_call_limit.py`

监控并限制特定工具或全部工具的累计调用次数，拦截频繁多余的工具调用，避免资源浪费和陷入死循环。

> **设计说明：** `tool_call_limit` 与 `model_call_limit` 在本质逻辑上是一致的。因为 Tool 的行为在一定程度上与 Model 的行为相似，执行也有上限。两者基本上采用相似的逻辑实现。

## 六、Tool Retry（工具重试）

**文件：** `tool_retry.py`

对发生瞬时异常的工具调用进行指数退避式自动重试，提高外部 API 工具和三方依赖接口调用的可靠性。

> **设计说明：** 该机制与 Model Retry 的 try-catch 逻辑一致，采用相同的退避重试策略设计。

## 七、Tool Emulator（工具模拟器）

**文件：** `tool_emulator.py`

使用大模型模拟（仿真）工具的返回结果，供自动化测试和 Dry-run 运行时脱离外部 API 执行评估。

使用 emulator 包裹一些 Middleware 或 Tool 时，会拦截这些 Tool 或 Middleware 对模型的调用，并生成模拟的返回结果。主要用于测试场景。

## 八、Tool Selection（工具选择路由）

**文件：** `tool_selection.py`

利用轻量路由模型干预、改写或过滤大模型选择的工具，在模型与工具之间增加一层动态决策路由，控制工具调用流。

**核心设计：** 使用一个 LLM 来"Use an LLM to select relevant tools before calling the main model"。即，在执行主模型之前，先通过轻量模型选择最适合的模型或最适合的工具。

**实现方式：**
1. 获取最近一轮的用户消息以及开发者固定的一些消息（如始终存在的工具，如 HIL）。
2. 固定工具不会占用 Available tools 的占位，会在后续拼接。
3. 减少主模型的 token 消耗，帮助主模型聚焦在正确的工具上。

## 九、Summarization（上下文摘要压缩）

**文件：** `summarization.py`

自动在 Token 数量超限时对较早的历史消息进行摘要式压缩并替换，优化上下文窗口占用，控制长会话下的计算与输入 Token 成本。

### LangChain 的压缩策略

LangChain 作为一个 Agent SDK，其 `SummarizationMiddleware` 是一个样板实现，主要分为几个部分：

**role / primary obj / obj_info：**
- role：Context Extraction Assistant
- primary obj：从历史对话中提取高质量或最相关的上下文
- obj_info：接近 token 上限时提取高价值历史信息

**instruction 包含四个提取维度：**

| 维度 | 说明 |
| :--- | :--- |
| SESSION INTENT | 用户的会话意图和主要请求 |
| SUMMARY | 重要的选择、结论、策略决策及其推理逻辑 |
| ARTIFACTS | 产出的文件、资源访问、修改创建记录 |
| NEXT STEPS | 距离完成任务还有几步，下一步要做什么 |

LangChain 的默认总结 prompt：

```python
DEFAULT_SUMMARY_PROMPT = """
<role>
Context Extraction Assistant
</role>
<primary_objective>
Your sole objective in this task is to extract the highest quality/most relevant context from the conversation history below.
</primary_objective>
<objective_information>
...
</objective_information>
<instructions>
...
</instructions>
"""
```

### Claude Code 的压缩策略对比

Claude Code（CC）的压缩策略更加细致且科学，与 LangChain 的通用策略相比，更加专注于代码工程场景。

**CC 的核心特点：**
1. 强调**不允许调用工具**（NO_TOOLS_PREAMBLE + NO_TOOLS_TRAILER），防止模型在压缩过程中执行额外操作。
2. 要求输出 `<analysis>` 和 `<summary>` 格式的 plain text。
3. 从多个维度对总结内容进行详细规定：
   - **Primary Request and Intent**：用户明确的请求和意图细节
   - **Key Technical Concepts**：技术概念、技术和框架讨论
   - **Files and Code Sections**：具体文件和代码段，含完整代码片段
   - **Errors and Fixes**：错误及其修复方式
   - **Problem Solving**：已解决和正在定位的问题
   - **All User Messages**：非 tool call 的用户消息
   - **Pending Tasks**：待处理任务
   - **Current Work**：当前工作精确描述
   - **Optional Next Step**：下一步最相关的任务

**CC 的设计侧重工程性**：没有以轮数作为压缩单位，而是着重于文件修改、历史对话、技术细节、错误修改及其原因和任务状态，特别是改动细节是最主要的总结对象。这种压缩策略更像是以 diff 为主的工程性变动，而非对话性质的压缩。

**共同点**：LangChain 和 CC 的 summarize/compact 都是为了压缩上下文，侧重对象都包含用户意图、执行过程中的错误及修改方式、文件的生成和创建等。

## 十、PII（隐私数据脱敏）

**文件：** `pii.py`

检测并遮蔽（Mask）或哈希（Hash）输入输出中的敏感个人隐私数据，满足安全审计与合规要求，防止用户隐私数据泄漏给外部大模型。

> 该中间件主要涉及数据脱敏处理，与 Agent 的任务流程控制关系不大，但安全合规方面非常重要。

## 十一、Shell Tool（安全终端执行）

**文件：** `shell_tool.py`

绑定持续终端会话工具，并提供 Host、Docker 等执行环境策略，隔离并安全运行大模型生成的代码，避免破坏宿主机。

## 十二、Context Editing（上下文裁剪）

**文件：** `context_editing.py`

对超出 token 界限的历史会话进行过滤并将其替换为 placeholder，快速裁切过往冗余的详细工具结果，精简上下文。

## 十三、Todo（任务待办清单）

**文件：** `todo.py`

提供任务进度待办清单工具，将目标任务分解为 pending、in_progress 和 completed 状态，使模型能保持长序列复杂任务的执行规划和状态可见度。

### 设计模式

TODO 围绕着 `wrap_model_call` 控制模型的生成，通过 `after_model` 控制结果。计划生成依靠模型进行，是一种合理的职责分配。

### Prompt 设计

TODO 的 prompt 分为两部分：

**WRITE_TODOS_SYSTEM_PROMPT**（系统层提示）：
- 使用 `write_todos` 工具管理和规划复杂目标
- 任务完成后需显式标记为 done，不可批量执行多步骤后再标记
- 仅用于复杂任务，简单任务不需要使用

**WRITE_TODOS_TOOL_DESCRIPTION**（工具层描述）：

| 维度 | 内容 |
| :--- | :--- |
| When to Use | 复杂多步任务（3步以上）、用户明确要求、需要迭代的 plan 任务 |
| How to Use | 执行前标记 in_progress、完成后标记 completed、动态增删任务 |
| Task States | pending / in_progress / completed |
| Task Management | 实时更新状态、一个接一个执行、首个任务立即标记 in_progress |
| Completion Requirements | 全部完成才标记、错误/阻塞保持 in_progress、禁止标记 completed 的四种情况 |
| Task Breakdown | 生成可执行的条目、复杂任务拆分、使用清晰描述性名称 |

### 核心原则

- 状态的稳定管理比硬性约束更为重要
- 通过 `StructuredTool` 构建 `write_todo` 方法
- 任务可以在 `wrap_model_call` 中切换模型进行思考

## 十四、File Search（文件系统检索）

**文件：** `file_search.py`

提供文件系统的 Glob 和 Grep 检索工具，帮助 Agent 更加快速精准地定位和读取文件内容。

### 初始化参数

| 参数 | 说明 |
| :--- | :--- |
| 文件路径 | 检索的基础路径 |
| 是否使用 rg 命令 | 是否启用 ripgrep 加速搜索 |
| max_file_size_mb | 能搜索的最大文件大小（默认 10 MB） |

### 提供的工具

**`glob_search(pattern: str, path: str = "/")`** — 基于 Glob 模式匹配文件路径。

**`grep_search(pattern: str, path: str = "/", include: str | None = None, output_mode: Literal["files_with_matches", "content", "count"] = "files_with_matches")`** — 基于正则表达式的文件内容搜索，支持三种输出模式：仅文件名、内容匹配、匹配计数。

## 十五、Types（Middleware 类型系统）

**文件：** `types.py`

规定了 Middleware 的一套元数据设计，提供了已经内置其中的 Agent/Model 行为注解，方便开发者只需要用到单个 `before_agent` / `after_agent` / `before_model` / `after_model` 周期而不需要全套实现。

### 注解装饰器

LangChain 提供了四个装饰器：`@before_agent`、`@after_agent`、`@before_model`、`@after_model`。它们采用相同的设计模式：

```python
@before_agent(can_jump_to=["end"])
def conditional_before_agent(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    if some_condition(state):
        return {"jump_to": "end"}
    return None
```

装饰器会使用函数名自动创建 Middleware 类，方便调试。它支持：
- `state_schema`：自定义 state schema
- `tools`：注册额外的工具
- `can_jump_to`：条件跳转目的地（`"tools"`、`"model"`、`"end"`）
- `name`：自定义 middleware 名称

### ModelRequest / ModelResponse

`ModelRequest` 和 `ModelResponse` 是存在于 `wrap_model_call` 周期的重要参数：
- **ModelRequest**：实例化于 Graph invoke 时，注意 override 时 `sys_msg` 和 `sys_prompt` 不可同时存在
- **ModelResponse**：存在于 `wrap_model_call` 返回期间

## 总结

LangChain 的 Middleware 系统涵盖了模型调用控制、工具管理、安全审计、上下文管理、人工审批等多个维度。理解每个 Middleware 的作用节点（before/after/wrap）、设计原理以及它们如何在 Graph 中组合，对于正确配置和扩展 Agent 行为至关重要。开发者也可以基于这套模式设计自定义 Middleware，满足特定业务需求。
