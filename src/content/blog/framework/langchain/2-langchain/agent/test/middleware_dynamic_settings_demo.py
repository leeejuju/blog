from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ModelRequest,
    ModelResponse,
)
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import BaseMessage


class EchoSettingsChatModel(FakeChatModel):
    """Fake model that returns the runtime kwargs it received."""

    def _call(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> str:
        return (
            "model received settings: "
            f"temperature={kwargs.get('temperature')}, "
            f"max_tokens={kwargs.get('max_tokens')}"
        )


class DynamicModelSettingsMiddleware(AgentMiddleware[AgentState, None]):
    """Modify model parameters dynamically before the model call."""

    def wrap_model_call(
        self,
        request: ModelRequest[None],
        handler: Callable[[ModelRequest[None]], ModelResponse],
    ) -> ModelResponse:
        user_text = "\n".join(message.text for message in request.messages)

        if "detailed" in user_text.lower():
            new_settings = {
                **request.model_settings,
                "temperature": 0.2,
                "max_tokens": 2000,
            }
        else:
            new_settings = {
                **request.model_settings,
                "temperature": 0,
                "max_tokens": 200,
            }

        print("middleware changed model_settings:", new_settings)
        return handler(request.override(model_settings=new_settings))


def main() -> None:
    print("building agent")
    agent = create_agent(
        model=EchoSettingsChatModel(),
        tools=[],
        middleware=[DynamicModelSettingsMiddleware()],
    )

    print("invoke short")
    short_result = agent.invoke(
        {"messages": [{"role": "user", "content": "short answer"}]},
        config={"recursion_limit": 2},
    )
    print(short_result["messages"][-1].content)
    print()

    print("invoke detailed")
    detailed_result = agent.invoke(
        {"messages": [{"role": "user", "content": "detailed answer please"}]},
        config={"recursion_limit": 2},
    )
    print(detailed_result["messages"][-1].content)


if __name__ == "__main__":
    main()
