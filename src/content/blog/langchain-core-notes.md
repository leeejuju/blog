---
title: "LangChain 源码阅读笔记：Core 模块"
description: "全面解析 LangChain Core 模块源码，涵盖 Runnable、Messages、Prompts、Language Models、Tools、Callbacks、Output Parsers、Load、Documents、Embeddings 等核心子模块的设计与实现"
pubDate: 2026-02-11
updatedDate: 2026-04-06
---

本文是阅读 LangChain Core 模块源码时的笔记整理，涵盖 Runnable、Messages、Prompts、Language Models、Tools、Callbacks、Output Parsers 等核心子模块的设计与实现分析。文中包含大量源码片段与作者的个人理解与评价。

> `langchain-core` 是整个 LangChain 所有的基本行为的抽象集合，定义了所有 agent 组件的调用标准协议，但是你让我用这玩意上工程，或许之前我会，但是现在就算了。
> 所有其他包（`langchain`、`langgraph`、`langchain-openai` 等）都依赖它，但它不依赖任何人。

---

## 模块总览

```text
langchain-core          ← 最底层，定义所有基础抽象
    │
    ├── callbacks           # 回调系统（追踪、日志、事件钩子）
    ├── documents           # Document 数据结构（RAG 的基础单元）
    ├── embeddings          # 嵌入模型接口（文本 → 向量）
    ├── example_selectors   # Few-shot 示例选择器
    ├── indexing            # 索引 API（文档去重、增量更新）
    ├── language_models     # 语言模型基类（BaseChatModel、BaseLLM）
    ├── load                # 序列化/反序列化（Serializable）
    ├── messages            # 消息类型（HumanMessage、AIMessage 等）
    ├── output_parsers      # 输出解析器（JSON、Pydantic 等）
    ├── outputs             # 模型输出结构（ChatResult、LLMResult）
    ├── prompts             # Prompt 模板（ChatPromptTemplate 等）
    ├── runnables      🌟   # Runnable 接口（核心中的核心）
    ├── tools               # 工具定义接口（BaseTool）
    ├── tracers             # 追踪器（LangSmith、Console）
    ├── utils               # 通用工具函数
    └── vectorstores        # 向量数据库接口
```

---

## 在 LangChain 生态中的位置

```text
langchain-core              ← 基础协议
    │
    ├── langchain            ← 上层封装（create_agent 等）
    ├── langgraph            ← Agent 编排引擎（状态图）
    └── langchain-xxx        ← 各厂商集成（openai、anthropic...）
```

---

## Runnable — LangChain 的核心协议

> `Runnable` 是 LangChain 的**绝对核心**，**且没有之一**。
> 无论是 Model、Tool、Prompt 还是 Parser，所有组件都实现了 `Runnable` 接口。
> LangChain 这样设计，我估计是有以下原因：
> 1. 为了不同的情况下，依旧能实现统一的调用方法，是高度抽象的设计。
> 2. 这里吐槽一下，感觉是没有必要的东西，设计有点过于复杂。

### `runnables/base.py` 核心类

```text
Runnable (ABC, Generic[Input, Output])        ← 基类
    │
    ├── RunnableSerializable                  ← 可序列化的 Runnable
    │
    ├── RunnableSequence                      ← 串行链（A | B | C）
    │
    ├── RunnableParallel                      ← 并行链（{"a": A, "b": B}）
    │
    ├── RunnableGenerator                     ← 生成器函数包装器
    │
    └── RunnableLambda                        ← 普通函数包装器
```

### Runnable 接口定义（核心方法）

| 分类 | 方法 | 说明 |
| :--- | :--- | :--- |
| **执行** | `invoke` / `ainvoke` | 单次调用（同步/异步） |
|  | `stream` / `astream` | 流式输出 |
|  | `batch` / `abatch` | 批量并发 |
|  | `transform` / `atransform` | 流式输入 → 流式输出 |
| **组合** | `__or__` (`\|`) | 串行组合：`A \| B \| C` → `RunnableSequence` |
|  | `pipe()` | 同上，方法调用版 |
|  | `pick()` | 从 dict 输出中选 key |
|  | `assign()` | 给 dict 输出添加新 key |
|  | `coerce_to_runnable()` | 组合所有继承自 `Runnable` 的对象，是组合核心 |
| **装饰** | `bind()` | 绑定默认参数（Agent 绑定工具的基础） |
|  | `with_config()` | 绑定运行时配置 |
|  | `with_retry()` | 失败自动重试 |
|  | `with_fallbacks()` | 失败切换备用方案 |
|  | `with_listeners()` | 添加生命周期钩子 |
| **内省** | `input_schema` / `output_schema` | 获取输入/输出的 Pydantic Schema |
|  | `get_graph()` | 底层核心转向 langGraph 后的重要方法，主要用于生成和获取图结构 |

#### 设计初衷

LangChain 早期各组件调用方式不统一，`Runnable` 的出现将**所有组件统一为同一套方案**：

1. **调用方法的统一** → 统一 `invoke`/`stream`/`batch`

2. **泛型推断**

```python
@property
def InputType(self) -> type[Input]:
    # First loop through all parent classes and if any of them is
    # a Pydantic model, we will pick up the generic parameterization
    # from that model via the __pydantic_generic_metadata__ attribute.
    for base in self.__class__.mro():
        if hasattr(base, "__pydantic_generic_metadata__"):
            metadata = base.__pydantic_generic_metadata__
            if (
                "args" in metadata
                and len(metadata["args"]) == _RUNNABLE_GENERIC_NUM_ARGS
            ):
                return cast("type[Input]", metadata["args"][0])

    # If we didn't find a Pydantic model in the parent classes,
    # then loop through __orig_bases__.
    for cls in self.__class__.__orig_bases__:
        type_args = get_args(cls)
        if type_args and len(type_args) == _RUNNABLE_GENERIC_NUM_ARGS:
            return cast("type[Input]", type_args[0])

    msg = (
        f"Runnable {self.get_name()} doesn't have an inferable InputType. "
        "Override the InputType property to specify the input type."
    )
    raise TypeError(msg)
```

3. **组合式的执行** → `|` 其底层重写了 `__or__` 方法

```python
def __or__(
    self,
    other: Runnable[Any, Other]
    | Callable[[Iterator[Any]], Iterator[Other]]
    | Callable[[AsyncIterator[Any]], AsyncIterator[Other]]
    | Callable[[Any], Other]
    | Mapping[str, Runnable[Any, Other] | Callable[[Any], Other] | Any],
) -> RunnableSerializable[Input, Other]:
    return RunnableSequence(self, coerce_to_runnable(other))
```

这使得封装出一个 Sequence 序列，将上一步的结果作为下一步组件的输出：

```python
chain = prompt | model    # prompt 为 ChatPromptTemplate 等对象时，Runnable 重写了 __or__
chain = prompt.__or__(model) # 返回 RunnableSequence 对象
```

这便是 **langchain 最初串联组件的核心方式**。

当然这里又出现了一个缺点，这就要回到 `Agent` 的定义上去了。什么是 `Agent`，即 *An LLM agent runs tools in a loop to achieve a goal*。Key point is **the loop**，但是其串行的方式意味着这无法进行自检和循环，这就不符合其定义。因此 `langchain` 便推出了 `langgraph` 以及后续的大改版。

4. **异步/流式重复写** → 基类提供默认实现
5. **类型不透明** → `input_schema`/`output_schema` 自动推断

### RunnableSerializable — 一切都是可序列化的

```python
class RunnableSerializable(Serializable, Runnable[Input, Output]):
    """Runnable that can be serialized to JSON."""

    name: str | None = None

    @override
    def to_json(self) -> SerializedConstructor | SerializedNotImplemented:
        dumped = super().to_json()
        with contextlib.suppress(Exception):
            dumped["name"] = self.get_name()
        return dumped

    def configurable_fields(self, **kwargs: AnyConfigurableField) -> RunnableSerializable[Input, Output]:
        # ...

    def configurable_alternatives(self, which: ConfigurableField, *, default_key: str = "default", prefix_keys: bool = False, **kwargs) -> RunnableSerializable[Input, Output]:
        # ...
```

langchain 重写了 Serializable，填充了关于 lc 的一堆属性：

```python
@property
def lc_secrets(self) -> dict[str, str]:
    return {}

@property
def lc_attributes(self) -> dict:
    return {}

@classmethod
def lc_id(cls) -> list[str]:
    return []
```

### RunnableSequence — 串行链

```python
chain = prompt | model | parser
# 内部: RunnableSequence(first=prompt, middle=[model], last=parser)
# 执行: prompt 的输出 → model 的输入 → parser 的输入
```

`|` 操作符就是 `__or__` 重载，返回一个 `RunnableSequence` 对象。

```python
first: Runnable[Input, Any]
"""The first `Runnable` in the sequence."""
middle: list[Runnable[Any, Any]] = Field(default_factory=list)
"""The middle `Runnable` in the sequence."""
last: Runnable[Any, Output]
"""The last `Runnable` in the sequence."""

def __init__(
    self,
    *steps: RunnableLike,
    name: str | None = None,
    first: Runnable[Any, Any] | None = None,
    middle: list[Runnable[Any, Any]] | None = None,
    last: Runnable[Any, Any] | None = None,
) -> None:
    steps_flat: list[Runnable] = []
    if not steps and first is not None and last is not None:
        steps_flat = [first] + (middle or []) + [last]
    for step in steps:
        if isinstance(step, RunnableSequence):
            steps_flat.extend(step.steps)
        else:
            steps_flat.append(coerce_to_runnable(step))
    # ...
    super().__init__(
        first=steps_flat[0],
        middle=list(steps_flat[1:-1]),
        last=steps_flat[-1],
        name=name,
    )
```

### RunnableParallel — 并行链

**RunnableParallel is one of the two main composition primitives**，另一个是 RunnableSequence。

RunnableParallel 的构建方式是 key-value 的形式：

```python
steps__={key: coerce_to_runnable(r) for key, r in merged.items()}
```

```python
class RunnableParallel(RunnableSerializable[Input, dict[str, Any]]):
    """Runnable that runs a mapping of `Runnable`s in parallel,
    returns a mapping of their outputs."""

    steps__: Mapping[str, Runnable[Input, Any]]

    def __init__(self, steps__=None, **kwargs):
        merged = {**steps__} if steps__ is not None else {}
        merged.update(kwargs)
        super().__init__(
            steps__={key: coerce_to_runnable(r) for key, r in merged.items()}
        )
```

值得注意的是，RunnableParallel 底层用了一个继承了 `ThreadPoolExecutor` 的 `ContextThreadPoolExecutor`，其同步方法用到的是线程池的方案，同时保留了上下文的信息。

### RunnableGenerator — 生成器包装器

主要是包装一个底层的迭代器，便于用户自行定义 Stream 的后处理过程：

```python
from langchain_core.runnables import RunnableGenerator

def stream_words(input):
    for word in input.split():
        yield word

streamer = RunnableGenerator(stream_words)  # 支持流式
```

官方示例：

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableGenerator, RunnableLambda
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

model = ChatOpenAI()
chant_chain = (
    ChatPromptTemplate.from_template("Give me a 3 word chant about {topic}")
    | model
    | StrOutputParser()
)

def character_generator(input: Iterator[str]) -> Iterator[str]:
    for token in input:
        if "," in token or "." in token:
            yield "\U0001f44f" + token
        else:
            yield token

runnable = chant_chain | character_generator
assert type(runnable.last) is RunnableGenerator
"".join(runnable.stream({"topic": "waste"}))  # Reduce👏, Reuse👏, Recycle👏.
```

### RunnableEach — Each 运行单元

该部分底层用到的是 asyncio 的 gather 方法，然后遍历 `config`：

```python
class RunnableEachBase(RunnableSerializable[list[Input], list[Output]]):
    """Runnable that calls another `Runnable` for each element of the input sequence."""

    bound: Runnable[Input, Output]

    def _invoke(self, inputs, run_manager, config, **kwargs) -> list[Output]:
        configs = [
            patch_config(config, callbacks=run_manager.get_child()) for _ in inputs
        ]
        return self.bound.batch(inputs, configs, **kwargs)
```

### RunnableLambda — 接入单元

RunnableLambda 的核心就是把普通函数包装成 Runnable 对象，让它具备统一接口：invoke/ainvoke/batch/stream，并能参与 `|` 链式组合、配置。

### Runnable 大总结

Runnable 的 base 是 langchain 这个项目核心中的核心，其定义了 langchain 中可执行对象 Runnable 所有的行为以及组合方式（运行方式）：Sequence 和 Map/Parallel，即顺序执行和并发执行。

LangChain 该部分的设计哲学：

1. 通过高度抽象的继承等方法，将所有的执行体（chain）组合成 Runnable 对象，便于统一性的处理结果。
2. 高度解耦，例如 initialize，完全依赖了 pydantic 模型，也就意味着完全和执行方法进行了解耦，这样就便于参数和状态的改变，同时使用 config/callback 上下文和递归执行语义，实现上下文的低度耦合。
3. 缺点：抽象程度太高了，也太深，分支也太多了。不同类型的需求，比如并发、顺序、迭代等，会经过好几个 patch，感觉不是很必要，而且看代码累个半死。但是组合能力上挺强的，避免了高度的耦合设计，总觉得对 agent 来说，是个复杂的设计。因为 agent 只是个无限循环，直到完成用户任务的工具，这么复杂的设计，没有必要。

---

## Messages — 消息协议

消息里和其他组件一样，继承了 BaseMessage，并且规定了基础的 Message 参数以及序列化等。

### BaseMessage 核心字段

```python
content: str | list[str | dict]
"""The contents of the message."""

additional_kwargs: dict = Field(default_factory=dict)
"""Reserved for additional payload data associated with the message."""

response_metadata: dict = Field(default_factory=dict)
"""Examples: response headers, logprobs, token counts, model name."""

type: str
"""The type of the message. Must be a string that is unique to the message type."""

name: str | None = None
"""An optional name for the message."""

id: str | None = Field(default=None, coerce_numbers_to_str=True)
```

### 类层次

BaseMessage 在大类上设计了二类：`BaseMessage` 与 `BaseMessageChunk`，对应单条消息和多组 BaseMessage 子集消息集合。除此之外没有别的了，基本就是消息的合并转化。

### 设计思考

写法感觉是有点遗留设计的意思，但是又感觉像故意这么设计的。并非目的性的质疑，而是 for 循环略慢，但是他这个又是没法避免的，为了适配多家模型，for 循环一步一步整理。后续他又推出了一堆 `langchain-xxx`，估计也是性质的设计，毕竟还有那种普适方法。

### 消息格式转换流水线

```python
from langchain_core.messages.block_translators.anthropic import (
    _convert_to_v1_from_anthropic_input,
)
from langchain_core.messages.block_translators.bedrock_converse import (
    _convert_to_v1_from_converse_input,
)
from langchain_core.messages.block_translators.google_genai import (
    _convert_to_v1_from_genai_input,
)
from langchain_core.messages.block_translators.langchain_v0 import (
    _convert_v0_multimodal_input_to_v1,
)
from langchain_core.messages.block_translators.openai import (
    _convert_to_v1_from_chat_completions_input,
)
```

消息的转化经过了以下五个工序：

```python
for parsing_step in [
    _convert_v0_multimodal_input_to_v1,
    _convert_to_v1_from_chat_completions_input,
    _convert_to_v1_from_anthropic_input,
    _convert_to_v1_from_genai_input,
    _convert_to_v1_from_converse_input,
]:
```

#### 第一步：`_convert_v0_multimodal_input_to_v1`（旧格式兼容）

分为两个方法：`_convert_legacy_v0_content_block_to_v1` 和 `_convert_v0_multimodal_input_to_v1`。基础的逻辑是将初始的所有类型消息，无论是 text or image or something else，将其分开包裹，其中包括消息类型、格式、extra 等。

有几个点很有意思：

1. `_convert_v0_multimodal_input_to_v1` 判断了双层的：
   ```python
   if block_type not in {"image", "audio", "file"} or "source_type" not in block:
       # Not a v0 format block, return unchanged
       return block
   ```
   估计是一种防御性质的写法，毕竟是 legacy 了。

2. 当存在 img 内容时，source 会有一个 id 的情况，估计是传图是一种 text 的方式的时候，会有这情况。

总体也说明了 V1 的 Messages 格式包含的都是 `xxxContentBlock` 的实例，基本处理对象也只有 img, file, audio 三种类型。

#### 第二步：`_convert_to_v1_from_chat_completions_input`（OpenAI 格式兼容）

这是对于模型产生结果的兼容。对于已经清理好的 langchain v1 的 message，先走一段 `is_openai_data_block` 方法。总之要满足符合 OpenAI 的格式，image 文件需要 block 的顶级字段符合 `{"type", "image_url", "detail"}`，同时 `image_url` 需要是 dict，且 `url` 必须是 str。file 和 audio 倒是简单一点。完事走了 `_convert_openai_format_to_data_block` 将 OpenAI 的格式转为 v1，然后将非 v1 的消息关键字下沉到 nonstandard。

#### 第三步~第五步：Anthropic / Google / AWS 格式适配

后续三个都是为了适配 Anthropic、Google、AWS 的格式了。

### SystemMessage 与 HumanMessage

这俩基本上单纯继承了 BaseMessage，没做其他特别修改，所有操作基本从父类拿。

### AIMessage 与 ToolMessage

AI Message 是最最最核心的部分，Agent 运行的上下文基本都是这里的产出，主要分为五类。

#### InputTokenDetails / OutputTokenDetails / UsageMetadata

定义了 Token 消耗的元数据结构。

#### AIMessage

这里定义了三个主要参数：`tool_call`、`invalid_toolcall`、`usage_metadata`。有效/无效的 toolcall 以及 token 消耗的元数据。

其返回了两个 attr，都是 tool 相关的。`content_blocks` 这里编排了 AI 相关的内容，如果消息的返回内容符合 v1 格式，直接返回 v1 定义的各种 `xxContentBlock`。不符合就会走 `get_translator`，`get_translator` 注册了基本各个大厂商的模型，并且提供了从各个厂商转接回 v1 格式的中间件。

而对于 toolcall，AI Message 两手措施：一个是 tool call，一个是 content。所以在 content block 加上了 tool call 的失败或者错漏的问题。

还有一个很奇怪的问题：如果你开启了 `enable reasoning`，它会把 reasoning 放到最前面。

```python
has_reasoning = any(block.get("type") == "reasoning" for block in blocks)
if not has_reasoning and (
    reasoning_block := _extract_reasoning_from_additional_kwargs(self)
):
    blocks.insert(0, reasoning_block)

return blocks
```

我 debug 了一下，发现确实在前面。我猜这可能是一种语义上的约定。通常我们人类做事都会先 reasoning，先想好应该怎么做，然后再决定下一步。这就跟炒菜似的：做菜之前先想好怎么做，然后再去准备油、盐、醋。

#### AIMessageChunk（流式输出）

AI Message Chunk 其实是一个比较特殊的东西。你可以这样理解：在输出时本质上只有 AI Message 这一种对象，所以当它进行流式输出（Streaming）时，系统会将 AI Message 打碎，以 AI Chunk 的方式进行输出。

这个机制的作用主要体现在两个方面：
1. **前端 UI 界面**：用户可以看到内容逐字跳出的流式变化。后端基本上都可以看到 message、tool name 的 message、tool arguments 这些东西全都可以看到。
2. **本地工具执行**：工具的执行（Tool Call）必须等 AI Chunk 全部输出完毕。后端在拼接好完整的 Tool Call 参数后，才会正式触发工具的执行。`chunk_position` 参数其实也是代表这个意思。它也会在纯粹的 Tool Call 场景下，对其进行标准化的 format。

AIMessageChunk 有一个特定的处理方法，因为它涉及到流式输出，所以需要连续 add 到初始的 message list 里面，不然也没法拼成一个整体的有效片段。

#### ToolMessages & ToolMessagesChunk & ToolCall & ToolCallChunk

作为 AIMessages 的下位组件，承担着解耦和工具信息的聚合作用。Toolcall 的基本元素应该包括了 Tool 的 name, id, args。ToolCallChunk 也是应用于 stream 场景下，连续输出时 Tool 消息的载体。

#### Content

`content.py` 中集中定义了消息内容类：

| 类名 | 说明 |
| :--- | :--- |
| `Citation` | 引用 |
| `NonStandardAnnotation` | 非标准注解 |
| `TextContentBlock` | 文本内容块 |
| `ToolCall` | 工具调用 |
| `ToolCallChunk` | 工具调用块 |
| `InvalidToolCall` | 无效工具调用 |
| `ServerToolCall` | 服务端工具调用 |
| `ServerToolCallChunk` | 服务端工具调用块 |
| `ServerToolResult` | 服务端工具结果 |
| `ReasoningContentBlock` | 推理内容块 |
| `ImageContentBlock` | 图片内容块 |
| `VideoContentBlock` | 视频内容块 |
| `AudioContentBlock` | 音频内容块 |
| `PlainTextContentBlock` | 纯文本内容块 |
| `FileContentBlock` | 文件内容块 |
| `NonStandardContentBlock` | 非标准内容块 |

源码中的类型别名：

```python
Annotation = Citation | NonStandardAnnotation

DataContentBlock = (
    ImageContentBlock
    | VideoContentBlock
    | AudioContentBlock
    | PlainTextContentBlock
    | FileContentBlock
)

ToolContentBlock = (
    ToolCall | ToolCallChunk | ServerToolCall | ServerToolCallChunk | ServerToolResult
)

ContentBlock = (
    TextContentBlock
    | InvalidToolCall
    | ReasoningContentBlock
    | NonStandardContentBlock
    | DataContentBlock
    | ToolContentBlock
)
```

---

## Prompts

Prompt 是模型的输入（Prompt is input of the model），Prompt 是由多个组件和 Prompt Value 构成的开放结构（Prompt is open construct for multiple components and prompt values）。Prompt 的类及其函数是为了让构建和处理 Prompt 变得更加简单。

Prompt 大类的设计，目前来说集中了以下内容，但本质上很多内容感觉是没用的。

大体上目前来说，集成了 AI 的：
1. Message
2. Chat Message Prompt
3. Chat Prompt Template
4. Human Message Prompt
5. Message Placeholder
6. System Message Prompt

主要是集中在一些这样的场景，比如 Chat、Dict、Few-shot 这种场景下，集成了很多个 Prompt 类型。

拿 AI Message 来说，你可以看到它集成了：
1. Tool Call
2. Invalid Tool Call
3. Usage Metadata

这些东西是能够去获取到 AI 执行的一些状态，最主要的就是 message placeholder，至于 prompt template 甚至都不重要。还是 message placeholder 比较重要。更多地应该是去学到它这个 prompt 在整个 agent loop 的环节下，到底会产生一个什么样的作用。

---

## Language Models — 模型抽象层

> 本模块定义了 LangChain 中所有语言模型的标准接口。无论是 OpenAI、Anthropic、Qwen 还是本地模型，都必须遵循这套协议。

### 继承链

```text
Runnable[Input, Output]                  ← 万物基类（统一调用协议）
    │
RunnableSerializable[Input, Output]      ← 加入序列化能力
    │   └── 继承了 Serializable（存盘/读盘）
    │   └── 继承了 Runnable（invoke/stream/batch）
    │
BaseLanguageModel[LanguageModelOutputVar] ← 基础定义输入输出泛型
    │
    └── BaseChatModel                     ← 聊天模型（输入消息列表，输出 AIMessage）
        │
        └── BaseChatOpenAI                ← OpenAI 聊天模型
            │
            ├── ChatOpenAI                ← GPT-4 等
            └── AzureChatOpenAI           ← Azure 部署
```

### 核心概念

#### BaseLanguageModel — Model 的基基类

定义了模型所需的固定行为以及部分参数，比如 `generate`——prompt 的行为以及一些 cache 以及 token 相关。

```python
class BaseLanguageModel(RunnableSerializable[LanguageModelInput, LanguageModelOutputVar], ABC):
```

- `LanguageModelInput` — 输入类型，支持 `str`、`list[BaseMessage]`、`PromptValue`
- `LanguageModelOutputVar` — 输出类型，被约束为 `AIMessage` 或 `str`

#### BaseChatModel — 所有 langchain 的适配都是走这个

```python
class BaseChatModel(BaseLanguageModel[AIMessage], ABC):
```

- 输出类型固定为 `AIMessage`
- 和其他方法一样提供了异步和同步的方法

由于 Python 本身的问题，只说异步的（反正异步也是同步改过来的）。它异步生成的这一套经过特别复杂的过程，基本上是套了 N 多层的路径，导致了这么慢的执行速度。

#### RunnableSerializable

```python
class RunnableSerializable(Serializable, Runnable[Input, Output]):
```

---

## Tools — 工具接口

### BaseTool

```python
name: str
description: str
args_schema: Annotated[ArgsSchema | None, SkipValidation()] = Field(
    default=None, description="The tool schema."
)
return_direct: bool = False
# True 的时候调用后会直接结束 AgentExecutor 的循环
verbose: bool = False  # 日志

callbacks: Callbacks = Field(default=None, exclude=True)
tags: list[str] | None = None
metadata: dict[str, Any] | None = None
handle_tool_error: bool | str | Callable[[ToolException], str] | None = False
handle_validation_error: (
    bool | str | Callable[[ValidationError | ValidationErrorV1], str] | None
) = False
response_format: Literal["content", "content_and_artifact"] = "content"
extras: dict[str, Any] | None = None
```

### InjectedToolArg & InjectedToolCallId & BaseToolkit

运行时注入的工具参数，Tool arguments annotated with this class are not included in the tool schema sent to language models and are instead injected during execution。

---

## Callbacks — 贯穿模型输出期间的行为

回调包括：

- `on_chat_model_start`
- `on_llm_start`
- `on_llm_new_token`
- `on_llm_end`
- `on_llm_error`

主要是可以在这里埋点，比如日志之类的，但是最主要的还是追踪 token 生成期间的行为，这一点还是比较重要。

---

## Output Parsers — 输出解析器

### BaseLLMOutputParser

定义了模型结果解析的抽象类。所有基类都要实现自己的 `parse_result` 方法，根据返回的 Generation 块，生成结构化的 output。

### BaseGenerationOutputParser

Generation 输出解析器的基类。

### Outputs 子模块

#### Generation 与 GenerationChunk

`Generation` 定义了生成消息的基本属性，依旧属于可 Serializable 的对象。

`GenerationChunk` 是模型生成内容的最小单位，其定义了 `add` 方法，可以把所有 Chunk 拼接起来后重新返回 GenerationChunk。

#### ChatGeneration 与 ChatGenerationChunk

`ChatGeneration` 是单次对话生成的内容，兼容了 deprecated 的消息格式，初始化后填充信息。

`ChatGenerationChunk` 合并多轮的 GenerationChunk。

#### ChatResult

代表单次的 prompt 触发后的模型输出结果。

```text
Use to represent the result of a chat model call with a single prompt.
```

#### LLMResult

存储模型触发回答的一系列的 List，基本也是模型输出的下游任务处理。

### 设计思考

以上作为消息生成的基建类包，承载了模型输出后的格式规定以及内容上的编排，output 负责结果的生成，等任务逐渐走向下游的具体类中时，这些才会真正发挥作用。但是其定义总觉得有些过头的地方。

LangChain 在设计的时候，Generation 集成了基础属性、内容、names 以及 Serializable 那一套的属性。GenerationChunk 作为基础性质的容器，负责将多个 Generation 进行集成为一整个 chunk。同时又定义了 ChatGeneration 以及 ChatGenerationChunk 这个 more Specific 一点的，用于集成 LLM 输出的、经由 langchain 的 msg 格式化的 BaseMessages 及其子类的（HumanMessage, AIMessage, SystemMessages）等消息。

LLMResult 以及 generation、generationchunk 反倒觉得有些遗留设计的问题。因为 Generation 本身的内容除了承载输出单元的属性定义以外，是有点不符合的，ChatGeneration 才是更符合当前对话消息输出的设计方案。

---

## Load — 序列化/反序列化

这里定义了 langchain 的核心行为之一，即 `Serializable`。它实现了 langchain 对象的在模型输入输出的序列化和反序列化，并且给出了大量的解释，为何要这么设计，序列化和反序列化时的所要注意的问题。

### Reviver

和 Serializable 是一对，负责 lc 对象的恢复，涉及到 langchain 运行周期的各个方面。

### Serializable

#### Mapping

这里规定了所有的可序列化/反序列化相关规定的 langchain 命名空间，兼容了一堆老包。比如说那个 serializable mapping，它会把以前的 `langchain.schema.messages.ai_messages` 映射到 `langchain.core.messages.ai_messages`。而且这也是现在的包裡的结构，它已经不是以前那样了。剩下的基本上都是这样的 repeat 操作了。

#### Validators

大概就是针对亚马逊单独适配的一个东西，详细的定义了 lc 的序列化和反序列化的核心内容。在 LangChain 里面，基本上所有的 Runnable 对象都会有这些属性。也就是说，在 Runnable 的定义中，LangChain 不只是分了三层，而是分了四五层这样的继承，只觉得很繁琐吧。

#### Serializable Details

**Is langchain serializable** (`is_lc_serializable`)：langchain 官方提到，对于其基础的 langchain-core 包，它可以完全信任地将你提供的 JSON 串还原成 langchain 所专属的一个类。但对于一些外来的、不属于其核心包的内容，它就不会进行反序列化。官方给出的理由是可能会发生网络连接异常等问题，但其实最主要的核心考量还是为了防投毒。

**Get LangChain namespaces** (`get_lc_namespace`)：这个方法是序列化和反序列化的一个钩子。当你序列化的时候，会用它来生成包所在的路径并作为它的 ID；而在反序列化的时候，也会通过这个 Class Path 去将它还原为某类的一个实例。

**lc_secrets**：LangChain 的 BaseModel 里面代指 API Key 的东西。当你看到 OpenAI 的这一部分，不管是写成 `openai_api_key` 还是别的什么，反正指的就是这些东西，加载的就是这些玩意儿。

**lc_attributes**：一些其他的参数，序列化的时候需要用的参数。

**lc_id**：跟 `get_lc_namespace` 差不多，是生成类的标识。

**to_json**：序列化的时候会有一个判断 `_is_field_useful`，检查字段是否作为构造参数有用。序列化时，会从整个继承树去进行 secret key 的挂载和查找。从 MRO 拿到继承树上的所有内容，从底往上开始排，获取到定义的 secret key，再继续整合到 LangChain 的 `lc_kwargs` 里面。

思考：序列化和反序列化时为什么没有直接把 secret key 放到类属性里面一起进行序列化？后来看了 Reviver 的实现，发现他那边又专门定义了一个字段叫做 `secrets_from_env`：

> "Only include specific secrets that serializable objects require. If a secret is not found in the map, it will be loaded from environment."

因为你在处理的时候，一般就是 `secret_from_env`。对于 false 的话，只传 `secret_map`，然后这样就可以避免恶意地去加载。

**最重要的一点：要注意序列化和反序列化的安全问题。**

---

## Documents — 文档与 RAG 基础单元

### BaseMedia

RAG 检索和处理（str）数据的基本定义单位，但不适用多模态的情况。由于 Retrieval 在发展初期的碎片性，导致其必定是一块一块的。

### Blob

一般是 Python 有个基类，这是文件加载中的初始最小原始单位。

### Document

```python
class Document(BaseMedia):
    """Class for storing a piece of text and associated metadata.

    !!! note
        `Document` is for **retrieval workflows**, not chat I/O. For sending text
        to an LLM in a conversation, use message types from `langchain.messages`.

    Example:
        ```python
        from langchain_core.documents import Document

        document = Document(
            page_content="Hello, world!", metadata={"source": "https://example.com"}
        )
        ```
    """
```

这个我熟，以前刚做 RAG 处理，拆分后的字段加原始数据直接拆分后进行处理就完事了。

### BaseDocumentCompressor

文档的后处理方式抽象类。

### BaseDocumentTransformer

文件转换的抽象类。

---

## Embeddings — 嵌入模型接口

只是定义了 Embedding 层面的简单行为。

```text
langchain_core.Embeding
├── Embeddings  ← 只是定义了 Embedding 层面的简单行为
```
