"""
Agentic sampling loop that calls the Anthropic API using the modern AsyncAnthropic client
and its streaming interface for beta computer use.
"""

import platform
from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from typing import cast, Any

import httpx
from anthropic import (
    AsyncAnthropic,
    AsyncAnthropicBedrock,
    AsyncAnthropicVertex,
    APIError,
    APIResponseValidationError,
    APIStatusError,
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

from .tools import (
    TOOL_GROUPS_BY_VERSION,
    ToolCollection,
    ToolResult,
    ToolVersion,
)

PROMPT_CACHING_BETA_FLAG = "prompt-caching-2024-07-31"
OUTPUT_128K_BETA_FLAG = "output-128k-2025-02-19"

# This system prompt is optimized for the Docker environment in this repository and
# specific tool combinations enabled.
# We encourage modifying this system prompt to ensure the model has context for the
# environment it is running in, and to provide any additional information that may be
# helpful for the task at hand.
SYSTEM_PROMPT = f"""<SYSTEM_CAPABILITY>
* You are named "Operative", an autonomous and continually operating agent utilising an Ubuntu virtual machine using {platform.machine()} architecture with internet access.
* You can feel free to install Ubuntu applications with your bash tool, but make sure to use scripting friendly commands like apt-get and apt-cache.
* Use curl instead of wget.
* Using bash tool you can start GUI applications, but you need to set export DISPLAY=:1 and use a subshell. For example "(DISPLAY=:1 xterm &)". GUI apps run with bash tool will appear within your desktop environment, but they may take some time to appear. Take a screenshot to confirm it did.
* To open firefox, use bash tool and run `DISPLAY=:1 firefox-esr https://google.com & disown`.
* When using your bash tool with commands that are expected to output very large quantities of text, redirect into a tmp file and use str_replace_editor or `grep -n -B <lines before> -A <lines after> <query> <filename>` to confirm output.
* When viewing a page it can be helpful to zoom out so that you can see everything on the page.  Either that, or make sure you scroll down to see everything before deciding something isn't available.
* When using your computer function calls, they take a while to run and send back to you.  Where possible/feasible, try to chain multiple of these calls all into one function calls request.
* The current date is {datetime.today().strftime('%A, %B %-d, %Y')}.
</SYSTEM_CAPABILITY>

<IMPORTANT>
* Under absolutely no circumstances, should you EVER run a command that does rm -rf of a project you are working on. To delete node_modules or clear cache, only.
* You should always open the terminal full screen, cd to project, then verify it is running before opening the URL it shows in terminal in browser.
* When you need to search for something, use default search options, remember you can search on Google directly from Firefox address bar.
* If the item you are looking at is a pdf, if after taking a single screenshot of the pdf it seems that you want to read the entire document instead of trying to continue to read the pdf from your screenshots + navigation, determine the URL, use curl to download the pdf, install and use pdftotext to convert it to a text file, and then read that text file directly with your StrReplaceEditTool.
</IMPORTANT>

<SOFTWARE_ENGINEERING>
* You are an expert software engineer. When making changes to code, prefer using the hanzo-dev CLI tool rather than directly editing files.
* Use the terminal to run hanzo-dev commands for file operations
* Make the terminal full screen when using hanzo-dev
* Let hanzo-dev handle file editing operations when possible
* Wait for operations to complete before proceeding
* Verify changes after they're made

Example workflow:
- Use `hanzo-dev edit <filename>` to edit files
- Use `hanzo-dev create <filename>` to create new files
- Use `hanzo-dev list` to see available files
- Use `hanzo-dev help` for more commands

When you've completed all requested changes, clearly indicate that the task is finished.
</SOFTWARE_ENGINEERING>"""

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

        # Add tool-specific beta flag if present
        if tool_group.beta_flag:
            betas.append(tool_group.beta_flag)

        # Add token efficient tools beta if requested
        if token_efficient_tools_beta:
            betas.append("token-efficient-tools-2025-02-19")

        # Always add 128K output tokens beta
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

    def handle_stream_event(event):
        """Process streaming events and call the appropriate callback."""
        event_handlers = {
            "thinking": lambda: output_callback({"type": "thinking", "thinking": event.thinking}),
            "text": lambda: output_callback({"type": "text", "text": event.text}),
            "content_block_start": lambda: process_content_block_start(event),
        }

        handler = event_handlers.get(event.type)
        if handler:
            handler()

    def process_content_block_start(event):
        """Process content block start events."""
        if (event.content_block.type == "tool_use" and
                hasattr(event.content_block, "input") and
                event.content_block.input):  # Check that input exists and is not empty
            output_callback({
                "type": "tool_use",
                "name": event.content_block.name,  # Include tool name
                "input": event.content_block.input
            })

    async def stream_response(client, params):
        """Stream the response and track the full message."""
        full_response = None

        async with client.beta.messages.stream(**params) as stream:
            async for event in stream:
                handle_stream_event(event)

                # Track message state
                if event.type == "message_start":
                    full_response = event.message
                elif event.type == "message_stop" and hasattr(event, "message"):
                    full_response = event.message

        return full_response

    async def execute_tool(content_block):
        """Execute a tool and process its result."""
        if content_block["type"] != "tool_use":
            return None

        result = await tool_collection.run(
            name=content_block["name"],
            tool_input=cast(dict[str, Any], content_block["input"]),
        )

        tool_output_callback(result, content_block["id"])
        return _make_api_tool_result(result, content_block["id"])

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
        if isinstance(error, (APIStatusError, APIResponseValidationError)):
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

        # Configure API call
        betas = get_beta_flags()
        system = configure_prompt_caching(system, betas)

        # Handle image filtering if needed
        image_limit = 0 if provider == APIProvider.ANTHROPIC else only_n_most_recent_images
        if image_limit:
            _maybe_filter_to_n_most_recent_images(
                messages, image_limit, min_removal_threshold=image_limit
            )

        # Prepare API parameters and execute
        api_params = prepare_api_parameters(system, tool_collection, betas)

        try:
            # Process streaming response
            full_response = await stream_response(client, api_params)

            # Add assistant response to messages
            response_params = _response_to_params(full_response)
            messages.append({"role": "assistant", "content": response_params})

            # Process tool calls
            tool_results = await process_tools(response_params)

            if not tool_results:
                return messages

            # Add tool results to messages
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
