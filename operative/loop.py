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

PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"


class APIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


# Base system prompt
SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are using an Ubuntu virtual machine on {platform.machine()} architecture with internet access.
* You can install Ubuntu applications using your bash tool. Use curl, not wget.
* To open Firefox, click its icon (firefox-esr is installed).
* If you run GUI apps via the bash tool, set DISPLAY=:1, e.g. "(DISPLAY=:1 xterm &)".
* For large outputs, redirect to a file or grep to manage tokens.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>

<IMPORTANT>
* Ignore any Firefox startup wizards and just click the address bar to enter a URL.
* For PDFs, if you want the entire text, download with curl and use pdftotext.
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
    Agentic sampling loop that calls the Anthropic API to handle conversation & tool usage.
    Uses the modern async streaming interface with the beta computer use feature.
    """
    # Prepare the tool collection from the user-specified tool version.
    tool_group = TOOL_GROUPS_BY_VERSION[tool_version]
    tool_collection = ToolCollection(*(ToolCls() for ToolCls in tool_group.tools))

    # Construct the system prompt with optional user suffix.
    system = BetaTextBlockParam(
        type="text",
        text=f"{SYSTEM_PROMPT}{' ' + system_prompt_suffix if system_prompt_suffix else ''}",
    )

    # If thinking is enabled, inject prompt caching and do not truncate images.
    if provider == APIProvider.ANTHROPIC and thinking_budget:
        _inject_prompt_caching(messages)
        only_n_most_recent_images = 0
        system["cache_control"] = {"type": "ephemeral"}  # type: ignore

    # Possibly filter out older images to save tokens.
    if only_n_most_recent_images:
        _maybe_filter_to_n_most_recent_images(
            messages, only_n_most_recent_images, min_removal_threshold=only_n_most_recent_images
        )

    # Add the "thinking" param if thinking_budget is set.
    extra_body = {}
    if thinking_budget:
        extra_body = {"thinking": {"type": "enabled", "budget_tokens": thinking_budget}}

    # For beta computer use, set an extra header (anthropic-beta).
    extra_headers = {}
    if provider == APIProvider.ANTHROPIC:
        # If the tool version string includes "20250124", assume the new version
        if "20250124" in str(tool_version):
            extra_headers["anthropic-beta"] = "computer-use-2025-01-24"
        else:
            extra_headers["anthropic-beta"] = "computer-use-2024-10-22"

        # If we want to also test token-efficient-tools, set that here
        if token_efficient_tools_beta:
            # This can be combined with the existing anthropic-beta header if needed
            # For now, just note that you'd set a different header or param.
            pass

    # Instantiate the modern async client for the chosen provider.
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

    # Create the streaming request.
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
            # We'll accumulate incremental text in final_text.
            assistant_blocks = []
            final_text = ""

            # Iterate over text chunks from the stream.
            async for text_chunk in stream.iter_text():
                final_text += text_chunk
                block: BetaContentBlockParam = {"type": "text", "text": text_chunk}
                output_callback(block)
                assistant_blocks.append(block)

            # After streaming completes, parse the final message from the stream.
            # The modern SDK's recommended approach is parse() or partial parse,
            # but if it's unavailable, we build a minimal final BetaMessage manually.
            final_message = await stream.parse()

    except (APIStatusError, APIResponseValidationError) as e:
        # Return partial or handle error
        api_response_callback(e.request, e.response, e)
        return messages
    except APIError as e:
        api_response_callback(e.request, e.body, e)
        return messages
    except Exception as e:
        # Any other error
        api_response_callback(None, None, e)
        return messages

    # Indicate we have no raw request/response to pass
    api_response_callback(None, None, None)

    # Convert final message to content blocks
    response_params = _response_to_params(final_message)
    messages.append({"role": "assistant", "content": response_params})

    # Check for any tool use blocks. We'll run them if present and store the results.
    tool_result_content: list[BetaToolResultBlockParam] = []
    for content_block in response_params:
        output_callback(content_block)
        if content_block["type"] == "tool_use":
            result = await tool_collection.run(
                name=content_block["name"],
                tool_input=cast(dict[str, Any], content_block["input"]),
            )
            tool_result_block = _make_api_tool_result(result, content_block["id"])
            tool_result_content.append(tool_result_block)
            # Provide the result to the user as well.
            tool_output_callback(result, content_block["id"])

    # If no tool calls were made, we are done.
    if not tool_result_content:
        return messages

    # Otherwise, we add the tool results as user content to continue the loop.
    messages.append({"role": "user", "content": tool_result_content})
    return messages


def _maybe_filter_to_n_most_recent_images(
    messages: list[BetaMessageParam],
    images_to_keep: int,
    min_removal_threshold: int,
):
    """
    Remove older screenshot images from the conversation to save tokens.
    We remove them in blocks of `min_removal_threshold` to avoid prompt cache disruption.
    """
    if images_to_keep is None:
        return messages

    tool_result_blocks = cast(
        list[BetaToolResultBlockParam],
        [
            item
            for msg in messages
            for item in (msg["content"] if isinstance(msg["content"], list) else [])
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ],
    )

    total_images = sum(
        1
        for tool_result in tool_result_blocks
        for c in tool_result.get("content", [])
        if isinstance(c, dict) and c.get("type") == "image"
    )

    images_to_remove = total_images - images_to_keep
    images_to_remove -= images_to_remove % min_removal_threshold

    for tool_result in tool_result_blocks:
        content_list = tool_result.get("content", [])
        if isinstance(content_list, list):
            new_list = []
            for block in content_list:
                if isinstance(block, dict) and block.get("type") == "image":
                    if images_to_remove > 0:
                        images_to_remove -= 1
                        continue
                new_list.append(block)
            tool_result["content"] = new_list


def _response_to_params(response: BetaMessage) -> list[BetaContentBlockParam]:
    """
    Convert BetaMessage content blocks to BetaContentBlockParam for the final
    user-facing messages list.
    """
    result: list[BetaContentBlockParam] = []
    for block in response.content:
        if isinstance(block, BetaTextBlock):
            if block.text:
                result.append(BetaTextBlockParam(type="text", text=block.text))
            elif getattr(block, "type", None) == "thinking":
                # If we have a thinking block, capture it.
                thinking = {
                    "type": "thinking",
                    "thinking": getattr(block, "thinking", None),
                }
                if hasattr(block, "signature"):
                    thinking["signature"] = getattr(block, "signature", None)
                result.append(cast(BetaContentBlockParam, thinking))
        else:
            # For tool_use blocks, convert via model_dump()
            result.append(cast(BetaToolUseBlockParam, block.model_dump()))
    return result


def _inject_prompt_caching(messages: list[BetaMessageParam]):
    """
    If we have thinking enabled, we inject ephemeral cache control for the
    last 3 user turns to reduce cost. Adjust if needed.
    """
    breakpoints_remaining = 3
    for msg in reversed(messages):
        if msg["role"] == "user" and isinstance(msg["content"], list):
            if breakpoints_remaining:
                breakpoints_remaining -= 1
                # Mark the last block ephemeral
                msg["content"][-1]["cache_control"] = BetaCacheControlEphemeralParam({"type": "ephemeral"})  # type: ignore
            else:
                msg["content"][-1].pop("cache_control", None)
                break


def _make_api_tool_result(result: ToolResult, tool_use_id: str) -> BetaToolResultBlockParam:
    """
    Convert the result from a local tool run into a BetaToolResultBlockParam for
    appending to the conversation.
    """
    tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
    is_error = False
    if result.error:
        is_error = True
        tool_result_content = _maybe_prepend_system_tool_result(result, result.error)
    else:
        if result.output:
            tool_result_content.append({
                "type": "text",
                "text": _maybe_prepend_system_tool_result(result, result.output)
            })
        if result.base64_image:
            tool_result_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": result.base64_image
                }
            })
    return {
        "type": "tool_result",
        "content": tool_result_content,
        "tool_use_id": tool_use_id,
        "is_error": is_error,
    }


def _maybe_prepend_system_tool_result(result: ToolResult, text: str) -> str:
    """
    If the tool result included some system context, prepend it to the text.
    """
    if result.system:
        return f"<system>{result.system}</system>\n{text}"
    return text
