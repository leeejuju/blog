---
title: "源码阅读: langchain-core"
description: "langchain-core 是 LangChain 的核心包。(之前)"
pubDate: 2026-03-10
section: framework
categories:
  - langchain
---

# LangChain-Core

> `langchain-core` 是整个 LangChain 所有的基本行为的抽象集合，定义了所有agent组件的调用标准协议，但是你让我用这玩意上工程，或许之前我会，但是现在就算了。
> 所有其他包（`langchain`、`langgraph`、`langchain-openai` 等）都依赖它，但它不依赖任何人。

> 以下全是 ****纯手打 + Typeless 口喷****

---

## 📦 模块总览

```
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

## langchain 核心包

### **1. callback**

即贯穿模型输出期间的行为：

1. **`on_chat_model_start`** — chat model 开始调用时触发，携带输入的 messages 和 invocation params
2. **`on_llm_start`** — LLM 开始生成时触发，携带 prompt 和 invocation params（chat model 也会触发此事件）
3. **`on_llm_new_token`** — 流式生成中每产生一个新 token 时触发，是 token-level 追踪的核心钩子
4. **`on_llm_end`** — LLM 生成完成时触发，携带完整的生成结果（ChatResult / LLMResult）
5. **`on_llm_error`** — LLM 调用出错时触发，携带异常信息，用于重试/降级/告警

主要是可以在这里埋点，比如日志、token 计数、延迟监控之类的。

但是我认为最主要的还是追踪 token 生成期间的行为（`on_llm_new_token`），这一点还是比较重要。

### **2. langchain_core.document**

#### 2.1 BaseMedia

官方是这么说的，RAG检索和处理（str）数据的基本定义单位，但是不适用多模态的情况。由于 Retrieval 在发展初期的的碎片性，所以导致其必定是一块一块的

#### 2.2 Blob

一般是py有个基类，这是文件加载中的初最小原始单位

#### 2.3 Document

````python
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
````

这个我熟，以前刚做RAG处理，拆分后的字段+原始数据直接拆分后进行处理就完事了。

#### 2.4 BaseDocumentCompressor

文档的后处理方式抽象类，后面用到再说

#### 2.5  BaseDocumentTransformer

文件转换的抽象类，后面看到会给穿起来

### **3. langchain_corE.Embeding**

#### 3.1 Embeddings

只是定义了 Embeding层面的简单行为

### **4. langchain_core indexing part**

整个类我怎么没咋见过其实。按下不表先

#### 4.1 RecordManager

### **5. Language Models ⭐⭐**

> 模型抽象层
> 本模块定义了 LangChain 中所有语言模型的标准接口。
> 无论是 OpenAI、Anthropic、Qwen 还是本地模型，都必须遵循这套协议。

#### 5.1 Language Models 继承链

``` markdown
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

#### 5.2 `BaseLanguageModel`

Model的基基类，定义了模型所需的固定行为以及部分参数

比如generate——prompt的行为以及一些cache以及token相关 (cache行为后面再说，相当重要的知识点)

```python
class BaseLanguageModel(RunnableSerializable[LanguageModelInput, LanguageModelOutputVar], ABC):
```

- `LanguageModelInput` — 输入类型，支持 `str`、`list[BaseMessage]`、`PromptValue`
- `LanguageModelOutputVar` — 输出类型，被约束为 `AIMessage` 或 `str`

#### 5.3 `BaseChatModel`

模型基类，所有 langchain 的适配都是走这个

```python
class BaseChatModel(BaseLanguageModel[AIMessage], ABC):

这里由于 Python 本身的问题，只说异步的，反正异步也是同步改过来的，他异步生成的这一套经过的特别复杂的过程

ps: py 的 AgentSDK 太麻烦，我真他妈被折磨的不行。

我只说ainvoke 和 astream这部分。

基本上是套了 N 多层的路径，导致了这么慢的执行速度，草泥马

```

- 输出类型固定为 `AIMessage`
- 和其他方法一样提供了异步和同步的方法

### **6.langchain_core load part**

这里定义了 langchain 的核心行为之一，即 Serializable 它实现了langchain对象的在模型输入输出的序列化和反序列化，尤其重要的一点

并且给出了大量的解释，为何要这么设计，序列化和反序列化时的所要注意的问题

#### 6.1 Reviver

和 Serializable 是一对，负责 lc 对象的恢复，涉及到 langchain 运行周期的各个方面

#### 6.2 Serializable

##### 6.2.1 mapping

这里规定了所有的可序列化/反序列化相关规定的  langchain 命名空间
兼容了一堆老包,  比如说那个 serializable mapping，它会把以前的 langchain.schema.messages.ai_messages 映射到 langchain.core.messages.ai_messages。而且这也是现在的包里边的结构，它已经不是以前那样了
然后剩下的基本上都是这样的 repeat 操作了

##### 6.2.2 validators

我看了一下，大概就是针对亚马逊单独适配的一个东西，我估计之前发生过什么问题
这个详细的定义了lc的序列化和反序列化的核心内容,在 LangChain 里面，基本上所有的 Runnable 对象都会有这些属性。也就是说，在 Runnable 的定义中，LangChain 不只是分了三层，而是分了四五层这样的继承,我只觉得很繁琐吧

#### 6.3 Serializable Details

这里我会详细说一下 LangChain 的序列化和反序列化的一个行为,比如 Serializable，其实可以看到它那个基础的属性有

##### 6.3.1 Is langchain serializable （is_lc_serializable）

这一属性就跟我们之前看到的 langchain 里面规定的序列化和反序列化的规定对应上了。

langchain 官方提到，对于其基础的 langchain-core 包，它可以完全信任地将你提供的 JSON 串还原成 langchain 所专属的一个类，从而方便地使用。

但对于一些外来的、不属于其核心包的内容，它就不会进行反反序列化。官方给出的理由是可能会发生网络连接异常等问题，但其实最主要的核心考量还是为了防投毒。

##### 6.3.2 Get LangChain namespaces

 (get_lc_namespace)

``` python
    @classmethod
    def get_lc_namespace(cls) -> list[str]:
        """Get the namespace of the LangChain object.

        The default implementation splits `cls.__module__` on `'.'`, e.g.
        `langchain_openai.chat_models` becomes
        `["langchain_openai", "chat_models"]`. This value is used by `lc_id` to
        build the serialization identifier.

        New partner packages should **not** override this method. The default
        behavior is correct for any class whose module path already reflects
        its package name. Some older packages (e.g. `langchain-openai`,
        `langchain-anthropic`) override it to return a legacy-style namespace
        like `["langchain", "chat_models", "openai"]`, matching the module
        paths that existed before those integrations were split out of the
        main `langchain` package. Those overrides are kept for
        backwards-compatible deserialization; new packages should not copy them.

        Deserialization mapping is handled separately by
        `SERIALIZABLE_MAPPING` in `langchain_core.load.mapping`.

        Returns:
            The namespace.
        """
        return cls.__module__.split(".")
```

这个方法是序列化和反序列化的一个钩子。当你序列化的时候，会用它来生成包所在的路径，作为它的 ID；
而在反序列化的时候，也会通过这个 Class Path 去将它还原为某类的一个实例。

``` python
@property
def lc_secrets(self) -> dict[str, str]:
```

LC_SECRET 其实你可以看到，它就是 LangChain 的 BaseModel 里面代指 API Key 的东西。当你看到 OpenAI 的这一部分，不管是写成 openai_api_key 还是别的什么，反正指的就是这些东西，加载的就是这些玩意儿。
在初始化的时候，你会往里填，这个其实没什么好说的

``` python
@property
def lc_attributes(self) -> dict:
```

 lc_attributes 其实是一些其他的参数，就是一些序列化的时候需要用的参数。也没什么好说的，不是什么重要的东西

``` python
@classmethod
def lc_id(cls) -> list[str]:这玩意儿其实跟 generate_namespace 差不多，它其实是生成类的一个标识
```

``` python
def to_json(self) -> SerializedConstructor | SerializedNotImplemented:
        """Serialize the object to JSON.

        Raises:
            ValueError: If the class has deprecated attributes.

        Returns:
            A JSON serializable object or a `SerializedNotImplemented` object.
        """
        if not self.is_lc_serializable():
            return self.to_json_not_implemented()

        model_fields = type(self).model_fields
        secrets = {}
        # Get latest values for kwargs if there is an attribute with same name
        lc_kwargs = {}
        for k, v in self:
            if not _is_field_useful(self, k, v):
                continue
            # Do nothing if the field is excluded
            if k in model_fields and model_fields[k].exclude:
                continue

            lc_kwargs[k] = getattr(self, k, v)

        # Merge the lc_secrets and lc_attributes from every class in the MRO
        for cls in [None, *self.__class__.mro()]:
            # Once we get to Serializable, we're done
            if cls is Serializable:
                break

            if cls:
                deprecated_attributes = [
                    "lc_namespace",
                    "lc_serializable",
                ]

                for attr in deprecated_attributes:
                    if hasattr(cls, attr):
                        msg = (
                            f"Class {self.__class__} has a deprecated "
                            f"attribute {attr}. Please use the corresponding "
                            f"classmethod instead."
                        )
                        raise ValueError(msg)

            # Get a reference to self bound to each class in the MRO
            this = cast("Serializable", self if cls is None else super(cls, self))

            secrets.update(this.lc_secrets)
            # Now also add the aliases for the secrets
            # This ensures known secret aliases are hidden.
            # Note: this does NOT hide any other extra kwargs
            # that are not present in the fields.
            for key in list(secrets):
                value = secrets[key]
                if (key in model_fields) and (
                    alias := model_fields[key].alias
                ) is not None:
                    secrets[alias] = value
            lc_kwargs.update(this.lc_attributes)

        # include all secrets, even if not specified in kwargs
        # as these secrets may be passed as an environment variable instead
        for key in secrets:
            secret_value = getattr(self, key, None) or lc_kwargs.get(key)
            if secret_value is not None:
                lc_kwargs.update({key: secret_value})

        return {
            "lc": 1,
            "type": "constructor",
            "id": self.lc_id(),
            "kwargs": lc_kwargs
            if not secrets
            else _replace_secrets(lc_kwargs, secrets),
        }
```

然后这里边可以说的就是一个 to_json 的方法，它那个 signature 写的是：

1. Serialize the object to JSON
2. Raise value if class has deprecated attributes
3. Or return a JSON-realizable object
4. Or serialize non-serializable object

然后他那个叫 _is_field_useful ，就是 to_json 序列化的时候它序列化的时候会有一个判断，即 field is useful。他原文写的是：checking the field is useful as a constructor argument。

也就是说，它是作为序列化的时候，判断这个参数对于 constructor 是否有用。因为有的字段是不参与到序列化中的

其次 to_json 他去序列化的时候，有一个比较值得注意的东西：他会从整个继承树去进行 secret key 的挂载和查找
因为 LC 的 namespace 以及 LC 的 Serializable，这两个参数已经 deprecated 了

``` python
for cls in [None, *self.__class__.mro()]:
            # Once we get to Serializable, we're done
            if cls is Serializable:
                break
```

它基本上是这样一个逻辑：从 MRO 拿到继承树上的所有内容，然后从底往上开始排，获取到定义的 secret key，再继续整合到 LangChain 的 lc_Kwargs 里面。

我一开始想的时候，就在思考他序列化和反序列化的时候，为什么没有直接把 secret key 放到类属性里面一起进行序列化。

后来看了 Reviver 的实现，发现他那边又专门定义了一个字段，叫做 secrets_from_env。他的解释是：
"Only include specific secrets that serializable objects require. If a secret is not found in the map(map 指的是 key:sk 的键值对), it will be loaded from environment."

因为你在处理的时候，一般就是 secret_from_env。对于 false 的话，只传 secret_map 嘛，然后这样的话你就可以避免恶意地去加载

### **7. LangChain Message**

#### 7.1 BaseMessage

消息基类message里和其他组件一样，继承了 BaseMessage，并且规定了基础的Message参数，以及序列化等一些玩意。

``` python
    content: str | list[str | dict]
    """The contents of the message."""

    additional_kwargs: dict = Field(default_factory=dict)
    """Reserved for additional payload data associated with the message.

    For example, for a message from an AI, this could include tool calls as
    encoded by the model provider.

    """

    response_metadata: dict = Field(default_factory=dict)
    """Examples: response headers, logprobs, token counts, model name."""

    type: str
    """The type of the message. Must be a string that is unique to the message type.

    The purpose of this field is to allow for easy identification of the message type
    when deserializing messages.

    """

    name: str | None = None
    """An optional name for the message.

    This can be used to provide a human-readable name for the message.

    Usage of this field is optional, and whether it's used or not is up to the
    model implementation.

    """

    id: str | None = Field(default=None, coerce_numbers_to_str=True)
```

比如这些等，这里就一一不表了

#### 7.2 BaseMessage & BaseMessageChunk

base在大类上设计了二类: BaseMessage 与 BaseMessageChunk，对应单条消息和多组BaseMessag子集消息集合

除此之外没有别的了，基本就是消息的合并转化，

#### 7.3 设计思考

除此之外，比较好奇的就是，我感觉写法是有点遗留设计的意思，但是又感觉像故意这么设计的
并非是目的性的质疑，而是for循环略慢，但是他这个又是没法避免的，为了适配多家模型，for循环一步一步整理

但是后续他又推出了一堆 langchain-xxx，估计也是性质的设计，毕竟，还有那种普适方法

#### 7.4 消息格式转换流水线

```python
from langchain_core.messages.block_translators.anthropic import (  # noqa: PLC0415
    _convert_to_v1_from_anthropic_input,
)
from langchain_core.messages.block_translators.bedrock_converse import (  # noqa: PLC0415
    _convert_to_v1_from_converse_input,
)
from langchain_core.messages.block_translators.google_genai import (  # noqa: PLC0415
    _convert_to_v1_from_genai_input,
)
from langchain_core.messages.block_translators.langchain_v0 import (  # noqa: PLC0415
    _convert_v0_multimodal_input_to_v1,
)
from langchain_core.messages.block_translators.openai import (  # noqa: PLC0415
    _convert_to_v1_from_chat_completions_input,
)
```

以上消息类型的转化，基本上

```python
for parsing_step in [
    _convert_v0_multimodal_input_to_v1,
    _convert_to_v1_from_chat_completions_input,
    _convert_to_v1_from_anthropic_input,
    _convert_to_v1_from_genai_input,
    _convert_to_v1_from_converse_input,
]:
```

消息的转化经过了以上五个工序

##### 第一步：_convert_v0_multimodal_input_to_v1（旧格式兼容）

这部分是初步的过滤，分为俩方法，

_convert_legacy_v0_content_block_to_v1
以及
_convert_v0_multimodal_input_to_v1

基础的逻辑上是将

符合他的名字，是将初始的所有类型消息，无论是 text or image or something else,
将其分开包裹，其中包括消息类型，格式，extra等

而且有几个点很有意思

1. 就是_convert_v0_multimodal_input_to_v1 判断了双层的，我估计是一种防御性质的写法？毕竟是legacy了？

``` python
   if block_type not in {"image", "audio", "file"} or "source_type" not in block:
       # Not a v0 format block, return unchanged
        return block
```

2. 当存在img内容时， source会有一个 id 的情况， 这个我调试的时候没太遇见，我估计是传图是一种，text的方式的时候，会有这情况总体，也说明了V1 的 Messages 格式，包含的都是 xxxxContentBlock 的实例

基本处理对象也只有 img，file, audio 三种类型

##### 第二步：_convert_to_v1_from_chat_completions_input（OpenAI 格式兼容）

这是对于模型产生结果的兼容，比如之前国内特别多的厂商走的都是 OpemAI的格式，现在走 Anthropic 的也多,对于已经清理好的信息 langchain v1 的 message
先走一段 is_openai_data_block 方法

方法具体我就不提供了

总之要满足符合 OpenAI 的格式，image 文件，需要block 的顶级字段符合 {"type", "image_url", "detail"},同时 iamge_url 需要是 dict, 且 url 必须是 str .

file 和 audio 倒是简单一点，

完事走了 _convert_openai_format_to_data_block 将 OpenAI 的格式，转为 v1

然后将非 v1 的消息关键字下沉到 nostandard

##### 第三步: 第五步：Anthropic / Google / AWS 格式适配

后续三个都是为了适配 Anthropic, Google, AWS的格式了，不再一一详述

#### 7.5 SystemMessage 与 HumanMessage

这俩基本上单纯继承了 BaseMessage 然后没做其他的特别修改而已，

这里就跳过了先，所有的操作基本是从父类拿

#### 7.6 AIMessage 与 ToolMessage

AI msg 是最最最核心的部分，Agent运行的上下文，基本都是这里的产出

其主要分为了五类

##### 7.6.1 InputTokenDetails / OutputTokenDetails / UsageMetadata

1. InputTokenDetails

2. OutputTokenDetails

3. UsageMetadata

##### 7.6.2 AIMessage

AIMessage

这里定义了三个主要参数

tool call、invalid_toolcall, usage_metadata
顾名思义，有效/无效的toolcall 以及 token消耗的元数据，

其返回了俩 attr , 都是 tool 相关的， 剩下的就是，content_blocks 这里编排了 AI 相关的内容， 

如果消息的返回内容，符合 v1 格式，直接返回 v1 定义的各种 xxContentBlock

不符合就会走，get_translator，

get_translator 注册了基本各个大厂商的模型，并且提供了，从各个厂商转接回 v1 格式的中间件

然后通过中间件把 AIMessage 转出去，前提是 Response 了模型厂商，而且是得集成了Translator

而对于 toolcall AI message 两手措施，一个是 tool call 一个是content，所以在content block 加上了 tool call的失败或者错漏的问题

还有一个很奇怪的问题，就是如果你开启了 enable reasoning，它会把 reasoning 放到最前面。

``` python
   has_reasoning = any(block.get("type") == "reasoning" for block in blocks)
   if not has_reasoning and (
       reasoning_block := _extract_reasoning_from_additional_kwargs(self)
   ):
       blocks.insert(0, reasoning_block)

return blocks
```

我 debug 了一下，发现确实在前面。我猜这可能是一种语义上的约定。通常我们人类做事都会先 reasoning，先想好应该怎么做，然后再决定下一步。
这就跟炒菜似的：做菜之前先想好怎么做，然后再去准备油、盐、醋。这种行为逻辑应该是这样的。

##### 7.6.3 AIMessageChunk（流式输出）

``` python
class AIMessageChunk(AIMessage, BaseMessageChunk):
    """Message chunk from an AI (yielded when streaming)."""

    # Ignoring mypy re-assignment here since we're overriding the value
    # to make sure that the chunk variant can be discriminated from the
    # non-chunk variant.
    type: Literal["AIMessageChunk"] = "AIMessageChunk"  # type: ignore[assignment]
    """The type of the message (used for deserialization)."""

    tool_call_chunks: list[ToolCallChunk] = Field(default_factory=list)
    """If provided, tool call chunks associated with the message."""

    chunk_position: Literal["last"] | None = None
    """Optional span represented by an aggregated `AIMessageChunk`.

    If a chunk with `chunk_position="last"` is aggregated into a stream,
    `tool_call_chunks` in message content will be parsed into `tool_calls`.
    """
```

AI Message Chunk 其实是一个比较特殊的东西。

你可以这样理解：输出时本质上只有 AI Message 这一种对象，所以当它进行流式输出（Streaming）时，系统会将 AI Message 打碎，以 AI Chunk 的方式进行输出。

基本上，这个机制的作用主要体现在两个方面：

1. 前端 UI 界面：用户可以看到内容逐字跳出的流式变化。后端基本上都可以看到，比如说 message、tool name 的 message，还有 tool arguments，这些东西全都可以看到。
2. 本地工具执行：
    工具的执行（Tool Call）必须等 AI Chunk 全部输出完毕。后端在拼接好完整的 Tool Call 参数后，才会正式触发工具的执行。 chunk_position 的参数其实也是代表这个意思. 然后，它也会在纯粹的 Tool Call 场景下，对其进行标准化的 format

   但是你可以看到 AIMessageChunk 有一个特定的处理方法，因为它是涉及到流式输出的，所以需要连续add到初始的 message list 里面，不然也没法拼成一个整体的有效片段

##### 7.6.4 ToolMessages && ToolMessagesChunk && ToolCall && ToolCallChunk

作为 AIMessages 的下位组件，承担着解耦和工具信息的聚合作用

Toolcall的基本元素应该包括了 Tool 的 name, id, args.ToolCallChunk 也是应用于 stream 场景下，连续输出时 Tool 消息的载体

#### 7.7 Content

`content.py` 中集中定义了消息内容类：

1. `Citation`
2. `NonStandardAnnotation`
3. `TextContentBlock`
4. `ToolCall`
5. `ToolCallChunk`
6. `InvalidToolCall`
7. `ServerToolCall`
8. `ServerToolCallChunk`
9. `ServerToolResult`
10. `ReasoningContentBlock`
11. `ImageContentBlock`
12. `VideoContentBlock`
13. `AudioContentBlock`
14. `PlainTextContentBlock`
15. `FileContentBlock`
16. `NonStandardContentBlock`

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

嗯，因为所有的东西都是从第一性原理去看的，所以说这些不是特别重要的东西我都不看了，本身也是结合开发过程中所看到的一些东西去分析

以上所有内容由 Typeless 口述整理

### **8. langchain_core outparser**

模型输出结果规定的究极基类

#### 8.1 Base's BaseLLMOutputParser

定义了模型结果解析的抽象类，没啥好说的，只是所有基类都要实现自己的 parse_result 方法
根据返回的 Geration 块，生成结构化的 output .

#### 8.2 Base's BaseGenerationOutputParser

### 9. langchain_core output

#### 9.1 generation's Generation

定义了生成消息的基本属性，依旧是属于可Serilizable的对象

#### 9.2 generation's GenerationChunk

模型生成内容的最小单位，其定义了 add 方法，可以把所有 Chunk 拼接起来后重新返回 GenerationChunk

#### 9.3 chatgeneartion's ChatGeneration

单次对话生成的内容，兼容了 deprcated 的消息格式，初始化后填充信息

#### 9.4 chatgeneartion's ChatGenerationChunk

合并多轮的 GenerateChunk

#### 9.5 chat_result's ChatResult

原文是 Use to represent the result of a chat model call with a single prompt. 即代表单次的 prompt 触发后的模型输出结果，

#### 10. LLMResult

"A container for results of an LLM call. 也很简单，存储模型触发回答的一系列的 List .基本也是模模型输出的下游任务处理

以上作为消息生成的基建类pack，承载了模型输出后的格式规定以及内容上的编排，output负责结果的生成，等任务逐渐走向下游的具体类中时，这些才会这真正的发挥作用，

但是其定义总觉得有些过头的地方，langchain 在设计的时候，Generation 集成了基础属性，内容，names以及Serializeable那一套的属性, GenerateChunk 作为基础性质的容器,负责将多个 Generation 进行集成为一整个的chunk 。 

同时又定义了 ChatGeneration 以及 ChatGenerationChunk 这个 more Spesific 一点，用于集成 LLM 输出的，经由 langchain 的 msg 格式化的 BaseMessages 及其子类的（HumanMessage, AIMessage, SystemMessages）等消息。、

LLMResult以及generation， generationchunk 我反倒是觉得有些遗留设计的问道

因为Genertion本身的内容除了承载输出单元的属性定义以外，是有点不符合的，ChatGeration 才是更符合当前对话消息输出的设计方案

### 11. LangChain Prompt

"""    现在来看一下 Prompt 的介绍：

1. Prompt 是模型的输入 (Prompt is input of the model)
2. Prompt 是由多个组件和 Prompt Value 构成的开放结构 (Prompt is open construct for multiple components and prompt values)
3. Prompt 的类及其函数是为了让构建和处理 Prompt 变得更加简单 (Prompt classes and functions make construction and working with prompts easy)

大意上就是说，Prompt 这个类以及它的一些函数，就是为了让处理 Prompt 的过程更加简单。

现在来看一下 Prompt 大类的设计部分。目前来说，它还是集中了刚才以下的一些东西，但本质上我觉得很多内容是没有用的。

我来说一下为什么没有用啊。

因为在大体上看来，比如 Few-shot Prompt，本质上你是在 Prompt 里面提供一些 example。但为什么我要对此单独设计一个类呢？我觉得是没有必要的。

大体上目前来说，集成了 AI 的：

  1. Message
  2. Chat Message Prompt
  3. Chat Prompt Template
  4. Human Message Prompt
  5. Message Placeholder
  6. System Message Prompt

主要是集中在一些这样的场景，比如说是 Chat、Dict、Few-shot 这种场景下，集成了很多个 Prompt 类型。

拿 AI Message 来说的话，你可以看到它集成了：

1. Tool Call
2. Invalid Tool Call
3. Usage Metadata

这些东西是能够去获取到 AI 执行的一些状态最主要的就是 message placeholder，至于 prompt template 甚至都不重要（这句话可以删掉了），还是  message placeholder 比较重要。

我感觉更多地应该是去学到，它这个 prompt 在整个 agent loop 的环节下，到底会产生一个什么样的作用。

### 12. Runnables⭐⭐⭐⭐⭐

> LangChain 的核心协议
> `Runnable` 是 LangChain 的**绝对核心**，**且没有之一**。
> 无论是 Model、Tool、Prompt 还是 Parser，所有组件都实现了 `Runnable` 接口。
> LangChain 这样设计，我估计是有以下原因
>
> 1，为了不同的情况下，依旧能实现统一的调用方法，是高度抽象的设计。
> 2，这里吐槽一下，感觉是没有必要的东西，设计有点过于复杂

#### 12.1 runnables/base.py

``` markdown
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

##### 12.1.1 Runnable 🌟🌟🌟

第一部分：接口定义（超级重要）

##### 核心方法（4 类）

| 分类 | 方法 | 说明 |
| :--- | :--- | :--- |
| **执行** | `invoke` / `ainvoke` | 单次调用（同步/异步） |
| | `stream` / `astream` | 流式输出 |
| | `batch` / `abatch` | 批量并发 |
| | `transform` / `atransform` | 流式输入 → 流式输出 |
| **组合** | `__or__` (`|`) | 串行组合：`A \| B \| C` → `RunnableSequence` |
| | `pipe()` | 同上，方法调用版 |
| | `pick()` | 从 dict 输出中选 key |
| | `assign()` | 给 dict 输出添加新 key |
| | `⭐⭐⭐coerce_to_runnable()` | 组合所有继承自 `Runnable` 的对象，是组合核心 |
| **装饰** | `bind()` | 绑定默认参数（Agent 绑定工具的基础） |
| | `with_config()` | 绑定运行时配置 |
| | `with_retry()` | 失败自动重试 |
| | `with_fallbacks()` | 失败切换备用方案 |
| | `with_listeners()` | 添加生命周期钩子 |
| **内省** | `input_schema` / `output_schema` | 获取输入/输出的 Pydantic Schema |
| | `⭐⭐get_graph()` | 底层核心转向langGraph后的重要方法，主题用于生成和获取图结构 |

##### 一，ainvoke方法（这里都解说异步）

```python
# Runnable的invoke方法，即单个的任务

async def ainvoke(
        self,
        input: Input,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Output:
        """Transform a single input into an output.

        Args:
            input: The input to the `Runnable`.
            config: A config to use when invoking the `Runnable`.

                The config supports standard keys like `'tags'`, `'metadata'` for
                tracing purposes, `'max_concurrency'` for controlling how much work to
                do in parallel, and other keys.

                Please refer to `RunnableConfig` for more details.

        Returns:
            The output of the `Runnable`.
        """
        return await run_in_executor(config, self.invoke, input, config, **kwargs)
```

> ps:langchain 的异步方法设计中使用了大量的 asyncio 的 run_in_executor 方法，具体不说了，目的就是实现线程池去并发的处理任务而又不阻塞

##### 设计初衷

LangChain 早期各组件调用方式不统一 `Runnable` 的出现将**所有组件统一为同一套方案**，解决了以下问题：

Runnable 的源码为以下，但是太长了，这里按下不表，后续再说

```python
class Runnable(ABC, Generic[Input, Output]):
    """A unit of work that can be invoked, batched, streamed, transformed and composed.

    Key Methods
    ===========

    - `invoke`/`ainvoke`: Transforms a single input into an output.
    - `batch`/`abatch`: Efficiently transforms multiple inputs into outputs.
    - `stream`/`astream`: Streams output from a single input as it's produced.
    - `astream_log`: Streams output and selected intermediate results from an
        input.
    name: str | None
    """The name of the `Runnable`. Used for debugging and tracing."""
```

##### 12.1.1 **调用方法的统一** → 统一 `invoke`/`stream`/`batch`

##### 12.1.2 **泛型推断**

```python
@property
    def InputType(self) -> type[Input]:  # noqa: N802
           """Input type.
   
           The type of input this `Runnable` accepts specified as a type annotation.
   
           Raises:
               TypeError: If the input type cannot be inferred.
           """
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
           # then loop through __orig_bases__. This corresponds to
           # Runnables that are not pydantic models.
           for cls in self.__class__.__orig_bases__:  # type: ignore[attr-defined]
               type_args = get_args(cls)
               if type_args and len(type_args) == _RUNNABLE_GENERIC_NUM_ARGS:
                   return cast("type[Input]", type_args[0])
   
           msg = (
               f"Runnable {self.get_name()} doesn't have an inferable InputType. "
               "Override the InputType property to specify the input type."
           )
           raise TypeError(msg)
   
       @property
       def OutputType(self) -> type[Output]:  # noqa: N802
           """Output Type.
   
           The type of output this `Runnable` produces specified as a type annotation.
   
           Raises:
               TypeError: If the output type cannot be inferred.
           """
           # First loop through bases -- this will help generic
           # any pydantic models.
           for base in self.__class__.mro():
               if hasattr(base, "__pydantic_generic_metadata__"):
                   metadata = base.__pydantic_generic_metadata__
                   if (
                       "args" in metadata
                       and len(metadata["args"]) == _RUNNABLE_GENERIC_NUM_ARGS
                   ):
                       return cast("type[Output]", metadata["args"][1])
   
           for cls in self.__class__.__orig_bases__:  # type: ignore[attr-defined]
               type_args = get_args(cls)
               if type_args and len(type_args) == _RUNNABLE_GENERIC_NUM_ARGS:
                   return cast("type[Output]", type_args[1])
   
           msg = (
               f"Runnable {self.get_name()} doesn't have an inferable OutputType. "
               "Override the OutputType property to specify the output type."
           )
           raise TypeError(msg)
   ```

##### 12.1.3 **组合式的执行** → `|` 其底层重写了 `__or__` 方法

   ```python
   def __or__(
           self,
           other: Runnable[Any, Other]
           | Callable[[Iterator[Any]], Iterator[Other]]
           | Callable[[AsyncIterator[Any]], AsyncIterator[Other]]
           | Callable[[Any], Other]
           | Mapping[str, Runnable[Any, Other] | Callable[[Any], Other] | Any],
       ) -> RunnableSerializable[Input, Other]:
           """Runnable "or" operator.
   
           Compose this `Runnable` with another object to create a
           `RunnableSequence`.
   
           Args:
               other: Another `Runnable` or a `Runnable`-like object.
   
           Returns:
               A new `Runnable`.
           """
           return RunnableSequence(self, coerce_to_runnable(other))
   ```

   这使得封装出一个Sequence序列，将上一步的结果作为下一步组件的输出，当形成了 `langchain` 的组件之时例如以下例子。

   ```python
   chain = prompt | model    # 这里假设 prompt 为chatprompt之类的对象的时候， 由于 Runnable 重写了 __or__ 魔术方法
   chain = prompt.__or__(model) # 那么以上的动作就变成了这样子，使得其返回了 RunnableSequence 对象，当需要串行其他组件的时候，重复以上的操作即可
   ```

   **这便是`langchain` 最初串联组件的核心方式。**

   当然这里又出现了一个缺点，这就要回到 `Agent` 的定义上去了。

   什么是 `Agent` , 即 ***An LLM agent runs tools in a loop to achieve a goal***

   key point is ***the loop*** 但是其串行的方式意味着这无法进行自检和循环，这就不符合其定义

   因此 `langchain` 便推出了 `langgraph`  以及后续的大改版， 当然就这是其他模块要说的东西了。 

##### 12.1.4 **异步/流式重复写** → 基类提供默认实现

##### 12.1.5 **类型不透明** → `input_schema`/`output_schema` 自动推断

#### 🌟第二部分：一切都是Serializable之RunnableSerializable

``` python
class RunnableSerializable(Serializable, Runnable[Input, Output]):
    """Runnable that can be serialized to JSON."""

    name: str | None = None
    """The name of the `Runnable`.

    Used for debugging and tracing.
    """

    model_config = ConfigDict(
        # Suppress warnings from pydantic protected namespaces
        # (e.g., `model_`)
        protected_namespaces=(),
    )

    @override
    def to_json(self) -> SerializedConstructor | SerializedNotImplemented:
        """Serialize the `Runnable` to JSON.

        Returns:
            A JSON-serializable representation of the `Runnable`.

        """
        dumped = super().to_json()
        with contextlib.suppress(Exception):
            dumped["name"] = self.get_name()
        return dumped

    def configurable_fields(
        self, **kwargs: AnyConfigurableField
    ) -> RunnableSerializable[Input, Output]:
        """Configure particular `Runnable` fields at runtime.

        Args:
            **kwargs: A dictionary of `ConfigurableField` instances to configure.

        Raises:
            ValueError: If a configuration key is not found in the `Runnable`.

        Returns:
            A new `Runnable` with the fields configured.

        !!! example

            ```python
            from langchain_core.runnables import ConfigurableField
            from langchain_openai import ChatOpenAI

            model = ChatOpenAI(max_tokens=20).configurable_fields(
                max_tokens=ConfigurableField(
                    id="output_token_number",
                    name="Max tokens in the output",
                    description="The maximum number of tokens in the output",
                )
            )

            # max_tokens = 20
            print(
                "max_tokens_20: ", model.invoke("tell me something about chess").content
            )

            # max_tokens = 200
            print(
                "max_tokens_200: ",
                model.with_config(configurable={"output_token_number": 200})
                .invoke("tell me something about chess")
                .content,
            )
            ```
        """
        # Import locally to prevent circular import
        from langchain_core.runnables.configurable import (  # noqa: PLC0415
            RunnableConfigurableFields,
        )

        model_fields = type(self).model_fields
        for key in kwargs:
            if key not in model_fields:
                msg = (
                    f"Configuration key {key} not found in {self}: "
                    f"available keys are {model_fields.keys()}"
                )
                raise ValueError(msg)

        return RunnableConfigurableFields(default=self, fields=kwargs)

    def configurable_alternatives(
        self,
        which: ConfigurableField,
        *,
        default_key: str = "default",
        prefix_keys: bool = False,
        **kwargs: Runnable[Input, Output] | Callable[[], Runnable[Input, Output]],
    ) -> RunnableSerializable[Input, Output]:
        """Configure alternatives for `Runnable` objects that can be set at runtime.

        Args:
            which: The `ConfigurableField` instance that will be used to select the
                alternative.
            default_key: The default key to use if no alternative is selected.
            prefix_keys: Whether to prefix the keys with the `ConfigurableField` id.
            **kwargs: A dictionary of keys to `Runnable` instances or callables that
                return `Runnable` instances.

        Returns:
            A new `Runnable` with the alternatives configured.

        !!! example

            ```python
            from langchain_anthropic import ChatAnthropic
            from langchain_core.runnables.utils import ConfigurableField
            from langchain_openai import ChatOpenAI

            model = ChatAnthropic(
                model_name="claude-sonnet-4-5-20250929"
            ).configurable_alternatives(
                ConfigurableField(id="llm"),
                default_key="anthropic",
                openai=ChatOpenAI(),
            )

            # uses the default model ChatAnthropic
            print(model.invoke("which organization created you?").content)

            # uses ChatOpenAI
            print(
                model.with_config(configurable={"llm": "openai"})
                .invoke("which organization created you?")
                .content
            )
            ```
        """
        # Import locally to prevent circular import
        from langchain_core.runnables.configurable import (  # noqa: PLC0415
            RunnableConfigurableAlternatives,
        )

        return RunnableConfigurableAlternatives(
            which=which,
            default=self,
            alternatives=kwargs,
            default_key=default_key,
            prefix_keys=prefix_keys,
        )

```

其承载的核心功能就是Serialize所有可Serialize的Runnable的对象，langchain重写了Serializable，填充了关于lc的一堆属性，如下
这些参数再上面也说过了

```python
@property
def lc_secrets(self) -> dict[str, str]:
    """A map of constructor argument names to secret ids.

    For example, `{"openai_api_key": "OPENAI_API_KEY"}`
    """
    return {}

@property
def lc_attributes(self) -> dict:
    """List of attribute names that should be included in the serialized kwargs.

    These attributes must be accepted by the constructor.

    Default is an empty dictionary.
    """
    return {}

@classmethod
def lc_id(cls) -> list[str]:
    """Return a unique identifier for this class for serialization purposes.

    The unique identifier is a list of strings that describes the path
    to the object.

    For example, for the class `langchain.llms.openai.OpenAI`, the id is
    `["langchain", "llms", "openai", "OpenAI"]`.
```

等等方法，在langchain中万物皆对象，废话其实，对象就有独一无二的属性。

#### 🌟 第三部分：组合序列

##### 一，`RunnableSequence` — 串行链

```python
chain = prompt | model | parser
# 内部：RunnableSequence(first=prompt, middle=[model], last=parser)
# 执行：prompt 的输出 → model 的输入 → parser 的输入
```

`|` 操作符就是 `__or__` 重载，返回一个 `RunnableSequence` 对象。

因此，当Runnable对象使用 `__or__` 方法的时候，Runnable对象自己就变成了  `RunnableSequence`

```python
def __or__(
        self,
        other: Runnable[Any, Other]
        | Callable[[Iterator[Any]], Iterator[Other]]
        | Callable[[AsyncIterator[Any]], AsyncIterator[Other]]
        | Callable[[Any], Other]
        | Mapping[str, Runnable[Any, Other] | Callable[[Any], Other] | Any],
    ) -> RunnableSerializable[Input, Other]:
        """Runnable "or" operator.

        Compose this `Runnable` with another object to create a
        `RunnableSequence`.

        Args:
            other: Another `Runnable` or a `Runnable`-like object.

        Returns:
            A new `Runnable`.
        """
        return RunnableSequence(self, coerce_to_runnable(other))
```

这里`coerce_to_runnable` 会把类Runnable的所有类转成Runnable, 也是为了统一

##### 二，`RunnableParallel` — 并行链

官方在注释中写明了 ***RunnableParallel is one of the two main composition primitives***

嘛意思呢？白话就是，RunnalbeParallel 是非常重要组合件之一，另外一个是嘛呢，就是上面的RunnableSequenece

在这里说下这两种方式有何不同

**我们之前提到过了，RunnableSequence 是 Runnable 调用 or 方法后返回的结果，那么 Sequence 究竟产生了一个什么结果呢？**

看下他的init方法

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
        """Create a new `RunnableSequence`.

        Args:
            steps: The steps to include in the sequence.
            name: The name of the `Runnable`.
            first: The first `Runnable` in the sequence.
            middle: The middle `Runnable` objects in the sequence.
            last: The last `Runnable` in the sequence.

        Raises:
            ValueError: If the sequence has less than 2 steps.
        """
        steps_flat: list[Runnable] = []
        if not steps and first is not None and last is not None:
            steps_flat = [first] + (middle or []) + [last]
        for step in steps:
            if isinstance(step, RunnableSequence):
                steps_flat.extend(step.steps)
            else:
                steps_flat.append(coerce_to_runnable(step))
        if len(steps_flat) < _RUNNABLE_SEQUENCE_MIN_STEPS:
            msg = (
                f"RunnableSequence must have at least {_RUNNABLE_SEQUENCE_MIN_STEPS} "
                f"steps, got {len(steps_flat)}"
            )
            raise ValueError(msg)
        super().__init__(
            first=steps_flat[0],
            middle=list(steps_flat[1:-1]),
            last=steps_flat[-1],
            name=name,
        )
```

这里 RunnableSequence 方法，定义了三个参数，first、middle、last 首尾参数都是一个 Runnable 对象，中间是一个 list 的 Runnable 对象。
再结合Sequence这个方法名，显而易见，这是一个顺序的链条，下面再看其是如何拼接的

```python
        steps_flat: list[Runnable] = []
        if not steps and first is not None and last is not None:
            steps_flat = [first] + (middle or []) + [last]
        for step in steps:
            if isinstance(step, RunnableSequence):
                steps_flat.extend(step.steps)
            else:
                steps_flat.append(coerce_to_runnable(step))
        if len(steps_flat) < _RUNNABLE_SEQUENCE_MIN_STEPS:
            msg = (
                f"RunnableSequence must have at least {_RUNNABLE_SEQUENCE_MIN_STEPS} "
                f"steps, got {len(steps_flat)}"
            )
            raise ValueError(msg)
        super().__init__(
            first=steps_flat[0],
            middle=list(steps_flat[1:-1]),
            last=steps_flat[-1],
            name=name,
        )
```

其他的不赘述，要注意一点，就是当，step，即中间的一堆存在时，直接会用extend方法重构下，最后调用 pydantic 完成整体的验证
相比之下，RunnableParallel 的构建方式就 复杂一点，其规定了形成方式是 key-value 的形式，因此其初始化的时候
形成了的形式，其中 `coerce_to_runnable` 是一个强制转换的方法

```python
steps__={key: coerce_to_runnable(r) for key, r in merged.items()}
```

```python
class RunnableParallel(RunnableSerializable[Input, dict[str, Any]]):
    """Runnable that runs a mapping of `Runnable`s in parallel.

    Returns a mapping of their outputs.

    `RunnableParallel` is one of the two main composition primitives,
    alongside `RunnableSequence`. It invokes `Runnable`s concurrently, providing the
    same input to each.

    A `RunnableParallel` can be instantiated directly or by using a dict literal
    within a sequence.

    Here is a simple example that uses functions to illustrate the use of
    `RunnableParallel`:

        ```python
        from langchain_core.runnables import RunnableLambda


        def add_one(x: int) -> int:
            return x + 1


        def mul_two(x: int) -> int:
            return x * 2


        def mul_three(x: int) -> int:
            return x * 3


        runnable_1 = RunnableLambda(add_one)
        runnable_2 = RunnableLambda(mul_two)
        runnable_3 = RunnableLambda(mul_three)

        sequence = runnable_1 | {  # this dict is coerced to a RunnableParallel
            "mul_two": runnable_2,
            "mul_three": runnable_3,
        }
        # Or equivalently:
        # sequence = runnable_1 | RunnableParallel(
        #     {"mul_two": runnable_2, "mul_three": runnable_3}
        # )
        # Also equivalently:
        # sequence = runnable_1 | RunnableParallel(
        #     mul_two=runnable_2,
        #     mul_three=runnable_3,
        # )

        sequence.invoke(1)
        await sequence.ainvoke(1)

        sequence.batch([1, 2, 3])
        await sequence.abatch([1, 2, 3])
```

```python
`RunnableParallel` makes it easy to run `Runnable`s in parallel. In the below
example, we simultaneously stream output from two different `Runnable` objects:
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableParallel
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI()
    joke_chain = (
        ChatPromptTemplate.from_template("tell me a joke about {topic}") | model
    )
    poem_chain = (
        ChatPromptTemplate.from_template("write a 2-line poem about {topic}")
        | model
    )

    runnable = RunnableParallel(joke=joke_chain, poem=poem_chain)

    # Display stream
    output = {key: "" for key, _ in runnable.output_schema()}
    for chunk in runnable.stream({"topic": "bear"}):
        for key in chunk:
            output[key] = output[key] + chunk[key].content
        print(output)  # noqa: T201
```

``` python
steps__: Mapping[str, Runnable[Input, Any]]

def __init__(
    self,
    steps__: Mapping[
        str,
        Runnable[Input, Any]
        | Callable[[Input], Any]
        | Mapping[str, Runnable[Input, Any] | Callable[[Input], Any]],
    ]
    | None = None,
    **kwargs: Runnable[Input, Any]
    | Callable[[Input], Any]
    | Mapping[str, Runnable[Input, Any] | Callable[[Input], Any]],
) -> None:
    """Create a `RunnableParallel`.

    Args:
        steps__: The steps to include.
        **kwargs: Additional steps to include.

    """
    merged = {**steps__} if steps__ is not None else {}
    merged.update(kwargs)
    super().__init__(
        steps__={key: coerce_to_runnable(r) for key, r in merged.items()}
   )
```

`RunnableParallel` 的初始化运行是在invoke阶段完成的(也是废话)，其实都是这个阶段运行的，只不过是这个特殊一点，

值得注意的是，其底 RunnableParallel 底层用了一个 继承了 `ThreadPoolExecutor` 的 · `ContextThreadPoolExecutor` 

其同步方法用到的是线程池的方案，同时保留了上下文的信息，具体是怎么做到了呢？

##### 三，`RunnableGenerator` — 生成器包装器

该部分不太重要，主要是包装一个底层的迭代器了，其他的无他，主要目的是便于用户自行定义Stream的后处理过程，其官方给出了使用样例

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
                    yield "👏" + token
                else:
                    yield token


        runnable = chant_chain | character_generator
        assert type(runnable.last) is RunnableGenerator
        "".join(runnable.stream({"topic": "waste"}))  # Reduce👏, Reuse👏, Recycle👏.


        # Note that RunnableLambda can be used to delay streaming of one step in a
        # sequence until the previous step is finished:
        def reverse_generator(input: str) -> Iterator[str]:
            # Yield characters of input in reverse order.
            for character in input[::-1]:
                yield character


        runnable = chant_chain | RunnableLambda(reverse_generator)
        "".join(runnable.stream({"topic": "waste"}))  # ".elcycer ,esuer ,ecudeR"
```

```python
def stream_words(input):
    for word in input.split():
        yield word

streamer = RunnableGenerator(stream_words)  # 支持流式
```

##### 四，`RunnableEach` — **Each 运行单元**

该部分底层用到的是 `asynio` 的 `gather` 方法，然后遍历 `config`

```python
class RunnableEachBase(RunnableSerializable[list[Input], list[Output]]):
    """RunnableEachBase class.

    `Runnable` that calls another `Runnable` for each element of the input sequence.

    Use only if creating a new `RunnableEach` subclass with different `__init__`
    args.

    See documentation for `RunnableEach` for more details.

    """

    bound: Runnable[Input, Output]

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    @property
    @override
    def InputType(self) -> Any:
        return list[self.bound.InputType]  # type: ignore[name-defined]

    @override
    def get_input_schema(self, config: RunnableConfig | None = None) -> type[BaseModel]:
        return create_model_v2(
            self.get_name("Input"),
            root=(
                list[self.bound.get_input_schema(config)],  # type: ignore[misc]
                None,
            ),
            # create model needs access to appropriate type annotations to be
            # able to construct the Pydantic model.
            # When we create the model, we pass information about the namespace
            # where the model is being created, so the type annotations can
            # be resolved correctly as well.
            # self.__class__.__module__ handles the case when the Runnable is
            # being sub-classed in a different module.
            module_name=self.__class__.__module__,
        )

    @property
    @override
    def OutputType(self) -> type[list[Output]]:
        return list[self.bound.OutputType]  # type: ignore[name-defined]

    @override
    def get_output_schema(
        self, config: RunnableConfig | None = None
    ) -> type[BaseModel]:
        schema = self.bound.get_output_schema(config)
        return create_model_v2(
            self.get_name("Output"),
            root=list[schema],  # type: ignore[valid-type]
            # create model needs access to appropriate type annotations to be
            # able to construct the Pydantic model.
            # When we create the model, we pass information about the namespace
            # where the model is being created, so the type annotations can
            # be resolved correctly as well.
            # self.__class__.__module__ handles the case when the Runnable is
            # being sub-classed in a different module.
            module_name=self.__class__.__module__,
        )

    @property
    @override
    def config_specs(self) -> list[ConfigurableFieldSpec]:
        return self.bound.config_specs

    @override
    def get_graph(self, config: RunnableConfig | None = None) -> Graph:
        return self.bound.get_graph(config)

    @classmethod
    @override
    def is_lc_serializable(cls) -> bool:
        """Return `True` as this class is serializable."""
        return True

    @classmethod
    @override
    def get_lc_namespace(cls) -> list[str]:
        """Get the namespace of the LangChain object.

        Returns:
            `["langchain", "schema", "runnable"]`
        """
        return ["langchain", "schema", "runnable"]

    def _invoke(
        self,
        inputs: list[Input],
        run_manager: CallbackManagerForChainRun,
        config: RunnableConfig,
        **kwargs: Any,
    ) -> list[Output]:
        configs = [
            patch_config(config, callbacks=run_manager.get_child()) for _ in inputs
        ]
        return self.bound.batch(inputs, configs, **kwargs)

    @override
    def invoke(
        self, input: list[Input], config: RunnableConfig | None = None, **kwargs: Any
    ) -> list[Output]:
        return self._call_with_config(self._invoke, input, config, **kwargs)

    async def _ainvoke(
        self,
        inputs: list[Input],
        run_manager: AsyncCallbackManagerForChainRun,
        config: RunnableConfig,
        **kwargs: Any,
    ) -> list[Output]:
        configs = [
            patch_config(config, callbacks=run_manager.get_child()) for _ in inputs
        ]
        return await self.bound.abatch(inputs, configs, **kwargs)

    @override
    async def ainvoke(
        self, input: list[Input], config: RunnableConfig | None = None, **kwargs: Any
    ) -> list[Output]:
        return await self._acall_with_config(self._ainvoke, input, config, **kwargs)
```

##### 五，`RunnableLambda` — **接入单元**

RunnableLambda 的核心就是把普通函数包装成 Runnable 对象，让它具备统一接口：invoke/ainvoke/batch/stream，并能参与 | 链式组合、配置

具体看到其一堆的init方法就明白了

#### 🌟 第四部分：大总结

总的来说，Runnable 的 base 是 langchain 这个项目核心中的核心，其定义了 langchain 中可执行对象 Runnable 所有的行为以及组合方式（运行方式） Sequence 和 Map / Parallel 即顺序执行和并发执行，

langchain 该部分的设计哲学如下，

1，其通过高度抽象的继承等方法，将所有的执行体（chain），组合成Runnable对象，便于统一性的处理结果。

2，高度解耦，例如initialize，完全依赖了 pydantic 模型，也就意味着完全和执行方法进行了解耦，这样就便于参数和状态的改变，同时使用config/callback 上下文和递归执行语义，实现上下文的低度耦合。

3，缺点： 抽象程度太高了，也太深，分支也太多了，不同类型的需求，比如并发、顺序、迭代等，会经过好几个patch，感觉不是很必要，而且看代码累个半死，但是组合能力上挺强的，避免了高度的耦合设计，总觉的对agent来说，是个复杂的设计。因为agent只是个无线循环，直到完成用户任务的工具，这么复杂的设计，没有必要。

#### 🔗 相关源码

- `langchain_core/runnables/base.py` — `Runnable` 及所有组合原语的定义
- `langchain_core/runnables/config.py` — `RunnableConfig` 运行时配置

### langchain_core tool part

#### BaseTool

```python
name: str
description: str
args_schema: Annotated[ArgsSchema | None, SkipValidation()] = Field(
    default=None, description="The tool schema."
) 以上几个都不提了，一眼就知道干啥的


return_direct: bool = False
这个参数单独拎出来，按着源码的描述是这样子
处理 AgentExecutor 中的工具调用问题，True 的时候调用后会直接结束 AgentExecutor 的循环, 此外 AgentExecutor 是个巨老的包，弃用了已经

verbose: bool = False 日志

callbacks: Callbacks = Field(default=None, exclude=True)
我猜测是所有可 Runnable 的东西都要加上这样一个Call back函数,


tags: list[str] | None = None 

metadata: dict[str, Any] | None = None
handle_tool_error: bool | str | Callable[[ToolException], str] | None = False
handle_validation_error: (
    bool | str | Callable[[ValidationError | ValidationErrorV1], str] | None
) = False
response_format: Literal["content", "content_and_artifact"] = "content"
extras: dict[str, Any] | None = None
```

#### InjectedToolArg && InjectedToolCallId && ## BaseToolkit

"""Annotation for tool arguments that are injected at runtime.
Tool arguments annotated with this class are not included in the tool
    schema sent to language models and are instead injected during execution.
运行时注入的工具参数，这个后续我会说，先mark下

### langchain_core vectores part

#### class VectorStore(ABC)

  为了将所有的向量库纳入 langchain 体系下的基类，定义了VecDB的所有基础方法具体就不展开说了

  我一直觉得，langchain want do everything 的想法，有点弱智了，向量库作为外部数据源的读取以及内部数据的转换桥接部分，我不明白为何也要集成，数据交换的部分直接交给程序员自己做不好吗？

  除非是这样子，是在我看来。以后所有的基础设计，无论是已经纳入体系的 GREP 等 OS 的基础方法还是 text2sql（本质上是 SQL as tool） 这一类。以后的所有内容都可能会变成 AGENTIC Tool 的基础设施/工具节点， 而不是以前的单纯的信息的传递和交换（简单RAG的时代是作为检索或者embeding），可能是出于这个考虑，而将向量库纳入 Agent 体系，不仅是检索，而是作为体系的一员，附带上检索的能力，我能想到的设计目的只有这一个。

  但是感觉还是很臃肿，langchain 真的是叠了很多层。

---

## 🏗️ 在 LangChain 生态中的位置

``` markdown
langchain-core              ← 基础协议
    │
    ├── langchain            ← 上层封装（create_agent 等）
    ├── langgraph            ← Agent 编排引擎（状态图）
    └── langchain-xxx        ← 各厂商集成（openai、anthropic...）
```
