---
title: "3. langgraph 源码"
description: "langgraph  langchain 对于其 agent 执行逻辑的思考和重构，我倒是很好奇"
pubDate: 2026-06-16
section: framework
categories:
  - langchain
---

langgraph  langchain 对于其 agent 执行逻辑的思考和重构，我倒是很好奇

## 结构拆分

| 包/模块 | 思考 |
| :--- | :--- |
| `langgraph.cache` | [cache](#langgraphcache) |
| `langgraph.channels` | [channels](#langgraphchannels) |
| `langgraph.checkpoint` | [checkpoint](#langgraphcheckpoint) |
| `langgraph.func` | [func](#langgraphfunc) |
| `langgraph.graph` | [graph](#langgraphgraph) |
| `langgraph.managed` | [managed](#langgraphmanaged) |
| `langgraph.prebuilt` | [prebuilt](#langgraphprebuilt) |
| `langgraph.pregel` | [pregel](#langgraphpregel) |
| `langgraph.store` | [store](#langgraphstore) |
| `langgraph.utils` | [utils](#langgraphutils) |
| `langgraph._internal` | [_internal](#langgraph_internal) |
| `langgraph.callbacks` | [callbacks](#langgraphcallbacks) |
| `langgraph.config` | [config](#langgraphconfig) |
| `langgraph.constants` | [constants](#langgraphconstants) |
| `langgraph.errors` | [errors](#langgrapherrors) |
| `langgraph.runtime` | [runtime](#langgraphruntime) |
| `langgraph.types` | [types](#langgraphtypes) |
| `langgraph.typing` | [typing](#langgraphtyping) |
| `langgraph.version` | [version](#langgraphversion) |
| `langgraph.warnings` | [warnings](#langgraphwarnings) |
| `langgraph_sdk` | [langgraph_sdk](#langgraphlanggraph_sdk) |

---

## 1. langgraph.cache

源码位置：`.venv/Lib/site-packages/langgraph/cache/`

TODO

---

## 2. langgraph.callbacks

源码位置：`.venv/Lib/site-packages/langgraph/callbacks.py`

TODO

---

## 3. langgraph.channels

源码位置：`.venv/Lib/site-packages/langgraph/channels/`

### 3.1 BaseChannel

这里文档本身说了一个 ***Base class for all channels***

我倾向于把他定义为运行中状态的改变（基于参数），update 进行数据的转化
Channel 类似信道的概念。

就是面向 `Agent Runtime` 数据的不同行为，只不过抽象一个 BaseChannel 类

首先定义期间数据变化的行为 copy，consume, finish，其实更像数据的操作行为的定义
允许 state 参数再运行期间可以，复制，结束


 
#### 3.1.1 参数

1. key： 顾名思义是隶属于 channel 下参数的名称
2. typ： 顾名思义是隶属于 channel 下参数的type
3. 剩下的都是 copy，checkpoint， from_checkpoint，get，is_available，update，consume，finish 简单明了，即 channel 可以执行的操作

#### 3.1.2 类方法

##### 3.1.3 ValueType & UpdateType

规定了两个属性类的参数，说是接受 -> 保存需要保存的内容到信道

``` python
@property
@abstractmethod
def ValueType(self) -> Any:
    """The type of the value stored in the channel."""

@property
@abstractmethod
def UpdateType(self) -> Any:
    """The type of the update received by the channel."""
```

#### 3.1.4 checkpoint & from_checkpoint 
这里是关于 checkpointer 的存取过程，关于 checkpointer 的详细定义请看 [checkpoint](#langgraphcheckpoint) 这是 langgraph 维护短期记忆的核心部分

### 3.2 AnyValue

---

## langgraph.checkpoint

源码位置：`.venv/Lib/site-packages/langgraph/checkpoint/`



TODO

---

## langgraph.config


源码位置：`.venv/Lib/site-packages/langgraph/config.py`



TODO

---

## langgraph.constants


源码位置：`.venv/Lib/site-packages/langgraph/constants.py`



TODO

---

## langgraph.errors


源码位置：`.venv/Lib/site-packages/langgraph/errors.py`



TODO

---

## langgraph.func


源码位置：`.venv/Lib/site-packages/langgraph/func/`



TODO

---

## langgraph.graph

源码位置：`.venv/Lib/site-packages/langgraph/graph/`

### state.py (图创建的核心包)

```python
class StateGraph(Generic[StateT, ContextT, InputT, OutputT]):
    """A graph whose nodes communicate by reading and writing to a shared state.

    The signature of each node is `State -> Partial<State>`.
```

graph 创建类，当前 create_agent 的底层方法之一，也是图的入口。

其定义了一堆类属性， edages、nodes、branches、channels、managed、schemas、watting_edages、compiled。

以及以下几个状态管理参数

1. `state_schema: type[StateT]`
2. `context_schema: type[ContextT] | None`
3. `input_schema: type[InputT]`
4. `output_schema: type[OutputT]`

等四个层面的状态管理类

这里需要关注的是 `state_schema` 以及 `context_schema`, 另外俩属于出参和入参的管理，后面再说

这里有一点很有意思，主要是关于 `Graph` 参数的处理使用了一个 `_add_schema` 方法

### _add_schema （对于图所需的参数管理的function）

```python
    def _add_schema(self, schema: type[Any], /, allow_managed: bool = True) -> None:
        if schema not in self.schemas:
            _warn_invalid_state_schema(schema)
            channels, managed, type_hints = _get_channels(schema)
            if managed and not allow_managed:
                names = ", ".join(managed)
                schema_name = getattr(schema, "__name__", "")
                raise ValueError(
                    f"Invalid managed channels detected in {schema_name}: {names}."
                    " Managed channels are not permitted in Input/Output schema."
                )
            self.schemas[schema] = {**channels, **managed}
            for key, channel in channels.items():
                if key in self.channels:
                    if self.channels[key] != channel:
                        if isinstance(channel, LastValue):
                            pass
                        else:
                            raise ValueError(
                                f"Channel '{key}' already exists with a different type"
                            )
                else:
                    self.channels[key] = channel
            for key, managed in managed.items():
                if key in self.managed:
                    if self.managed[key] != managed:
                        raise ValueError(
                            f"Managed value '{key}' already exists with a different type"
                        )
                else:
                    self.managed[key] = managed
```

该方法对参数做了三个分类，`Managed`、`Channel`、`Schemas` 目测涉及到参数的更新，状态的管理，以及整体参数的整合（Schemas）

参数归约路径是 schema -> 使用 `_get_channels` 方法从 schema 中拆分出 channels 以及 managed，参数
归纳到 `channel` 以及 `managed`、`schemas` 三个实例属性

```python
def _get_channels(
    schema: type[dict],
) -> tuple[dict[str, BaseChannel], dict[str, ManagedValueSpec], dict[str, Any]]:
    if not hasattr(schema, "__annotations__"):
        return (
            {"__root__": _get_channel("__root__", schema, allow_managed=False)},
            {},
            {},
        )

    type_hints = get_type_hints(schema, include_extras=True)
    all_keys = {
        name: _get_channel(name, typ)
        for name, typ in type_hints.items()
        if name != "__slots__"
    }
    return (
        {k: v for k, v in all_keys.items() if isinstance(v, BaseChannel)},
        {k: v for k, v in all_keys.items() if is_managed_value(v)},
        type_hints,
    )
```

```python
def _get_channel(
    name: str, annotation: Any, *, allow_managed: bool = True
) -> BaseChannel | ManagedValueSpec:
    # Strip out Required and NotRequired wrappers
    if hasattr(annotation, "__origin__") and annotation.__origin__ in (
        Required,
        NotRequired,
    ):
        annotation = annotation.__args__[0]
    if manager := _is_field_managed_value(name, annotation):
        if allow_managed:
            return manager
        else:
            raise ValueError(f"This {annotation} not allowed in this position")
    elif channel := _is_field_channel(annotation):
        channel.key = name
        return channel
    elif channel := _is_field_binop(annotation):
        channel.key = name
        return channel

    fallback: LastValue = LastValue(annotation)
    fallback.key = name
    return fallback
```

他这个 `channel` 我在一开始始终没想明白是什么意思，细说下来（又要说废话了）】

1. Channel: 好比你继承 AgentState 的时候，有一个类是 MessagesState 主要的作用就是更新运行中的消息，然后窥一管而知全豹，顺着 [channels](#langgraph.channels) 的继承链去看，就会知道，

---

## langgraph_sdk

## langgraph_sdk

源码位置：`.venv/Lib/site-packages/langgraph_sdk/`

TODO

---

## langgraph.managed


源码位置：`.venv/Lib/site-packages/langgraph/managed/`



TODO

---

## langgraph.prebuilt


源码位置：`.venv/Lib/site-packages/langgraph/prebuilt/`



TODO

---

## langgraph.pregel


源码位置：`.venv/Lib/site-packages/langgraph/pregel/`



TODO

---

## langgraph.runtime


源码位置：`.venv/Lib/site-packages/langgraph/runtime.py`



TODO

---

## langgraph.store


源码位置：`.venv/Lib/site-packages/langgraph/store/`



TODO

---

## langgraph.types


源码位置：`.venv/Lib/site-packages/langgraph/types.py`



TODO

---

## langgraph.typing


源码位置：`.venv/Lib/site-packages/langgraph/typing.py`



TODO

---

## langgraph.utils


源码位置：`.venv/Lib/site-packages/langgraph/utils/`



TODO

---

## langgraph.version


源码位置：`.venv/Lib/site-packages/langgraph/version.py`



TODO

---

## langgraph.warnings


源码位置：`.venv/Lib/site-packages/langgraph/warnings.py`



TODO

---

## langgraph._internal


源码位置：`.venv/Lib/site-packages/langgraph/_internal/`



TODO
