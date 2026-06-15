---
title: "LangChain Agent 架构与中间件系统"
description: "深入解析 LangChain 2025 年 10 月大改版后的 Agent Factory 架构，包括 create_agent 初始化流程、Middleware 设计原理、Graph 边编排以及循环执行机制。"
pubDate: 2026-05-29
updatedDate: 2026-06-08
---

本文是阅读 LangChain Agent 架构源码时的笔记整理，重点关注 2025 年 10 月大改版后的 Factory 初始化流程、Middleware 设计原理以及基于 LangGraph 的 Graph 编排机制。

## 概述

从 2025 年 10 月开始，LangChain 进行了重大改版，Agent 创建入口主要挪到了 Factory 方法。这次改版后，Agent 底层走的是 LangGraph 的那一套 Graph 架构，后续的执行以及整个 Agent 行为的构成，都是依照 LangGraph 的原则去设计的。

## Factory 参数

`create_agent` 工厂方法提供以下参数：

| 参数名 | 类型 | 描述 |
| --- | --- | --- |
| model | `str \| BaseChatModel` | 模型本身 |
| tools | `Sequence[BaseTool \| Callable[..., Any] \| dict[str, Any]] \| None` | 初始化时传入的工具 |
| system_prompt | `str \| SystemMessage \| None` | 系统 prompt |
| middleware | `Sequence[AgentMiddleware[StateT_co, ContextT]]` | 中间件，控制模型的 tool call、agent、model call 前后的行为，是很重要的改动 |
| response_format | `ResponseFormat[ResponseT] \| type[ResponseT] \| dict[str, Any] \| None` | 模型的返回类型 |
| state_schema | `type[AgentState[ResponseT]] \| None` | Agent runtime 的 state 参数 |
| context_schema | `type[ContextT] \| None` | 一些额外的上下文参数 |
| checkpointer | `Checkpointer \| None` | memory，LangChain 管理记忆的核心内容 |
| store | `BaseStore \| None` | LangChain 管理记忆的核心内容 |
| interrupt_before | `list[str] \| None` | HIL 的打断参数，或一些前后操作可用的类似 AOP 的切入 |
| interrupt_after | `list[str] \| None` | 同上 |
| debug | `bool` | 调试模式 |
| name | `str \| None` | 给 graph 起别名 |
| cache | `BaseCache[Any] \| None` | 给图的执行结果存 cache，类似 LRU |

## create_agent 初始化流程

`create_agent` 初始化时遵循以下流程：

1. **初始化模型** — 使用 `init_chat_model`，一般情况下直接传入模型实例是最简单的初始化方式。
2. **合并消息 input**
3. **合并 System Prompt** — 初始化时使用 LangChain 专属的 `SystemMessage` 进行转换。
4. **处理 Structured Output**

### init_chat_model

`init_chat_model` 方法提供了几个工程上比较重要的参数：

```python
configurable_fields: Literal["any"] | list[str] | tuple[str, ...] | None = None
config_prefix: str | None = None
```

- `configurable_fields`：哪些模型参数可以在运行时配置。
- `config_prefix`：在同一个应用中有多个可配置模型时，为模型设置别名。

模型运行时参数的可变以及模型别名，提供了很大的灵活空间。例如 A 模型欠费、宕机或不想用了，或者不同任务需要不同价格或类型的模型，可以通过这种方式切换。不过有了 Middleware 之后，也可以通过 request override 重写当前用的模型，这种方式更为方便。`config_prefix` 则让不同角色的 Agent 及不同任务可以通过前缀使用指定模型去处理。

### structured_output

规定了结构化输出的一系列格式：`AutoStrategy`、`ProviderStrategy`、`ToolStrategy`，主要用于 `response_format` 的输出策略。

- **AutoStrategy**：自动选择最优的 response strategy。
- **ToolStrategy**：对于原生不支持结构化输出的模型，LangChain 将这部分封装成 Tool Calling 的形式，实现稳定的结构化 Response 效果。
- **ProviderStrategy**：各厂商自己的模型原生支持输出结构化结果。

## Middleware 设计

Middleware 是 LangChain 在 2025 年 10 月大改版以后一个特别重要的特性。它把模型的前后处理、Agent 的执行前后、Tool 的执行前后，以及 Model 周期内可能发生的一些行为进行了封装。其行为类似于 Java 里的 AOP。

Middleware 提供的方法包括：

1. `before_agent`
2. `after_agent`
3. `before_model`
4. `after_model`
5. `wrap_model_call`
6. `wrap_tool_call`

### Middleware 执行顺序

Middleware 的执行并不像直觉中那样按顺序链式执行，而是更像 Hook 机制：

1. **所有 before 行为**：把所有 Middleware 的 before 行为通过 for 循环串联到一起，顺序执行。
2. **所有 after 行为**：同样串联到一起，顺序执行。
3. **wrap 行为**：组合成 wrapper stack，包住对应的 model call 或 tool call。

### wrap_tool_call 的组合

LangChain 采用"倒序执行"的策略来组合多个 Middleware 的 wrap 方法：

```python
# Chain all wrappers: first -> second -> ... -> last
result = wrappers[-1]
for wrapper in reversed(wrappers[:-1]):
    result = compose_two(wrapper, result)
```

当拥有多个 Middleware（如 A、B、C）时，它们按顺序加载，但实际执行从最内层开始反向执行。最终返回一个包含了完整执行顺序的"套娃"函数体，类似 `A(B(C(kwargs)))`。

### before/after agent/model 的抽取

LangChain 会检查每个 Middleware 是否实际覆写了 `before_agent`、`after_agent`、`before_model`、`after_model` 方法，只抽取那些有实际实现的 Middleware：

```python
middleware_w_before_agent = [
    m for m in middleware
    if m.__class__.before_agent is not AgentMiddleware.before_agent
    or m.__class__.abefore_agent is not AgentMiddleware.abefore_agent
]
```

### wrap_model_call 的抽取

对于 `wrap_model_call` 方法，LangChain 将其与 `traceable` 装饰器结合，增强可观测性：

```python
if middleware_w_awrap_model_call:
    async_handlers = [
        traceable(name=f"{m.name}.awrap_model_call", process_inputs=_scrub_inputs)(
            m.awrap_model_call
        )
        for m in middleware_w_awrap_model_call
    ]
    awrap_model_call_handler = _chain_async_model_call_handlers(async_handlers)
```

### State 抽取

LangChain 从当前 Agent 抽取工具后遍历所有 Middleware 抽取 state schema：

```python
state_schemas: set[type] = {m.state_schema for m in middleware}
base_state = state_schema if state_schema is not None else AgentState
state_schemas.add(base_state)
```

类似 `ModelCallLimitMiddleware` 中的 `thread_model_call_count` 等专属参数，为了避免污染 runtime 内容，会使用 `PrivateStateAttr` 标记，并通过 `OmitFromSchema` 机制过滤。

## Graph 初始化

完成上述准备工作后，LangChain 使用 `StateGraph` 构建 Agent 的执行图：

```python
graph = StateGraph(
    state_schema=resolved_state_schema,
    input_schema=input_schema,
    output_schema=output_schema,
    context_schema=context_schema,
)
```

所有状态被打包好，开始构造初始的图。

## Graph 边构造

从 factory.py 中可以看到，LangChain 把 Middleware 的行为（before、after 那一套）都挂载成了 Graph 的边。Middleware 的执行顺序是：

```
before_agent -> before_model -> model -> after_model -> after_agent -> END
```

**before 系列的编排**：通过 `pairwise` 串联，A 组件执行完毕后导向 B，后续依次类推，构成 Graph 的中间件执行链路。

**entry/exit 节点和循环的 entry/exit**：Agent 作为 Model 的前置行为，会率先作为入口。

**after 系列的编排**：采用倒序执行策略：

```python
for idx in range(len(middleware_w_after_model) - 1, 0, -1):
```

前置链是 `before-agent -> before-model -> model -> after-model -> after-agent -> END`（如果没有循环的话）。

## 循环与工具机制

LangChain 设计了基于 Loop 的循环机制。

### 条件路径

Tool 的 edge 走向给出了条件分支：`after_agent`、`model`、`END`。

`loop_exit` 节点指向三个方向：
1. tools
2. exit_node（after_agent、END）

### loop 判断逻辑

`_make_model_to_model_edge` 包含以下判断：

1. **Jump 逻辑**：如果有指定的 `jump_to` 目的地，直接跳转并附带之前的参数。
2. **消息处理判断**：检查是否有 `AIMessage` 和 `ToolMessage` 并判断是否处理完毕。
3. **结束节点跳转**：如果没有 AI 消息，直接跳往 END 节点（包括 END 和 after_agent）。
4. **Pending to Call 状态**：判断是否存在 `pending_to_call`（工具存在但未被调用或未生成结果），若存在则再次发送到 tools 节点执行。

**为什么需要再次进入 tools 节点？**
1. tools 的执行过程可能会报错，不能保证百分之百成功。
2. tools 本身可能没有收集到足够的信息。
3. 上层 Agent（如 Agent As Tool 的 Agent）下属工具在收集信息后，经由 Agent 判定信息尚未收集完整，会再次跳回到 Tool 节点。

### return_direct

LangChain 在 `BaseTool` 类规定了 `return_direct` 参数。当该参数为 True 时，直接返回结果，然后进入 END 或 after_agent 环节。

### structured_output tool 分支

当没有给 Agent 提供工具，但又规定了结构化输出格式时，Agent 直接走 Middleware 的底层流程。

## 内置 Middleware 目录

LangChain 提供了丰富的内置 Middleware，覆盖了从模型调用、工具执行、安全审计到上下文管理等各个方面：

| 文件名 | 功能 | 目的 |
| :--- | :--- | :--- |
| **human_in_the_loop** | 提供人工审批介入流程 | 保证敏感/高危操作的安全控制 |
| **model_call_limit** | 监控并限制大模型调用次数 | 防止死循环，控制 Token 成本 |
| **model_retry** | 自动重试失败的大模型请求 | 提高 API 调用的鲁棒性 |
| **model_fallback** | 降级切换至备用大模型 | 保证模型层的高可用 |
| **summarization** | 对历史消息进行摘要压缩 | 优化上下文窗口占用 |
| **pii** | 遮蔽或哈希敏感隐私数据 | 满足安全审计与合规要求 |
| **shell_tool** | 绑定持续终端会话工具 | 隔离并安全运行生成代码 |
| **tool_call_limit** | 限制工具累计调用次数 | 避免资源浪费 |
| **tool_retry** | 工具调用的指数退避重试 | 提高外部 API 可靠性 |
| **context_editing** | 过滤并替换超限历史会话 | 精简上下文 |
| **tool_selection** | 利用轻量模型干预工具选择 | 动态决策路由 |
| **tool_emulator** | 模拟工具返回结果 | 自动化测试和 Dry-run |
| **todo** | 提供任务进度待办清单 | 保持复杂任务执行规划 |
| **file_search** | 提供文件系统的检索工具 | 快速定位和读取文件 |

## 总结

LangChain 2025 年大改版后的 Agent 架构以 LangGraph 为基础，通过 Factory 模式构建，利用 Middleware 机制实现关注点分离和可插拔的行为扩展。理解其 Graph 边的编排方式、Middleware 的执行顺序以及循环控制机制，对于构建稳定、可扩展的 Agent 应用至关重要。
