"""
Agentic sampling loop that calls the Anthropic API using the modern AsyncAnthropic client
and its streaming interface for beta computer use.
"""

from collections.abc import Callable
from enum import StrEnum
from typing import Any, cast

import httpx
from anthropic import (
    APIError,
    APIResponseValidationError,
    APIStatusError,
    AsyncAnthropic,
    AsyncAnthropicBedrock,
    AsyncAnthropicVertex,
)
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

from .prompt import SYSTEM_PROMPT
from .tools import (
    TOOL_GROUPS_BY_VERSION,
    ToolCollection,
    ToolResult,
    ToolVersion,
)

PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"
OUTPUT_128K_BETA_FLAG = "output-128k-2025-02-19"


class APIProvider(StrEnum):
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    VERTEX = "vertex"


async def sampling_loop(
    *,
    model: str,
    provider: APIProvider,
    system_prompt_suffix: str,
    messages: list[dict],
    output_callback: Callable[[BetaContentBlockParam], None],
    tool_output_callback: Callable[[ToolResult, str], None],
    api_response_callback: Callable[[httpx.Request | None, httpx.Response | object | None, Exception | None], None],
    api_key: str,
    only_n_most_recent_images: int | None = None,
    max_tokens: int = 4096,
    tool_version: ToolVersion,
    thinking_budget: int | None = None,
    token_efficient_tools_beta: bool = False,

) -> list[dict]:
    """Agentic sampling loop for assistant/tool interaction of computer use."""

    def setup_tool_collection():
        """Create and return tool collection for specified version."""
        tool_group = TOOL_GROUPS_BY_VERSION[tool_version]
        return ToolCollection(*(cls() for cls in tool_group.tools))

    def create_system_prompt():
        """Create the system prompt with optional suffix."""
        return BetaTextBlockParam(
            type="text",
            text=f"{SYSTEM_PROMPT}{' ' + system_prompt_suffix if system_prompt_suffix else ''}"
        )

    def get_api_client():
        """Get API client based on provider."""
        if provider == APIProvider.ANTHROPIC:
            return AsyncAnthropic(api_key=api_key, max_retries=4)
        elif provider == APIProvider.VERTEX:
            return AsyncAnthropicVertex()
        else:  # BEDROCK
            return AsyncAnthropicBedrock()

    def get_beta_flags():
        """Determine which beta flags to enable."""
        tool_group = TOOL_GROUPS_BY_VERSION[tool_version]
        betas = []
        if tool_group.beta_flag:
            betas.append(tool_group.beta_flag)
        if token_efficient_tools_beta:
            betas.append("token-efficient-tools-2025-02-19")
        betas.append(OUTPUT_128K_BETA_FLAG)
        return betas

    def configure_prompt_caching(system, betas):
        """Configure prompt caching if using Anthropic API."""
        if provider == APIProvider.ANTHROPIC:
            betas.append(PROMPT_CACHING_BETA_FLAG)
            _inject_prompt_caching(messages)
            system["cache_control"] = {"type": "ephemeral"}  # type: ignore
        return system

    def prepare_api_parameters(system, tool_collection, betas):
        """Prepare API call parameters."""
        params = {
            "max_tokens": max_tokens,
            "messages": messages,
            "model": model,
            "system": [system],
            "tools": tool_collection.to_params(),
            "betas": betas,
        }
        if thinking_budget:
            params["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
        return params

    def process_content_block_start(event):
        """Process content block start events."""
        if (hasattr(event, "content_block") and event.content_block.type == "tool_use" and hasattr(event.content_block, "input")):
            output_callback({
                "type": "tool_use",
                "name": getattr(event.content_block, "name", "Unknown Tool"),
                "input": event.content_block.input or {}
            })

    def process_content_block_delta(event):
        """Process content block delta events."""
        if hasattr(event, "delta") and event.delta:
            # For text deltas, extract just the text content
            if hasattr(event.delta, "type") and event.delta.type == "text_delta":
                output_callback({"type": "text", "text": event.delta.text})
            # For other delta types, pass through but format better
            else:
                output_callback({"type": "delta", "content": str(event.delta)})

    def process_tool_progress(event):
        """Process tool progress events."""
        if hasattr(event, "progress"):
            output_callback({"type": "progress", "progress": event.progress})

    def handle_stream_event(event):
        """Process streaming events and filter for meaningful content only."""
        # Skip events that shouldn't be displayed
        if event.type in ("message_start", "message_stop", "signature_delta", "input_json_delta"):
            return

        # For thinking events, only send if content exists
        if event.type == "thinking" and hasattr(event, "thinking") and event.thinking:
            output_callback({"type": "thinking", "thinking": event.thinking})

        # For thinking delta events, extract actual content
        elif event.type == "thinking_delta" and hasattr(event, "thinking_delta"):
            delta = event.thinking_delta
            thinking = getattr(delta, "thinking", None)
            if thinking:
                output_callback({"type": "thinking", "thinking": thinking})

        # For text events, send only if text exists
        elif event.type == "text" and hasattr(event, "text") and event.text:
            output_callback({"type": "text", "text": event.text})

        # For tool use events, ensure all properties exist
        elif event.type == "content_block_start" and hasattr(event, "content_block"):
            content_block = event.content_block
            if (getattr(content_block, "type", None) == "tool_use" and
                    hasattr(content_block, "input") and
                    hasattr(content_block, "name")):
                output_callback({
                    "type": "tool_use",
                    "name": content_block.name,
                    "input": content_block.input or {}
                })

        # For delta events, only handle text deltas with content
        elif event.type == "content_block_delta" and hasattr(event, "delta"):
            delta = event.delta
            if (getattr(delta, "type", None) == "text_delta" and
                    hasattr(delta, "text") and delta.text):
                output_callback({"type": "text", "text": delta.text})

        # For tool progress, send only if progress exists
        elif event.type == "tool_use_progress" and hasattr(event, "progress"):
            output_callback({"type": "progress", "progress": str(event.progress)})

    async def stream_response(client, params):
        """Stream the response and track the full message."""
        full_response = None
        async with client.beta.messages.stream(**params) as stream:
            async for event in stream:
                handle_stream_event(event)
                if event.type == "message_start":
                    full_response = event.message
                elif event.type == "message_stop" and hasattr(event, "message"):
                    full_response = event.message
        return full_response

    async def execute_tool(content_block):
        """Execute a tool and process its result."""
        if content_block["type"] != "tool_use":
            return None
        try:
            result = await tool_collection.run(
                name=content_block["name"],
                tool_input=cast(dict[str, Any], content_block["input"]),
            )
            tool_output_callback(result, content_block["id"])
            return _make_api_tool_result(result, content_block["id"])
        except Exception as e:
            error_result = ToolResult(
                error=f"Tool execution error: {str(e)}",
                output=None,
                base64_image=None,
                system="Error occurred during tool execution"
            )
            tool_output_callback(error_result, content_block["id"])
            return _make_api_tool_result(error_result, content_block["id"])

    async def process_tools(response_params):
        """Process all tool calls in the response."""
        tool_results = []
        for block in response_params:
            tool_result = await execute_tool(block)
            if tool_result:
                tool_results.append(tool_result)
        return tool_results

    def handle_error(error):
        """Handle API errors with appropriate callback."""
        if isinstance(error, APIStatusError | APIResponseValidationError):
            api_response_callback(error.request, error.response, error)
        elif isinstance(error, APIError):
            api_response_callback(error.request, error.body, error)
        else:
            api_response_callback(None, None, error)

    # Main loop
    while True:
        tool_collection = setup_tool_collection()
        system = create_system_prompt()
        client = get_api_client()
        betas = get_beta_flags()
        system = configure_prompt_caching(system, betas)

        image_limit = 0 if provider == APIProvider.ANTHROPIC else only_n_most_recent_images
        if image_limit:
            _maybe_filter_to_n_most_recent_images(
                messages, image_limit, min_removal_threshold=image_limit
            )

        api_params = prepare_api_parameters(system, tool_collection, betas)

        try:
            full_response = await stream_response(client, api_params)
            response_params = _response_to_params(full_response)
            messages.append({"role": "assistant", "content": response_params})

            tool_results = await process_tools(response_params)
            if not tool_results:
                return messages

            messages.append({"content": tool_results, "role": "user"})
        except Exception as e:
            handle_error(e)
            return messages


def _maybe_filter_to_n_most_recent_images(
    messages: list[BetaMessageParam],
    images_to_keep: int,
    min_removal_threshold: int,
):
    """
    With the assumption that images are screenshots that are of diminishing value as
    the conversation progresses, remove all but the final `images_to_keep` tool_result
    images in place, with a chunk of min_removal_threshold to reduce the amount we
    break the implicit prompt cache.
    """
    if images_to_keep is None:
        return messages

    tool_result_blocks = cast(
        list[BetaToolResultBlockParam],
        [
            item
            for message in messages
            for item in (
                message["content"] if isinstance(message["content"], list) else []
            )
            if isinstance(item, dict) and item.get("type") == "tool_result"
        ],
    )

    total_images = sum(
        1
        for tool_result in tool_result_blocks
        for content in tool_result.get("content", [])
        if isinstance(content, dict) and content.get("type") == "image"
    )

    images_to_remove = total_images - images_to_keep
    # for better cache behavior, we want to remove in chunks
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


def _response_to_params(
    response: BetaMessage,
) -> list[BetaContentBlockParam]:
    res: list[BetaContentBlockParam] = []
    for block in response.content:
        if isinstance(block, BetaTextBlock):
            if block.text:
                res.append(BetaTextBlockParam(type="text", text=block.text))
            elif getattr(block, "type", None) == "thinking":
                # Handle thinking blocks - include signature field
                thinking_block = {
                    "type": "thinking",
                    "thinking": getattr(block, "thinking", None),
                }
                if hasattr(block, "signature"):
                    thinking_block["signature"] = getattr(block, "signature", None)
                res.append(cast(BetaContentBlockParam, thinking_block))
        else:
            # Handle tool use blocks normally
            res.append(cast(BetaToolUseBlockParam, block.model_dump()))
    return res


def _inject_prompt_caching(
    messages: list[BetaMessageParam],
):
    """
    Set cache breakpoints for the 3 most recent turns
    one cache breakpoint is left for tools/system prompt, to be shared across sessions
    """

    breakpoints_remaining = 3
    for message in reversed(messages):
        if message["role"] == "user" and isinstance(
            content := message["content"], list
        ):
            if breakpoints_remaining:
                breakpoints_remaining -= 1
                # Use type ignore to bypass TypedDict check until SDK types are updated
                content[-1]["cache_control"] = BetaCacheControlEphemeralParam(  # type: ignore
                    {"type": "ephemeral"}
                )
            else:
                content[-1].pop("cache_control", None)
                # we'll only every have one extra turn per loop
                break


def _make_api_tool_result(
    result: ToolResult, tool_use_id: str
) -> BetaToolResultBlockParam:
    """Convert an agent ToolResult to an API ToolResultBlockParam."""
    tool_result_content: list[BetaTextBlockParam | BetaImageBlockParam] | str = []
    is_error = False
    if result.error:
        is_error = True
        tool_result_content = _maybe_prepend_system_tool_result(result, result.error)
    else:
        if result.output:
            tool_result_content.append(
                {
                    "type": "text",
                    "text": _maybe_prepend_system_tool_result(result, result.output),
                }
            )
        if result.base64_image:
            tool_result_content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": result.base64_image,
                    },
                }
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
