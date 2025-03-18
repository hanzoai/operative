"""
Agentic sampling loop that calls the Anthropic API using the modern AsyncAnthropic client
and its streaming response interface for beta computer use.
"""

import platform
import asyncio
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import Any, cast

import httpx
from anthropic import APIError, APIResponseValidationError, APIStatusError
from anthropic.types.beta import (
    BetaCacheControlEphemeralParam,
    BetaContentBlockParam,
    BetaImageBlockParam,
    BetaMessage,
    BetaMessageParam,
    BetaTextBlock,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
    BetaToolUseBlockParam,
)

from .tools import TOOL_GROUPS_BY_VERSION, ToolCollection, ToolResult, ToolVersion

# Used if prompt caching is enabled.
PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"


class APIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are utilising an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* You can install Ubuntu applications with your bash tool (use curl, not wget).
* To open Firefox, simply click its icon (firefox-esr is installed).
* GUI apps launched via the bash tool may take a moment to appear.
* For very large outputs, consider redirecting to a file.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>

<IMPORTANT>
* Ignore any Firefox startup wizards – simply click the address bar and enter your URL.
* For PDFs, if you need the full text instead of screenshots, download and convert with pdftotext.
</IMPORTANT>"""


async def sampling_loop(
    *,
    model: str,
    provider: APIProvider,
    system_prompt_suffix: str,
    messages: list[BetaMessageParam],
    output_callback: Callable[[BetaContentBlockParam], None],
    tool_output_callback: Callable[[ToolResult, str], None],
    api_response_callback: Callable[
        [httpx.Request | None, httpx.Response | object | None, Exception | None], None
    ],
    api_key: str,
    only_n_most_recent_images: int | None = None,
    max_tokens: int = 4096,
    tool_version: ToolVersion,
    thinking_budget: int | None = None,
    token_efficient_tools_beta: bool = False,
) -> list[BetaMessageParam]:
    """
    Sampling loop using the modern AsyncAnthropic client with streaming.
    Works with and without thinking enabled.
    """
    tool_group = TOOL_GROUPS_BY_VERSION[tool_version]
    tool_collection = ToolCollection(*(ToolCls() for ToolCls in tool_group.tools))
    system = BetaTextBlockParam(
        type="text",
        text=f"{SYSTEM_PROMPT}{' ' + system_prompt_suffix if system_prompt_suffix else ''}",
    )

    # If using Anthropic with thinking enabled, inject prompt caching.
    if provider == APIProvider.ANTHROPIC and thinking_budget:
        _inject_prompt_caching(messages)
        only_n_most_recent_images = 0
        system["cache_control"] = {"type": "ephemeral"}  # type: ignore

    if only_n_most_recent_images:
        _maybe_filter_to_n_most_recent_images(
            messages,
            only_n_most_recent_images,
            min_removal_threshold=only_n_most_recent_images,
        )

    extra_body = {}
    if thinking_budget:
        extra_body = {"thinking": {"type": "enabled", "budget_tokens": thinking_budget}}

    # Set extra_headers to enable computer use beta.
    extra_headers = {}
    if provider == APIProvider.ANTHROPIC:
        if "20250124" in str(tool_version):
            extra_headers["anthropic-beta"] = "computer-use-2025-01-24"
        else:
            extra_headers["anthropic-beta"] = "computer-use-2024-10-22"

    # Instantiate the modern asynchronous client.
    if provider == APIProvider.ANTHROPIC:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=api_key, max_retries=4)
    elif provider == APIProvider.VERTEX:
        from anthropic import AsyncAnthropicVertex
        client = AsyncAnthropicVertex()
    elif provider == APIProvider.BEDROCK:
        from anthropic import AsyncAnthropicBedrock
        client = AsyncAnthropicBedrock()
    else:
        raise ValueError(f"Unknown provider: {provider}")

    try:
        async with client.messages.with_streaming_response.create(
            max_tokens=max_tokens,
            messages=messages,
            model=model,
            system=[system],
            tools=tool_collection.to_params(),
            extra_body=extra_body,
            extra_headers=extra_headers,
        ) as stream:
            assistant_blocks = []
            # Use iter_text() to iterate over incremental text chunks.
            async for text in stream.iter_text():
                block: BetaContentBlockParam = {"type": "text", "text": text}
                output_callback(block)
                assistant_blocks.append(block)
            # Obtain the final complete message.
            final_message: BetaMessage = await stream.get_final_message()
    except Exception as e:
        api_response_callback(None, None, e)
        return messages

    api_response_callback(None, None, None)

    final_blocks = _response_to_params(final_message)
    for block in final_blocks:
        if block.get("type") == "tool_use":
            result = await tool_collection.run(
                name=block["name"],
                tool_input=cast(dict[str, Any], block["input"]),
            )
            tool_result = _make_api_tool_result(result, block["id"])
            tool_output_callback(result, block["id"])
    messages.append({"role": "assistant", "content": final_blocks})
    return messages


def _maybe_filter_to_n_most_recent_images(
    messages: list[BetaMessageParam], images_to_keep: int, min_removal_threshold: int
):
    """
    Remove older screenshot images from tool result blocks while preserving enough content
    to not break the prompt cache.
    """
    if images_to_keep is None:
        return messages

    tool_result_blocks = [
        item
        for message in messages
        for item in (message["content"] if isinstance(message["content"], list) else [])
        if isinstance(item, dict) and item.get("type") == "tool_result"
    ]
    total_images = sum(
        1
        for tool_result in tool_result_blocks
        for content in tool_result.get("content", [])
        if isinstance(content, dict) and content.get("type") == "image"
    )
    images_to_remove = total_images - images_to_keep
    images_to_remove -= images_to_remove % min_removal_threshold

    for tool_result in tool_result_blocks:
        if isinstance(tool_result.get("content"), list):
            new_content = []
            for content in tool_result.get("content", []):
                if isinstance(content, dict) and content.get("type") == "image":
                    if images_to_remove > 0:
                        images_to_remove -= 1
                        continue
                new_content.append(content)
            tool_result["content"] = new_content


def _response_to_params(response: BetaMessage) -> list[BetaContentBlockParam]:
    res: list[BetaContentBlockParam] = []
    for block in response.content:
        if isinstance(block, BetaTextBlock):
            if block.text:
                res.append(BetaTextBlockParam(type="text", text=block.text))
            elif getattr(block, "type", None) == "thinking":
                thinking_block = {"type": "thinking", "thinking": getattr(block, "thinking", None)}
                if hasattr(block, "signature"):
                    thinking_block["signature"] = getattr(block, "signature", None)
                res.append(cast(BetaContentBlockParam, thinking_block))
        else:
            res.append(cast(BetaToolUseBlockParam, block.model_dump()))
    return res


def _inject_prompt_caching(messages: list[BetaMessageParam]):
    """
    Set cache breakpoints for the three most recent turns.
    """
    breakpoints_remaining = 3
    for message in reversed(messages):
        if message["role"] == "user" and isinstance(message["content"], list):
            if breakpoints_remaining:
                breakpoints_remaining -= 1
                message["content"][-1]["cache_control"] = BetaCacheControlEphemeralParam({"type": "ephemeral"})  # type: ignore
            else:
                message["content"][-1].pop("cache_control", None)
                break


def _make_api_tool_result(result: ToolResult, tool_use_id: str) -> BetaToolResultBlockParam:
    """Convert an agent ToolResult to an API ToolResultBlockParam."""
    tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
    is_error = False
    if result.error:
        is_error = True
        tool_result_content = _maybe_prepend_system_tool_result(result, result.error)
    else:
        if result.output:
            tool_result_content.append(
                {"type": "text", "text": _maybe_prepend_system_tool_result(result, result.output)}
            )
        if result.base64_image:
            tool_result_content.append(
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": result.base64_image}}
            )
    return {
        "type": "tool_result",
        "content": tool_result_content,
        "tool_use_id": tool_use_id,
        "is_error": is_error,
    }


def _maybe_prepend_system_tool_result(result: ToolResult, result_text: str):
    if result.system:
        result_text = f"<system>{result.system}</system>\n{result_text}"
    return result_text
