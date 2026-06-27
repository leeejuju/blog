---
title: "源码阅读: langgraph 源码"
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

Channel 类似信道的概念。我倾向于把他定义为运行中状态的改变（基于参数），update 进行数据的转化


对于继承 `BaseChannel` 的类，规定只有两种参数，`typ`, `key` （比如定义的 x:int）, 子类根据自己的职责定位添加自己的属性值，同时固定持有信道的基础属性
一方面可以自己添加属性去对参数管理。一方面也可持有父类的属性去进行操作。

所以 `channel` 包的底层逻辑就是拆分了 `agent state` 参数的处理规则，那对于构建 Agent Application 的话，有何裨益

就是面向 `Agent Runtime` 数据的不同行为，只不过抽象一个 BaseChannel 类

首先定义期间数据变化的行为 copy，consume, finish，其实更像数据的操作行为的定义
允许 state 参数再运行期间可以，复制，结束, first look 下来是比较抽象的。

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

> Stores the last value received, assumes that if multiple values are received, they are all equal.
> 我也不知道这玩意咋用的，暂且按下不表，但是该类只接收最后一个参数，而且即使有多个值传过来，默认他们是相同。

#### 3.2.1 AnyValue 的结构和方法

`AnyValue` 除了 `channel` 的指定参数，又多规定了 `value` 参数，同时

``` python
    @property
    def ValueType(self) -> type[Value]:
        """The type of the value stored in the channel."""
        return self.typ

    @property
    def UpdateType(self) -> type[Value]:
        """The type of the update received by the channel."""
        return self.typ
    
        def copy(self) -> Self:
        """Return a copy of the channel."""
        empty = self.__class__(self.typ, self.key)
        empty.value = self.value
        return empty

    def from_checkpoint(self, checkpoint: Value) -> Self:
        empty = self.__class__(self.typ, self.key)
        if checkpoint is not MISSING:
            empty.value = checkpoint
        return empty

    def update(self, values: Sequence[Value]) -> bool:
        if len(values) == 0:
            if self.value is MISSING:
                return False
            else:
                self.value = MISSING
                return True

        self.value = values[-1]
        return True

    def get(self) -> Value:
        if self.value is MISSING:
            raise EmptyChannelError()
        return self.value

    def is_available(self) -> bool:
        return self.value is not MISSING

    def checkpoint(self) -> Value:
        return self.value

```

AnyValue 规定了信道的更新和存储的值，可以看到没有做任何的转化，直入直出，此外 `AnyValue` 对于状态的意义是，把新增的 `value` 作为了信号标识
有填充就返回/更新填充的内容，没有填充就返回 `Missing` 表示信道为空的信号，具体就不说了

### 3.3 BinaryOperatorAggregate

> Stores the result of applying a binary operator to the current value and each new value.
> 把一个二元运算符依次应用到当前值和每个新值之后，具体看应用

#### 3.3.1 BinaryOperatorAggregate的结构和方法

> BinaryOperatorAggregate 限定了 __slots__ = ("value", "operator")
> 也能看出来，比较符合类的定位，对于 value 使用 operator 进行计算/更新

关于状态的更新，`any_value` 和 `BinaryOperatorAggregate` 看出，对于 value 设置，当没有value的时候，value要么是missing,要么就是checkponter
这几个子类都是这样子

在 `BinaryOperation` 里比较重要的是如下

``` python
 def update(self, values: Sequence[Value]) -> bool:
        if not values:
            return False
        if self.value is MISSING:
            self.value = values[0]
            values = values[1:]
        seen_overwrite: bool = False
        for value in values:
            is_overwrite, overwrite_value = _get_overwrite(value)
            if is_overwrite:
                if seen_overwrite:
                    msg = create_error_message(
                        message="Can receive only one Overwrite value per super-step.",
                        error_code=ErrorCode.INVALID_CONCURRENT_GRAPH_UPDATE,
                    )
                    raise InvalidUpdateError(msg)
                self.value = overwrite_value
                seen_overwrite = True
                continue
            if not seen_overwrite:
                self.value = self.operator(self.value, value)
        return True
```

循环的时候，如果参数被 `Overwrite` 包裹，直接就更新过去, 不再走 `operator` 更新

### 3.4 EphemeralValue

> Stores the value received in the step immediately preceding, clears after
> 接受上一步产出的内容，注意是 `value` 单数，用完后且没有在传输值进来，将value清空

#### 3.4.1 EphemeralValue 的结构和方法

> __slots__ = ("value", "guard")
> 规定了两个参数，value 估计就是纯值 or somethingelse gurad 是

``` python
    def update(self, values: Sequence[Value]) -> bool:
        if len(values) == 0:
            if self.value is not MISSING:
                self.value = MISSING
                return True
            else:
                return False
        if len(values) != 1 and self.guard:
            raise InvalidUpdateError(
                f"At key '{self.key}': EphemeralValue(guard=True) 
                can receive only one value per step. Use guard=False
                 if you want to store any one of multiple values."
            )

        self.value = values[-1]
        return True
```

value 一次接收一个值，正如我刚才提到的，所以后面才写了一行这个

``` python
  if len(values) != 1 and self.guard:
            raise InvalidUpdateError(
                f"At key '{self.key}': EphemeralValue(guard=True) 
                can receive only one value per step. Use guard=False
                 if you want to store any one of multiple values."
            )
```

### 3.5 LastValue

> """Stores the last value received, can receive at most one value per step."""
> 存储收到的最后一个值，而且每一步，最多只接受一个值

#### 3.5.1 LastValue 的结构和方法

> __slots__ = ("value",)
> 规定 value 纯值

``` python
    def update(self, values: Sequence[Value]) -> bool:
        if len(values) == 0:
            return False
        if len(values) != 1:
            msg = create_error_message(
                message=f"At key '{self.key}': Can receive only one value per step. 
                Use an Annotated key to handle multiple values.",
                error_code=ErrorCode.INVALID_CONCURRENT_GRAPH_UPDATE,
            )
            raise InvalidUpdateError(msg)

        self.value = values[-1]
        return True
```

也很简单，不说了

### 3.6 NamedBarrierValue

> """A channel that waits until all named values are received before making the value available."""
> 该信道会持续 `await` 到所有的值都收齐，然后将值设置为 `available`

#### 3.6.1 NamedBarrierValue 的结构和方法

> __slots__ = ("names", "seen")
> 规定了参数的 `name` 以及 `seen` 后者是监控参数

``` python
def update(self, values: Sequence[Value]) -> bool:
        updated = False
        for value in values:
            if value in self.names:
                if value not in self.seen:
                    self.seen.add(value)
                    updated = True
            else:
                raise InvalidUpdateError(
                    f"At key '{self.key}': Value {value} not in {self.names}"
                )
        return updated
```

以上是核心的方法 根据值是否已经全部收集完毕去判断是否可更新

#### 3.6.1 NamedBarrierValueAfterFinish 的结构和方法

> """A channel that waits until all named values are received before making the value ready to be made available. It is only made available after finish() is called."""
> 该信道间距上面的功能的同时们还会限定 只有 `finish` 后参数才会可用

### 3.7 Topic

>"""A configurable PubSub Topic.
> Args:
> typ: The type of the value stored in the channel.
> accumulate: Whether to accumulate values across steps. If `False`, the channel will be emptied after each step.
> """
> 这个就算是他内部的消息队列了，***估计是 harness 会用，而且也是非常需要用到***，到 `accumulate` False 后每一步都会清除信道里面存的数据，你从名字就看出了啊

#### 3.7.1 Topic 的结构和方法

> __slots__ = ("values", "accumulate")
> 是否堆积参数主要作用

``` python
def update(self, values: Sequence[Value | list[Value]]) -> bool:
        updated = False
        if not self.accumulate:
            updated = bool(self.values)
            self.values = list[Value]()
        if flat_values := tuple(_flatten(values)):
            updated = True
            self.values.extend(flat_values)
        return updated
```

根据是否堆积，只保留是否更新状态，否则就extend value

### 3.8 UntrackedValue

#### 3.8.1 UntrackedValue 的结构和方法

这个和之前的 `EphemralVlaue` 基本一致，但是完全不经过 `checkpointer`，就不说了

总结下来，其实 Channel 本身就是用户定义的实体类的各个参数，每一个参数都是一个 Channel。

它为每一个参数都规划了行为（比如是丢弃还是其他操作）。从 checkpoint 的行为中可以看到，系统为每一个参数都设置了一个版本号。这是合理的，因为并非所有参数都需要更新，所以它是根据已经变化的参数类型来去判断的。

即通过各个 channel (参数) 对运行中的状态，进行了一系列的规划，比如是参数是丢弃？堆叠? 更新？ 这一些列的操作，同时也规定了其 checkpointer 类要保存的最小单元

---

## 4. langgraph.checkpoint ⭐

这是 langgraph 维护长短期上下文的核心，在 channel 的各个基础类中，都以序列化参数的方式定义了检查点的内容，但是都是很小的单元，
按说，应该有检查点的 id, tag 之类的，应该是在外围包构建了这些消息

### base.id

> 惯例的零帧起手，看 base 的包结构
> 是个 uuid 的创建类，估计是为了序列化检查点的快照，提供 id 标识

### base.__init__

> meta define 的地方

#### base.init.CheckpointMetadata

``` python

class CheckpointMetadata(TypedDict, total=False):
    """Metadata associated with a checkpoint."""

    source: Literal["input", "loop", "update", "fork"]
    """The source of the checkpoint.

    - `"input"`: The checkpoint was created from an input to invoke/stream/batch.
    - `"loop"`: The checkpoint was created from inside the pregel loop.
    - `"update"`: The checkpoint was created from a manual state update.
    - `"fork"`: The checkpoint was created as a copy of another checkpoint.
    """
    step: int
    """The step number of the checkpoint.

    `-1` for the first `"input"` checkpoint.
    `0` for the first `"loop"` checkpoint.
    `...` for the `nth` checkpoint afterwards.
    """
    parents: dict[str, str]
    """The IDs of the parent checkpoints.

    Mapping from checkpoint namespace to checkpoint ID.
    """

```

> 规定了 checkpointer 的 来源，给了四个参数 `input` `loop` `update` `fork` 分别代表，checkpointer 生成的阶段是，输入、循环、更新、fork 阶段
> step: 用int 规定所处阶段，-1标识输入，0标识进入 loop, ...代表后续的所有阶段
> parents: 字典奥注意，大概是这样子 xxx.xx.xx(包名)：uid. 后续我贴一个输出就知道了 "TODO"

#### base.init.Checkpoint

``` python
class Checkpoint(TypedDict):
    """State snapshot at a given point in time."""

    v: int
    """The version of the checkpoint format. Currently 1."""
    id: str
    """The ID of the checkpoint. This is both unique and monotonically
    increasing, so can be used for sorting checkpoints from first to last."""
    ts: str
    """The timestamp of the checkpoint in ISO 8601 format."""
    channel_values: dict[str, Any]
    """The values of the channels at the time of the checkpoint.
    Mapping from channel name to deserialized channel snapshot value.
    """
    channel_versions: ChannelVersions
    """The versions of the channels at the time of the checkpoint.
    The keys are channel names and the values are monotonically increasing
    version strings for each channel.
    """
    versions_seen: dict[str, ChannelVersions]
    """Map from node ID to map from channel name to version seen.
    This keeps track of the versions of the channels that each node has seen.
    Used to determine which nodes to execute next.
    """
    updated_channels: list[str] | None
    """The channels that were updated in this checkpoint.
    """
```

> v：规定了 Checkpoint 的格式版本，说是 v1
> id: 用int 规定所处阶段，-1标识输入，0标识进入 loop, ...代表后续的所有阶段
> ts: checkpointer 创建的时间戳
> channel_values: 看之前的channel 
> channel_versions: 生成 `checkponiter` 时的 channel_versions, 这他妈文档写的够烂的，我操，他妈的，应该是 the version of the channels at the time of the checkpoint recreated or created. 它的格式应该是：Key 是 channel names，参数名， value 就是版本号，具体是社么样子的 string 再说
> versions_seen: 版本 形如 `dict[key,dict[key, value]] channel name  to version seen
> updated_channels: 记录当前 checkpointer 中，更新过的信道（参数）

#### base.init.CheckpointTuple

> CheckpointTuple 的元组

``` python
class CheckpointTuple(NamedTuple):
    """A tuple containing a checkpoint and its associated data."""

    config: RunnableConfig
    checkpoint: Checkpoint
    metadata: CheckpointMetadata
    parent_config: RunnableConfig | None = None
    pending_writes: list[PendingWrite] | None = None
```

1. `config` 凡是 `RunnableConfig` 都是可控制 langchain 运行的一堆参数， 什么控制 `callback`, 可配置的 configurable 参数，比如替换模型啥的，反正是开发者可自由支配的参数
2. 剩下几个就不说了，唯一要提的就是 `pending_writes` 存储运行中产生的内容，并且不是立即加入的内容，所以叫pending

#### base.init.BaseCheckpointSaver

##### BaseCheckpointSaver

> Checkpointer 的基础属性和行为

1. **get & get_tuple & aget & aget_tuple**：这里都是异步的操作取获得 `checkpointer` 具体要看子类的的实现方式
2. **list & alist & put & aput & put_writes & aput_writes**：同步/异步的获得，存储检查点，到 `postgres` 我具体说
3. **delete_thread & adelete_thread**：对话线程删除

##### memory.__init__.InMemorySaver

> 这是个短期记忆的 saver 之前看官方都不推荐用，说是测试用
> 对于测试来说，也可看的

这里有三个参数。 storage、writes、blobs

``` python
 storage: defaultdict[
        str,
        dict[str, dict[str, tuple[tuple[str, bytes], tuple[str, bytes], str | None]]],
    ]
    # (thread ID, checkpoint NS, checkpoint ID) -> (task ID, write idx)
    writes: defaultdict[
        tuple[str, str, str],
        dict[tuple[str, int], tuple[str, str, tuple[str, bytes], str]],
    ]
    blobs: dict[
        tuple[
            str, str, str, str | int | float
        ],  # thread id, checkpoint ns, channel, version
        tuple[str, bytes],
    ]

```

从 `CheckpointerTuple` 看下来 `writers` 主要是存储运行过程中生成，但是还没完全完成的东西
`blobs` 则是对于 `channel_value` 的值进行单独存储。且是对每个 checkpoint id 生成当前状态的存储 

`self.stores` 则是对checkpoint 完全体的存储，除了具体的值（具体的值会存放在blobs中）

``` python

class InMemorySaver(
    BaseCheckpointSaver[str], AbstractContextManager, AbstractAsyncContextManager
):
    """An in-memory checkpoint saver.

    This checkpoint saver stores checkpoints in memory using a defaultdict.

    Note:
        Only use `InMemorySaver` for debugging or testing purposes.
        For production use cases we recommend installing [langgraph-checkpoint-postgres](https://pypi.org/project/langgraph-checkpoint-postgres/) and using `PostgresSaver` / `AsyncPostgresSaver`.

        If you are using LangSmith Deployment, no checkpointer needs to be specified. The correct managed checkpointer will be used automatically.

    Args:
        serde: The serializer to use for serializing and deserializing checkpoints.

    Examples:

            import asyncio

            from langgraph.checkpoint.memory import InMemorySaver
            from langgraph.graph import StateGraph

            builder = StateGraph(int)
            builder.add_node("add_one", lambda x: x + 1)
            builder.set_entry_point("add_one")
            builder.set_finish_point("add_one")

            memory = InMemorySaver()
            graph = builder.compile(checkpointer=memory)
            coro = graph.ainvoke(1, {"configurable": {"thread_id": "thread-1"}})
            asyncio.run(coro)  # Output: 2
    """

    # thread ID ->  checkpoint NS -> checkpoint ID -> checkpoint mapping
    storage: defaultdict[
        str,
        dict[str, dict[str, tuple[tuple[str, bytes], tuple[str, bytes], str | None]]],
    ]
    # (thread ID, checkpoint NS, checkpoint ID) -> (task ID, write idx)
    writes: defaultdict[
        tuple[str, str, str],
        dict[tuple[str, int], tuple[str, str, tuple[str, bytes], str]],
    ]
    blobs: dict[
        tuple[
            str, str, str, str | int | float
        ],  # thread id, checkpoint ns, channel, version
        tuple[str, bytes],
    ]

    def __init__(
        self,
        *,
        serde: SerializerProtocol | None = None,
        factory: type[defaultdict] = defaultdict,
    ) -> None:
        super().__init__(serde=serde)
        self.storage = factory(lambda: defaultdict(dict))
        self.writes = factory(dict)
        self.blobs = factory()
        self.stack = ExitStack()
        if factory is not defaultdict:
            self.stack.enter_context(self.storage)  # type: ignore[arg-type]
            self.stack.enter_context(self.writes)  # type: ignore[arg-type]
            self.stack.enter_context(self.blobs)  # type: ignore[arg-type]
```

##### memory的 pipeline

> 根据 memory 的流程解读, 顺序是，先 get，再执行，再 put；中间还可能穿插 put_writes。
> 这个流程的底层是，读取以前的checkpointer, 没有就创建，中间有执行状态（他以行为进行区分）放到 writes

##### memory.__init__.InMemorySaver.get_tuple

``` python
def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Get a checkpoint tuple from the in-memory storage.

        This method retrieves a checkpoint tuple from the in-memory storage based on the
        provided config. If the config contains a `checkpoint_id` key, the checkpoint with
        the matching thread ID and timestamp is retrieved. Otherwise, the latest checkpoint
        for the given thread ID is retrieved.

        Args:
            config: The config to use for retrieving the checkpoint.

        Returns:
            The retrieved checkpoint tuple, or None if no matching checkpoint was found.
        """
        thread_id: str = config["configurable"]["thread_id"]
        checkpoint_ns: str = config["configurable"].get("checkpoint_ns", "")
        if checkpoint_id := get_checkpoint_id(config):
            if saved := self.storage[thread_id][checkpoint_ns].get(checkpoint_id):
                checkpoint, metadata, parent_checkpoint_id = saved
                writes = self.writes[(thread_id, checkpoint_ns, checkpoint_id)].values()
                checkpoint_: Checkpoint = self.serde.loads_typed(checkpoint)
                return CheckpointTuple(
                    config=config,
                    checkpoint={
                        **checkpoint_,
                        "channel_values": self._load_blobs(
                            thread_id, checkpoint_ns, checkpoint_["channel_versions"]
                        ),
                    },
                    metadata=self.serde.loads_typed(metadata),
                    pending_writes=[
                        (id, c, self.serde.loads_typed(v)) for id, c, v, _ in writes
                    ],
                    parent_config=(
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": parent_checkpoint_id,
                            }
                        }
                        if parent_checkpoint_id
                        else None
                    ),
                )
        else:
            if checkpoints := self.storage[thread_id][checkpoint_ns]:
                checkpoint_id = max(checkpoints.keys())
                checkpoint, metadata, parent_checkpoint_id = checkpoints[checkpoint_id]
                writes = self.writes[(thread_id, checkpoint_ns, checkpoint_id)].values()
                checkpoint_ = self.serde.loads_typed(checkpoint)
                return CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": checkpoint_id,
                        }
                    },
                    checkpoint={
                        **checkpoint_,
                        "channel_values": self._load_blobs(
                            thread_id, checkpoint_ns, checkpoint_["channel_versions"]
                        ),
                    },
                    metadata=self.serde.loads_typed(metadata),
                    pending_writes=[
                        (id, c, self.serde.loads_typed(v)) for id, c, v, _ in writes
                    ],
                    parent_config=(
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": parent_checkpoint_id,
                            }
                        }
                        if parent_checkpoint_id
                        else None
                    ),
                )
```

##### memory.__init__.InMemorySaver.put

可以看下短期记忆的行为存储行为是什么, 让我先根据参数以及之前的对于参数规定猜测下。
只说这个 `new_versions: ChannelVersions` 之前，我写过，channel 其实就是参数本身，但是在 agent 中，参数运行的时候，并不是所有参数都需要更新，所以对每个参数都单独设立了 version, 所以这个会整合进 Checkpint, so let resume

同时，self.store作为

``` python
    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint to the in-memory storage.

        This method saves a checkpoint to the in-memory storage. The checkpoint is associated
        with the provided config.

        Args:
            config: The config to associate with the checkpoint.
            checkpoint: The checkpoint to save.
            metadata: Additional metadata to save with the checkpoint.
            new_versions: New versions as of this write

        Returns:
            RunnableConfig: The updated config containing the saved checkpoint's timestamp.
        """
        c = checkpoint.copy()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        values: dict[str, Any] = c.pop("channel_values")  # type: ignore[misc]
        for k, v in new_versions.items():
            self.blobs[(thread_id, checkpoint_ns, k, v)] = (
                self.serde.dumps_typed(values[k]) if k in values else ("empty", b"")
            )
        self.storage[thread_id][checkpoint_ns].update(
            {
                checkpoint["id"]: (
                    self.serde.dumps_typed(c),
                    self.serde.dumps_typed(get_checkpoint_metadata(config, metadata)),
                    config["configurable"].get("checkpoint_id"),  # parent
                )
            }
        )
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }
```

values: dict[str, Any] = c.pop("channel_values")  # type: ignore[misc]

这里重点提 `values` 其实就是 `channel value` 的过渡存储，你可以看到这样一个东西
在上层的 `pregel runtime` 会生成当前过渡态的消息，同时消息的事件戳保持一致，说明他们是同一时间发生的操作

具体为

``` python
`_new_version_` (更新状态):{'__start__': {'messages': [...]}} -> {'messages': [HumanMessage()], 'branch:to:model': None}
-> {'messages': [HumanMessage()], 'messages': [AIMessage()]} 有新的状态进入后大概就是这样，
```

所以这就是他的记忆流，甚至说状态流的更新方式。

下次要拜读下 `pregel` 的 paper

##### memory.__init__.InMemorySaver.put_writes

``` markdown

之前说记忆流的存储包含了过渡的信息，比如 {'branch:to:model' } 这种东西，明显的，
这种状态下。表明了消息的进行态，消息正在生成中，但是消息的生成也有成功和失败的两种情况
所以 `put_writes` 用于存储正在生成，但是消息进行态没走到最终态的时候的内容

他有一个 `outer_key` 标记单个 `checkpoint` 的标识，同时写入 self.write前会get下。估计也是保证消息处理的幂等性质。
putwrite 主要写入 self.write([])中，其形如

 (thread_id, checkpoint_ns, checkpoint_id): (task_id 当前对话消息的进度，由runtime生成，以及当前对话，需要write进去的东西的下标。)



```


``` python
def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Save a list of writes to the in-memory storage.

        This method saves a list of writes to the in-memory storage. The writes are associated
        with the provided config.

        Args:
            config: The config to associate with the writes.
            writes: The writes to save.
            task_id: Identifier for the task creating the writes.
            task_path: Path of the task creating the writes.

        Returns:
            RunnableConfig: The updated config containing the saved writes' timestamp.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]
        outer_key = (thread_id, checkpoint_ns, checkpoint_id)
        outer_writes_ = self.writes.get(outer_key)
        for idx, (c, v) in enumerate(writes):
            inner_key = (task_id, WRITES_IDX_MAP.get(c, idx))
            if inner_key[1] >= 0 and outer_writes_ and inner_key in outer_writes_:
                continue

            self.writes[outer_key][inner_key] = (
                task_id,
                c,
                self.serde.dumps_typed(v),
                task_path,
            )
```

##### memory.__init__.InMemorySaver.list

##### memory.__init__.InMemorySaver.delete_thread

以上两个就不说了，主要是针对内容的列举和删除，没有什么重大的逻辑存在

##### 关于 memory checkpoint 内容的生成和逻辑

ImemorySaver 作为了临时性质记忆存储工具，简短的揭示了记忆产生，存储，变化的逻辑

self.stores 用于存储checkpointe 各种版本号以及元数据

每一轮的对话，如果不是resume或者fork的状态，都会产生新的checkpoint id，用于存储每一轮发生的channel的变化

其中channel的变化使用channel_value（规定的参数的值）以及new_version（channel的变化行为）去配合更新
new_version 由上游的 pregel runtime 分配执行状态，看下来有 __start__ ,__loop__,等等存储在
self.blobs 通过键值的方式的进行更新

self.write则存中间态的行为

源码位置：`.venv/Lib/site-packages/langgraph/checkpoint/`

TODO

---

## 5. langgraph.config


源码位置：`.venv/Lib/site-packages/langgraph/config.py`



TODO

---

## 6. langgraph.constants


源码位置：`.venv/Lib/site-packages/langgraph/constants.py`



TODO

---

## 7. langgraph.errors


源码位置：`.venv/Lib/site-packages/langgraph/errors.py`



TODO

---

## 8. langgraph.func


源码位置：`.venv/Lib/site-packages/langgraph/func/`



TODO

---

## 9. langgraph.graph

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

### add_node

在 `create_agent` 方法中，agent 对于 `before/after/agent/model`等等中间件，通过 `add_node` 以及 `add_edage` 方法进行了组合，
其中 `add_node` 是添加可执行节点，`add_edage` 则是添加可执行的路径（即比如middleware执行顺序是 before_Agent->beforemodel等）。但是具体他们是怎么组合的呢？

``` python
def add_node(
        self,
        node: str | StateNode[NodeInputT, ContextT],
        action: StateNode[NodeInputT, ContextT] | None = None,
        *,
        defer: bool = False,
        metadata: dict[str, Any] | None = None,
        input_schema: type[NodeInputT] | None = None,
        retry_policy: RetryPolicy | Sequence[RetryPolicy] | None = None,
        cache_policy: CachePolicy | None = None,
        destinations: dict[str, str] | tuple[str, ...] | None = None,
        **kwargs: Unpack[DeprecatedKwargs],
    ) -> Self:
        """Add a new node to the `StateGraph`.

        Args:
            node: The function or runnable this node will run.

                If a string is provided, it will be used as the node name, and action will be used as the function or runnable.
            action: The action associated with the node.
                Will be used as the node function or runnable if `node` is a string (node name).
            defer: Whether to defer the execution of the node until the run is about to end.
            metadata: The metadata associated with the node.
            input_schema: The input schema for the node. (Default: the graph's state schema)
            retry_policy: The retry policy for the node.

                If a sequence is provided, the first matching policy will be applied.
            cache_policy: The cache policy for the node.
            destinations: Destinations that indicate where a node can route to.

                Useful for edgeless graphs with nodes that return `Command` objects.

                If a `dict` is provided, the keys will be used as the target node names and the values will be used as the labels for the edges.

                If a `tuple` is provided, the values will be used as the target node names.

                !!! note

                    This is only used for graph rendering and doesn't have any effect on the graph execution.

        Example:
            ```python
            from typing_extensions import TypedDict

            from langchain_core.runnables import RunnableConfig
            from langgraph.graph import START, StateGraph


            class State(TypedDict):
                x: int


            def my_node(state: State, config: RunnableConfig) -> State:
                return {"x": state["x"] + 1}


            builder = StateGraph(State)
            builder.add_node(my_node)  # node name will be 'my_node'
            builder.add_edge(START, "my_node")
            graph = builder.compile()
            graph.invoke({"x": 1})
            # {'x': 2}
            ```

        Example: Customize the name:
            ```python
            builder = StateGraph(State)
            builder.add_node("my_fair_node", my_node)
            builder.add_edge(START, "my_fair_node")
            graph = builder.compile()
            graph.invoke({"x": 1})
            # {'x': 2}
            ```

        Returns:
            Self: The instance of the `StateGraph`, allowing for method chaining.
        """
        if (retry := kwargs.get("retry", MISSING)) is not MISSING:
            warnings.warn(
                "`retry` is deprecated and will be removed. Please use `retry_policy` instead.",
                category=LangGraphDeprecatedSinceV05,
            )
            if retry_policy is None:
                retry_policy = retry  # type: ignore[assignment]

        if (input_ := kwargs.get("input", MISSING)) is not MISSING:
            warnings.warn(
                "`input` is deprecated and will be removed. Please use `input_schema` instead.",
                category=LangGraphDeprecatedSinceV05,
            )
            if input_schema is None:
                input_schema = cast(type[NodeInputT] | None, input_)

        if not isinstance(node, str):
            action = node
            if isinstance(action, Runnable):
                node = action.get_name()
            else:
                node = getattr(action, "__name__", action.__class__.__name__)
            if node is None:
                raise ValueError(
                    "Node name must be provided if action is not a function"
                )
        if self.compiled:
            logger.warning(
                "Adding a node to a graph that has already been compiled. This will "
                "not be reflected in the compiled graph."
            )
        if not isinstance(node, str):
            action = node
            node = cast(str, getattr(action, "name", getattr(action, "__name__", None)))
            if node is None:
                raise ValueError(
                    "Node name must be provided if action is not a function"
                )
        if action is None:
            raise RuntimeError
        if node in self.nodes:
            raise ValueError(f"Node `{node}` already present.")
        if node == END or node == START:
            raise ValueError(f"Node `{node}` is reserved.")

        for character in (NS_SEP, NS_END):
            if character in node:
                raise ValueError(
                    f"'{character}' is a reserved character and is not allowed in the node names."
                )

        inferred_input_schema = None

        ends: tuple[str, ...] | dict[str, str] = EMPTY_SEQ
        try:
            if (
                isfunction(action)
                or ismethod(action)
                or ismethod(getattr(action, "__call__", None))
            ) and (
                hints := get_type_hints(getattr(action, "__call__"))
                or get_type_hints(action)
            ):
                if input_schema is None:
                    first_parameter_name = next(
                        iter(
                            inspect.signature(
                                cast(FunctionType, action)
                            ).parameters.keys()
                        )
                    )
                    if input_hint := hints.get(first_parameter_name):
                        if isinstance(input_hint, type) and get_type_hints(input_hint):
                            inferred_input_schema = input_hint
                if rtn := hints.get("return"):
                    # Handle Union types
                    rtn_origin = get_origin(rtn)
                    if rtn_origin is Union:
                        rtn_args = get_args(rtn)
                        # Look for Command in the union
                        for arg in rtn_args:
                            arg_origin = get_origin(arg)
                            if arg_origin is Command:
                                rtn = arg
                                rtn_origin = arg_origin
                                break

                    # Check if it's a Command type
                    if (
                        rtn_origin is Command
                        and (rargs := get_args(rtn))
                        and get_origin(rargs[0]) is Literal
                        and (vals := get_args(rargs[0]))
                    ):
                        ends = vals
        except (NameError, TypeError, StopIteration):
            pass

        if destinations is not None:
            ends = destinations

        if input_schema is not None:
            self.nodes[node] = StateNodeSpec[NodeInputT, ContextT](
                coerce_to_runnable(action, name=node, trace=False),  # type: ignore[arg-type]
                metadata,
                input_schema=input_schema,
                retry_policy=retry_policy,
                cache_policy=cache_policy,
                ends=ends,
                defer=defer,
            )
        elif inferred_input_schema is not None:
            self.nodes[node] = StateNodeSpec(
                coerce_to_runnable(action, name=node, trace=False),  # type: ignore[arg-type]
                metadata,
                input_schema=inferred_input_schema,
                retry_policy=retry_policy,
                cache_policy=cache_policy,
                ends=ends,
                defer=defer,
            )
        else:
            self.nodes[node] = StateNodeSpec[StateT, ContextT](
                coerce_to_runnable(action, name=node, trace=False),  # type: ignore[arg-type]
                metadata,
                input_schema=self.state_schema,
                retry_policy=retry_policy,
                cache_policy=cache_policy,
                ends=ends,
                defer=defer,
            )

        input_schema = input_schema or inferred_input_schema
        if input_schema is not None:
            self._add_schema(input_schema)

        return self

```

`add_node` 用于把可执行StateGraph 定义的 node 节点容器中 `nodes: dict[str, StateNodeSpec[Any, ContextT]]`。并返回一个当前的实例对象
`add_node` 的核心职责就是把执行节点封装为StateNode的类型，同时把可执行节点的函数转为 `Runnale` 对象，附带该节点的走向，元数据等等，最主要的一点是 Runnble对象支持 invoke和ainvoke对象, 用 `asyncio` 的 `run_in_executor` 进行封装, 针对input的state，没输入直接从Graph的SatateSchema 拿，如果规定了自己的参数就用自己的

`add_edge` 这个没撒好说的，节点之间的路径存储到N->1的路的set集合，里面是元组但是只是放到了`waiting_edges: set[tuple[tuple[str, ...], str]]` 有点和记忆的写入 self.writes有一种同样的感觉

`add_sequence` 将一系列的可执行节点装入node节点中

`add_conditional_edges` 条件链路通过
`branches: defaultdict[str, dict[str, BranchSpec]]` 也形成的是当前的StateGraph

``

| 参数 | 含义 |
| --- | --- |
| `node` | 节点名或节点函数。如果传入 `str`，它表示节点名；如果传入 `StateNode`，它本身就是节点要执行的函数或 `Runnable`，节点名会从函数名或 `Runnable` 名推导。 |
| `action` | 节点实际执行的函数或 `Runnable`。只有当 `node` 是字符串节点名时才需要传。 |
| `defer` | 是否延迟执行该节点，直到当前 run 接近结束时再执行。 |
| `metadata` | 节点元数据，主要用于调试、追踪或图展示。 |
| `input_schema` | 当前节点的输入 schema。默认Stategrap定义的 的 `state_schema`。 |
| `retry_policy` | 节点执行失败时的重试策略。 |
| `cache_policy` | 节点缓存策略。 |
| `destinations` | 声明该节点可能跳转到哪些目标节点，主要用于图可视化和 `Command` 返回值的目标标注。 |

### compile

> 图编译，这里是定义好的图结构转向 `CompiledStateGraph` 的转换方法

``` python
def compile(
        self,
        checkpointer: Checkpointer = None,
        *,
        cache: BaseCache | None = None,
        store: BaseStore | None = None,
        interrupt_before: All | list[str] | None = None,
        interrupt_after: All | list[str] | None = None,
        debug: bool = False,
        name: str | None = None,
    ) -> CompiledStateGraph[StateT, ContextT, InputT, OutputT]:
        """Compiles the `StateGraph` into a `CompiledStateGraph` object.

        The compiled graph implements the `Runnable` interface and can be invoked,
        streamed, batched, and run asynchronously.

        Args:
            checkpointer: A checkpoint saver object or flag.

                If provided, this `Checkpointer` serves as a fully versioned "short-term memory" for the graph,
                allowing it to be paused, resumed, and replayed from any point.

                If `None`, it may inherit the parent graph's checkpointer when used as a subgraph.

                If `False`, it will not use or inherit any checkpointer.

                **Important**: When a checkpointer is enabled, you should pass a `thread_id`
                in the config when invoking the graph:

                ```python
                config = {"configurable": {"thread_id": "my-thread"}}
                graph.invoke(inputs, config)
                ```

                The `thread_id` is the key used to store and retrieve checkpoints. Use a
                unique ID for independent runs, or reuse the same ID to accumulate state
                across invocations (e.g., for conversation memory).

            interrupt_before: An optional list of node names to interrupt before.
            interrupt_after: An optional list of node names to interrupt after.
            debug: A flag indicating whether to enable debug mode.
            name: The name to use for the compiled graph.

        Returns:
            CompiledStateGraph: The compiled `StateGraph`.
        """
        checkpointer = ensure_valid_checkpointer(checkpointer)
        serde_allowlist: set[tuple[str, ...]] | None = None
        if _serde.STRICT_MSGPACK_ENABLED:
            schema_types: list[type[Any]] = [
                self.state_schema,
                self.input_schema,
                self.output_schema,
            ]
            if self.context_schema is not None:
                schema_types.append(self.context_schema)
            for node in self.nodes.values():
                schema_types.append(node.input_schema)
            for branches in self.branches.values():
                for branch in branches.values():
                    if branch.input_schema is not None:
                        schema_types.append(branch.input_schema)
            serde_allowlist = _serde.build_serde_allowlist(
                schemas=schema_types,
                channels=self.channels,
            )
            checkpointer = _serde.apply_checkpointer_allowlist(
                checkpointer, serde_allowlist
            )

        # assign default values
        interrupt_before = interrupt_before or []
        interrupt_after = interrupt_after or []

        # validate the graph
        self.validate(
            interrupt=(
                (interrupt_before if interrupt_before != "*" else []) + interrupt_after
                if interrupt_after != "*"
                else []
            )
        )

        # prepare output channels
        output_channels = (
            "__root__"
            if len(self.schemas[self.output_schema]) == 1
            and "__root__" in self.schemas[self.output_schema]
            else [
                key
                for key, val in self.schemas[self.output_schema].items()
                if not is_managed_value(val)
            ]
        )
        stream_channels = (
            "__root__"
            if len(self.channels) == 1 and "__root__" in self.channels
            else [
                key for key, val in self.channels.items() if not is_managed_value(val)
            ]
        )

        compiled = CompiledStateGraph[StateT, ContextT, InputT, OutputT](
            builder=self,
            schema_to_mapper={},
            context_schema=self.context_schema,
            nodes={},
            channels={
                **self.channels,
                **self.managed,
                START: EphemeralValue(self.input_schema),
            },
            input_channels=START,
            stream_mode="updates",
            output_channels=output_channels,
            stream_channels=stream_channels,
            checkpointer=checkpointer,
            interrupt_before_nodes=interrupt_before,
            interrupt_after_nodes=interrupt_after,
            auto_validate=False,
            debug=debug,
            store=store,
            cache=cache,
            name=name or "LangGraph",
        )
        compiled._serde_allowlist = serde_allowlist

        compiled.attach_node(START, None)
        for key, node in self.nodes.items():
            compiled.attach_node(key, node)

        # Record output/state mappers for v2 stream coercion (pydantic/dataclass only)
        compiled._output_mapper = _pick_mapper(
            list(output_channels)
            if isinstance(output_channels, list)
            else [output_channels],
            self.output_schema,
        )
        compiled._state_mapper = _pick_mapper(
            list(stream_channels)
            if isinstance(stream_channels, list)
            else [stream_channels],
            self.state_schema,
        )

        for start, end in self.edges:
            compiled.attach_edge(start, end)

        for starts, end in self.waiting_edges:
            compiled.attach_edge(starts, end)

        for start, branches in self.branches.items():
            for name, branch in branches.items():
                compiled.attach_branch(start, name, branch)

        return compiled.validate()

```

## 10. langgraph_sdk

## 11. langgraph_sdk

源码位置：`.venv/Lib/site-packages/langgraph_sdk/`

TODO

---

## 12. langgraph.managed

源码位置：`.venv/Lib/site-packages/langgraph/managed/`

TODO

---

## 13. langgraph.prebuilt


源码位置：`.venv/Lib/site-packages/langgraph/prebuilt/`



TODO

---

## 14. langgraph.pregel

源码位置：`.venv/Lib/site-packages/langgraph/pregel/`

### langgraph.pregel.main.Prgel

`Prgel` 是langgraph的核心，管理整个 lannggraph 的流程

官方说的是

Pregel combines [**actors**](https://en.wikipedia.org/wiki/Actor_model)
and **channels** into a single application.
**Actors** read data from channels and write data to channels.
Pregel organizes the execution of the application into multiple steps,
following the **Pregel Algorithm**/**Bulk Synchronous Parallel** model.

结合了 **actors** 和 **channels** 两种，前者操纵信道读写数据同时，Pregel 将ap的运行拆分为数个步骤
同时遵循Pregel算法和Bulk Synchronous Parallel，你问我这是啥，我怎么知道?

``` python

class Pregel(
    PregelProtocol[StateT, ContextT, InputT, OutputT],
    Generic[StateT, ContextT, InputT, OutputT],
):

```

粗看下代码，首先，`Pregel` 定义了图的行为以及一堆的参数, `StateGraph` 类通过添加 `add_edage` and `add_node` 后，调用`compile` 方法返回 `CompiledStateGraph`，`CompiledStateGraph` 又继承了 `Pregel`，所以直接调用 `invoke/ainvoke`，`stream/astream` 直接触发整个Graph的执行

这里就要把 `Pregel`, `StateGraph`, `CompiledStateGraph`串行讲述。

`Pregel` 定义的是“编译后图”的运行时协议和实例化后的执行机制以及图属性，方便图的执行， `StateGraph` 则是用于创建图的先遣状态，在编译后形成了`CompiledStateGraph` ，而 `CompiledStateGraph` 又继承了 `Pregel` 最终形成了图的路径，同时也可使用图的状态


TODO

---

## 15. langgraph.runtime

源码位置：`.venv/Lib/site-packages/langgraph/runtime.py`


TODO

---

## 16. langgraph.store


源码位置：`.venv/Lib/site-packages/langgraph/store/`



TODO

---

## 17. langgraph.types


源码位置：`.venv/Lib/site-packages/langgraph/types.py`



TODO

---

## 18. langgraph.typing


源码位置：`.venv/Lib/site-packages/langgraph/typing.py`



TODO

---

## 19. langgraph.utils


源码位置：`.venv/Lib/site-packages/langgraph/utils/`



TODO

---

## 20. langgraph.version


源码位置：`.venv/Lib/site-packages/langgraph/version.py`



TODO

---

## 21. langgraph.warnings


源码位置：`.venv/Lib/site-packages/langgraph/warnings.py`



TODO

---

## 22. langgraph._internal


源码位置：`.venv/Lib/site-packages/langgraph/_internal/`



TODO
