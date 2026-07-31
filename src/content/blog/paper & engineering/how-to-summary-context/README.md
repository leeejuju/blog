---
title: "How to Summary Context：对话历史的压缩机制"
description: "LLM Agent 长对话上下文的压缩策略：从朴素截断到 Token 级剪枝，探讨摘要在 LangChain 与 LangGraph 中的实现路径"
pubDate: 2026-07-05
section: engineering
---

# How to Summary Context：对话历史的压缩机制

## 问题定义

LLM Agent 在执行长任务时，上下文窗口是有限的。当对话历史不断增长，会在以下维度产生问题：

- **Token 超限**：超出模型最大输入 token 数，请求直接失败
- **成本膨胀**：每次请求携带全部历史，输入 token 消耗线性增长
- **注意力稀释**：模型对长上下文中部的信息检索能力下降（Lost in the Middle）

压缩的目标：**在保留任务关键信息的前提下，减少上下文占用**。

## 压缩策略分类

### 朴素截断

最简单的策略：保留最近 N 条消息，丢弃更早的内容。

- 优点：零延迟，无额外 token 消耗
- 缺点：丢失早期关键信息（任务目标、约束、已产生的产物），容易导致 Agent 行为漂移

### LLM 驱动摘要

用一个（通常是更便宜的）模型对历史对话进行摘要，用摘要替换原始历史。

LangChain 的 `SummarizationMiddleware` 即采用此策略。

### Token 级剪枝

不对对话进行语义压缩，而是删除"低价值"的 token/消息块。例如将过大的 tool 结果替换为文件路径引用。

LangChain 的 `context_editing.py` 即属于此类：

> This middleware automatically filters and replaces tool results that exceed token limits, keeping messages within acceptable bounds.

对超出 token 界限的历史会话进行过滤并将其替换为 placeholder。快速裁切过往冗余的详细工具结果，精简上下文。

### 层次化记忆

将上下文分为多层：热记忆（最近对话）、温记忆（摘要）、冷记忆（持久化存储，按需检索）。LangChain 的 `SummarizationMiddleware` + `FilesystemBackend` 组合即是此模式。

## 压缩时机

压缩策略的关键问题之一是**何时触发**压缩：

| 触发方式 | 机制 | 适用场景 |
|----------|------|----------|
| 固定阈值 | 达到模型上下文的一定比例（如 85%）自动触发 | 通用场景 |
| Agent 自主触发 | 通过 `compact_conversation` tool，由模型判断时机 | DeepAgent |
| 溢出兜底 | `ContextOverflowError` 时立即 fallback 压缩 | 所有场景 |

---

## LangChain SummarizationMiddleware

### 概述

> summarization，是一个需要思考的东西。不同的业务场景下，压缩的对象也应该是不同的。coding 下对于任务的连续性就很重要，但是你换到其他行业就不一定了，而且压缩的重点也各不相同。

`SummarizationMiddleware` 是 LangChain 内置的上下文压缩中间件。它在 token 数量接近上限时自动对较早的历史消息进行摘要式压缩并替换，优化上下文窗口占用，控制长会话下的计算与输入 token 成本。

### 压缩 Prompt

以下是 LangChain 压缩时使用的 prompt。LangChain 作为一个 Agent SDK，提供的是单个通用 prompt，`SummarizationMiddleware` 本身是个样板，策略上不像 Claude Code 或 Codex 那样复杂。主要分为 role、primary objective、objective information、instructions 几个部分。

#### role, primary objective, objective information

- **role**：Context Extraction Assistant
- **primary objective**：Prompt 的唯一任务就是根据历史对话，提取高质量/最相关的上下文
- **objective information**：当接近可接受的输入 token 上限时，根据历史对话提取高价值的历史/与对话最相关的上下文。提取出的上下文将会重写提供的对话历史，因此需要确保压缩信息对任务目标有用

#### instruction

- **SESSION INTENT（会话意图）**：确定用户的主要意图和请求，任务目标是什么。意图的总结需要足够简洁和充分，能理解对话的整个意图
- **SUMMARY（总结）**：从历史会话提取并记录所有重要内容，包括重要的选择、结论以及对话中的策略选择，以及重要决策背后的推理逻辑。记录下所有拒绝的选项，并且说明为何没有采用
- **ARTIFACTS（产物）**：产出了什么文件？整个对话（agent 执行）期间有无资源被访问、修改、创建？如果改了，说清楚改了什么，以及改的路径。（主要是为了防止丢失以及 rewind）
- **NEXT STEPS**：离完成任务还有几步？下一步要干什么

#### 原始 Prompt

```text
<role>
Context Extraction Assistant
</role>

<primary_objective>
Your sole objective in this task is to extract the highest quality/most relevant context from the conversation history below.
</primary_objective>

<objective_information>
You're nearing the total number of input tokens you can accept, so you must extract the highest quality/most relevant pieces of information from your conversation history.
This context will then overwrite the conversation history presented below. Because of this, ensure the context you extract is only the most important information to continue working toward your overall goal.
</objective_information>

<instructions>
The conversation history below will be replaced with the context you extract in this step.
You want to ensure that you don't repeat any actions you've already completed, so the context you extract from the conversation history should be focused on the most important information to your overall goal.

You should structure your summary using the following sections. Each section acts as a checklist - you must populate it with relevant information or explicitly state "None" if there is nothing to report for that section:

## SESSION INTENT
What is the user's primary goal or request? What overall task are you trying to accomplish? This should be concise but complete enough to understand the purpose of the entire session.

## SUMMARY
Extract and record all of the most important context from the conversation history. Include important choices, conclusions, or strategies determined during this conversation. Include the reasoning behind key decisions. Document any rejected options and why they were not pursued.

## ARTIFACTS
What artifacts, files, or resources were created, modified, or accessed during this conversation? For file modifications, list specific file paths and briefly describe the changes made to each. This section prevents silent loss of artifact information.

## NEXT STEPS
What specific tasks remain to be completed to achieve the session intent? What should you do next?

</instructions>

The user will message you with the full message history from which you'll extract context to create a replacement. Carefully read through it all and think deeply about what information is most important to your overall goal and should be saved:

With all of this in mind, please carefully read over the entire conversation history, and extract the most important and relevant context to replace it so that you can free up space in the conversation history.
Respond ONLY with the extracted context. Do not include any additional information, or text before or after the extracted context.

<messages>
Messages to summarize:
{messages}
</messages>
```

### 小结

LangChain 的压缩策略从对话、回溯、记忆、以及任务等方面对上下文进行拆分提取。对于一般的对话来说是够用的，但对于 Claude Code、Codex 这类 coding agent 的 harness 场景来说还不够。下面看 Claude Code 是如何 compact 上下文的。

---

## Claude Code Compact Strategy

像 Claude Code 和 Codex 这样的 coding agent，执行中涉及终端原生命令（如 rg、grep）、项目文件、CLAUDE.md 配置、代码变更、工具调用结果、中断、执行结果等。上下文结构远比普通对话复杂。

对于 Claude Code（这里只看 `/compact` 路径）：

### NO_TOOLS_PREAMBLE — 禁止调用工具

触发压缩时，Claude Code 首先将 `NO_TOOLS_PREAMBLE` 放在前面：

```markdown
CRITICAL: Respond with TEXT ONLY. Do NOT call any tools.

- Do NOT use Read, Bash, Grep, Glob, Edit, Write, or ANY other tool.
- You already have all the context you need in the conversation above.
- Tool calls will be REJECTED and will waste your only turn — you will fail the task.
- Your entire response must be plain text: an <analysis> block followed by a <summary> block.
```

Anthropic 在设计时反复强调不允许调用工具，并且枚举了禁止的工具，陈述了违规的后果。这种 **禁止 + 陈述利弊 + 再次要求** 的引导方式，目的是将模型输出倾向引导为直接输出内容，而非习惯性地发起 tool call。

### DETAILED_ANALYSIS_INSTRUCTION_BASE — 分析的精确性要求

```text
Before providing your final summary, wrap your analysis in <analysis> tags to organize your thoughts and ensure you've covered all necessary points. In your analysis process:

1. Chronologically analyze each message and section of the conversation. For each section thoroughly identify:
   - The user's explicit requests and intents
   - Your approach to addressing the user's requests
   - Key decisions, technical concepts and code patterns
   - Specific details like:
     - file names
     - full code snippets
     - function signatures
     - file edits
   - Errors that you ran into and how you fixed them
   - Pay special attention to specific user feedback that you received, especially if the user told you to do something differently.
2. Double-check for technical accuracy and completeness, addressing each required element thoroughly.
```

这段是对填充内容的**分析要求**。要求在给出结果前，在 `<analysis>` 标签里组织语言，并确保生成内容涵盖以下要点：

- **渐进式分析**所选对话的每个消息，每个消息需囊括：
    1. 用户的意图和需求
    2. 处理用户需求的方案方法
    3. 关键决策、技术概念和代码模式/结构
    4. 特定细节：文件名、完整代码、函数签名、文件改动
    5. 遇到的错误及解决方案
    6. 尤其注意（**pay special attention**）用户的反馈，尤其是要求做出调整的地方
- **反复检查**技术的准确性、总结分析的完整性，确保完备处理每个所需元素

### BASE_COMPACT_PROMPT — 核心压缩 Prompt

```text
Your task is to create a detailed summary of the conversation so far, paying close attention to the user's explicit requests and your previous actions.
This summary should be thorough in capturing technical details, code patterns, and architectural decisions that would be essential for continuing development work without losing context.
```

这里用了一个词 **paying close attention** to the user's explicit requests and your previous actions。总结需要：

> **捕捉技术细节、代码模式/结构、以及对于继续开发任务不可或缺的结构性决策**

重点关注的是历史行为和用户的**清晰请求**。总结需要涵盖：**技术细节**、**代码样式**、**不可或缺的、结构性的对于继续开发任务至关重要的决定**。

### 压缩内容的 9 个维度

```text
Your summary should include the following sections:

1. Primary Request and Intent: Capture all of the user's explicit requests and intents in detail
2. Key Technical Concepts: List all important technical concepts, technologies, and frameworks discussed.
3. Files and Code Sections: Enumerate specific files and code sections examined, modified, or created. Pay special attention to the most recent messages and include full code snippets where applicable and include a summary of why this file read or edit is important.
4. Errors and fixes: List all errors that you ran into, and how you fixed them. Pay special attention to specific user feedback that you received, especially if the user told you to do something differently.
5. Problem Solving: Document problems solved and any ongoing troubleshooting efforts.
6. All user messages: List ALL user messages that are not tool results. These are critical for understanding the users' feedback and changing intent.
7. Pending Tasks: Outline any pending tasks that you have explicitly been asked to work on.
8. Current Work: Describe in detail precisely what was being worked on immediately before this summary request, paying special attention to the most recent messages from both user and assistant. Include file names and code snippets where applicable.
9. Optional Next Step: List the next step that you will take that is related to the most recent work you were doing. IMPORTANT: ensure that this step is DIRECTLY in line with the user's most recent explicit requests, and the task you were working on immediately before this summary request. If your last task was concluded, then only list next steps if they are explicitly in line with the users request. Do not start on tangential requests or really old requests that were already completed without confirming with the user first.
                       If there is a next step, include direct quotes from the most recent conversation showing exactly what task you were working on and where you left off. This should be verbatim to ensure there's no drift in task interpretation.
```

详细拆解：

1. **Primary Request and Intent（主要需求/意图）**：捕捉用户所有清晰的需求和意图的细节
2. **Key Technical Concepts（关键技术概念）**：列出所有重要的技术概念、技术以及框架/架构上的讨论
3. **Files and Code Sections（文件和代码）**：枚举所有修改、检查、创建的指定文件和代码，尤其关注最新的消息，包含全部可用的代码片段，同时附上为何读取/修改该文件重要性的总结
4. **Errors and fixes（错误与修复）**：列举遇到的所有错误，以及对应的修改方案。尤其注意用户的反馈以及用户要求的修改/修复方式
5. **Problem Solving（问题处理）**：记录所有已经解决的问题以及正在定位中的问题（注意：问题不一定就是错误）
6. **All user messages（用户消息）**：列举出所有非 tool call 的用户消息，这些有助于理解用户的反馈和用户意图是否变化
7. **Pending Tasks（待处理任务）**：描述已经发出并且正在进行中的任务
8. **Current Work（当前任务）**：在总结历史前，以精确文字描述当前正在处理的任务，重点关注 AI 的回答和用户的消息，包含文件名称和代码实例
9. **Optional Next Step（可选下一步）**：根据当前任务列举出下一步最相关的任务。注意确保当前步骤和用户最近的需求一致，如果是上一步任务已经结束且下一步清晰符合用户需求则列举。要确保向用户确认，不要从老任务或无关任务开始。如果有下一步，需从最近对话中原封不动地引用，确保任务理解不漂移

### NO_TOOLS_TRAILER — 尾端再次强调

```text
REMINDER: Do NOT call any tools. Respond with plain text only —
an <analysis> block followed by a <summary> block.
Tool calls will be rejected and you will fail the task.
```

在长 prompt 末尾再次拼接 `NO_TOOLS_TRAILER`，防止长文本稀释开头的约束，在尾端再做一次强调。

### Claude Code Compact Prompt 特点总结

1. **不以轮数作为压缩单位**：没有规定保留多少轮对话
2. **而是着重于**：文件修改、历史对话、技术细节、错误及修复原因、任务状态
3. **以 diff 为主的工程性变动**为总结对象，而非对话性质的压缩
4. **首尾双重约束**：在 prompt 头部和尾部均禁止 tool call，防止长文本稀释导致模型"忘记"
5. **verbatim 引用**：下一步任务需原封不动引用对话原文，防止任务理解漂移

---

## LangChain vs Claude Code 压缩策略对比

| 维度 | LangChain SummarizationMiddleware | Claude Code Compact |
|------|----------------------------------|---------------------|
| **触发方式** | 固定阈值（fraction/tokens/messages） | 系统调度 + /compact 命令 |
| **压缩对象** | 对话历史消息 | 对话历史 + 工具调用结果 + 文件变更 |
| **摘要结构** | 4 段：Intent / Summary / Artifacts / Next Steps | 9 段：含错误修复、代码片段、用户反馈、verbatim 引用 |
| **代码/文件** | 仅记录路径和简要描述 | 完整代码片段 + 修改原因 + 重要性说明 |
| **错误处理** | 不明确 | 详细记录错误 + 修复方式 + 用户反馈 |
| **防漂移** | 无显式机制 | verbatim 引用 + Current Work + 首尾双重约束 |
| **Tool 禁止** | 无 | 首尾双重 NO_TOOLS_PREAMBLE / TRAILER |
| **定位** | 通用 Agent 框架样板 | Coding Agent 专用 |

两者侧重的对象异曲同工：都包含了用户意图、执行过程中的错误及修改方式、文件的生成和创建等。但 Claude Code 的设计更加细致且科学——它针对 coding agent 的特殊需求，将总结维度从 4 个拓展到 9 个，并通过首尾约束、verbatim 引用等方式防止任务漂移。

---

## langchain 和 claude 的压缩策略共性

看两边 prompt 的设计，有个很明显的规律——**压缩发生在输入侧**

为啥？压缩完之后模型要靠这一小撮上下文接着干活。什么信息丢了就真丢了？用户说过的话。用户的需求、纠偏、"别这样搞"、"换个方式"——这些是驱动任务不跑偏的锚点。工具调用的结果丢了可以重新跑，文件内容丢了可以重新读，但用户输入一旦裁掉就没了，模型只能猜。

证据在哪：

- LangChain 的 `SESSION INTENT`，问的就是"用户到底要什么"
- Claude Code 的 `All user messages`，要求把非 tool 结果的用户消息全列出来，原话是 **"critical for understanding the users' feedback and changing intent"**
- 错误修复那栏也强调 **"especially if the user told you to do something differently"**——多次强调用户输出的信息比代码片段本身重要

## 关键权衡

在设计上下文压缩策略时，需要在以下维度间做权衡：

1. **压缩率 vs 信息保真度**：压缩越激进，信息损失越大
2. **延迟 vs 质量**：用便宜模型做摘要（如 gpt-4o-mini）成本低但可能丢失细节；用主模型做摘要质量高但增加了 token 消耗和延迟
3. **通用性 vs 领域特化**：LangChain 的通用 prompt 适用于各种对话场景，但 coding 场景需要更精细的 prompt 设计
4. **自动触发 vs Agent 自主触发**：固定阈值简单可靠，但 Agent 自主触发可以在更自然的时机（任务完成、切换任务前）进行压缩

## 参考

- [LangChain SummarizationMiddleware 源码](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/deepagents/middleware/summarization.py)
- [Claude Code Compact Prompt（泄露源码）](https://github.com/anthropics/claude-code)
