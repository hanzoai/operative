"""
Entrypoint for Streamlit using the modern AsyncAnthropic client.
"""

import asyncio
import base64
import os
import subprocess
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from functools import partial
from pathlib import PosixPath
from typing import cast, get_args

import streamlit as st
import httpx
from anthropic import RateLimitError
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
)
from streamlit.delta_generator import DeltaGenerator

from operative.loop import APIProvider, sampling_loop
from operative.tools import ToolResult, ToolVersion

PROVIDER_TO_DEFAULT_MODEL_NAME: dict[APIProvider, str] = {
    APIProvider.ANTHROPIC: "claude-3-7-sonnet-20250219",
    APIProvider.BEDROCK: "anthropic.claude-3-5-sonnet-20241022-v2:0",
    APIProvider.VERTEX: "claude-3-5-sonnet-v2@20241022",
}


@dataclass(kw_only=True, frozen=True)
class ModelConfig:
    tool_version: ToolVersion
    max_output_tokens: int
    default_output_tokens: int
    has_thinking: bool = False


SONNET_3_5_NEW = ModelConfig(
    tool_version="computer_use_20241022",
    max_output_tokens=1024 * 8,
    default_output_tokens=1024 * 4,
)
SONNET_3_7 = ModelConfig(
    tool_version="computer_use_20250124",
    max_output_tokens=128_000,
    default_output_tokens=1024 * 16,
    has_thinking=True,
)
MODEL_TO_MODEL_CONF: dict[str, ModelConfig] = {
    "claude-3-7-sonnet-20250219": SONNET_3_7,
}

CONFIG_DIR = PosixPath("~/.anthropic").expanduser()
API_KEY_FILE = CONFIG_DIR / "api_key"
STREAMLIT_STYLE = """
<style>
    button[kind=header] {
        background-color: rgb(255, 75, 75);
        border: 1px solid rgb(255, 75, 75);
        color: rgb(255, 255, 255);
    }
    button[kind=header]:hover {
        background-color: rgb(255, 51, 51);
    }
    .stAppDeployButton {
        visibility: hidden;
    }
</style>
"""

WARNING_TEXT = "⚠️ Security Alert: Never provide access to sensitive accounts or data."
INTERRUPT_TEXT = "(user stopped or interrupted and wrote the following)"
INTERRUPT_TOOL_ERROR = "human stopped or interrupted tool execution"


class Sender(StrEnum):
    USER = "user"
    BOT = "assistant"
    TOOL = "tool"


def setup_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "api_key" not in st.session_state:
        st.session_state.api_key = load_from_storage("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
    if "provider" not in st.session_state:
        st.session_state.provider = os.getenv("API_PROVIDER", "anthropic") or APIProvider.ANTHROPIC
    if "provider_radio" not in st.session_state:
        st.session_state.provider_radio = st.session_state.provider
    if "model" not in st.session_state:
        _reset_model()
    if "auth_validated" not in st.session_state:
        st.session_state.auth_validated = False
    if "responses" not in st.session_state:
        st.session_state.responses = {}
    if "tools" not in st.session_state:
        st.session_state.tools = {}
    if "only_n_most_recent_images" not in st.session_state:
        st.session_state.only_n_most_recent_images = 3
    if "custom_system_prompt" not in st.session_state:
        st.session_state.custom_system_prompt = load_from_storage("system_prompt") or ""
    if "hide_images" not in st.session_state:
        st.session_state.hide_images = False
    if "token_efficient_tools_beta" not in st.session_state:
        st.session_state.token_efficient_tools_beta = False
    if "in_sampling_loop" not in st.session_state:
        st.session_state.in_sampling_loop = False
    if "streaming_thoughts" not in st.session_state:
        st.session_state.streaming_thoughts = ""


def _reset_model():
    st.session_state.model = PROVIDER_TO_DEFAULT_MODEL_NAME[cast(APIProvider, st.session_state.provider)]
    _reset_model_conf()


def _reset_model_conf():
    model_conf = SONNET_3_7 if "3-7" in st.session_state.model else MODEL_TO_MODEL_CONF.get(st.session_state.model, SONNET_3_5_NEW)
    st.session_state.tool_version = model_conf.tool_version
    st.session_state.has_thinking = model_conf.has_thinking
    st.session_state.output_tokens = model_conf.default_output_tokens
    st.session_state.max_output_tokens = model_conf.max_output_tokens
    st.session_state.thinking_budget = int(model_conf.default_output_tokens / 2)


async def main():
    """Main render loop for Streamlit."""
    setup_state()
    st.markdown(STREAMLIT_STYLE, unsafe_allow_html=True)
    st.title("Hanzo Operative")
    #if os.getenv("SHOW_WARNING", True):
    #    st.warning(WARNING_TEXT)

    with st.sidebar:
        def _reset_api_provider():
            if st.session_state.provider_radio != st.session_state.provider:
                _reset_model()
                st.session_state.provider = st.session_state.provider_radio
                st.session_state.auth_validated = False

        provider_options = [option.value for option in APIProvider]
        st.radio("API Provider", options=provider_options, key="provider_radio", format_func=lambda x: x.title(), on_change=_reset_api_provider)
        st.text_input("Model", key="model", on_change=_reset_model_conf)
        if st.session_state.provider == APIProvider.ANTHROPIC:
            st.text_input("Anthropic API Key", type="password", key="api_key", on_change=lambda: save_to_storage("api_key", st.session_state.api_key))
        st.number_input("Only send N most recent images", min_value=0, key="only_n_most_recent_images",
                        help="Remove older screenshots to decrease token usage")
        st.text_area("Custom System Prompt Suffix", key="custom_system_prompt",
                     help="Additional instructions to append to the system prompt.",
                     on_change=lambda: save_to_storage("system_prompt", st.session_state.custom_system_prompt))
        st.checkbox("Hide screenshots", key="hide_images")
        st.checkbox("Enable token-efficient tools beta", key="token_efficient_tools_beta")
        versions = get_args(ToolVersion)
        st.radio("Tool Versions", key="tool_versions", options=versions, index=versions.index(st.session_state.tool_version))
        st.number_input("Max Output Tokens", key="output_tokens", step=1)
        # Allow the user to enable thinking and set a thinking budget.
        st.checkbox("Thinking Enabled", key="thinking", value=False)
        st.number_input(
            "Thinking Budget",
            key="thinking_budget",
            max_value=st.session_state.max_output_tokens,
            step=1,
            disabled=not st.session_state.thinking
        )
        if st.button("Reset", type="primary"):
            with st.spinner("Resetting..."):
                st.session_state.clear()
                setup_state()
                subprocess.run("pkill Xvfb; pkill tint2", shell=True)
                await asyncio.sleep(1)
                subprocess.run("./start_all.sh", shell=True)

    if not st.session_state.auth_validated:
        if auth_error := validate_auth(st.session_state.provider, st.session_state.api_key):
            st.warning(f"Please resolve the following auth issue:\n\n{auth_error}")
            return
        else:
            st.session_state.auth_validated = True

    # Create three tabs: Chat, HTTP Exchange Logs, and Streaming Thoughts.
    chat_tab, http_logs_tab, streaming_tab = st.tabs(["Chat", "HTTP Logs", "Thinking Logs"])

    with chat_tab:
        for message in st.session_state.messages:
            if isinstance(message["content"], str):
                _render_message(message["role"], message["content"])
            elif isinstance(message["content"], list):
                for block in message["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        _render_message(Sender.TOOL, st.session_state.tools[block["tool_use_id"]])
                    else:
                        _render_message(message["role"], cast(BetaContentBlockParam | ToolResult, block))
        new_message = st.chat_input("Type a message to send to Operator to control the computer...")
        if new_message:
            st.session_state.messages.append({
                "role": Sender.USER,
                "content": [*maybe_add_interruption_blocks(), BetaTextBlockParam(type="text", text=new_message)],
            })
            _render_message(Sender.USER, new_message)

    with http_logs_tab:
        for identity, (request, response) in st.session_state.responses.items():
            _render_api_response(request, response, identity, http_logs_tab)

    with streaming_tab:
        streaming_placeholder = st.empty()
        if st.button("Clear Streaming Thoughts", key="clear_streaming"):
            st.session_state.streaming_thoughts = ""
            streaming_placeholder.empty()
        streaming_placeholder.markdown(f"**[Streaming Thoughts]**\n{st.session_state.streaming_thoughts}")

    try:
        most_recent_message = st.session_state["messages"][-1]
    except IndexError:
        return
    if most_recent_message["role"] is not Sender.USER:
        return

    def bot_output_callback(message: BetaContentBlockParam):
        if isinstance(message, dict) and message.get("type") == "thinking":
            current = st.session_state.streaming_thoughts
            st.session_state.streaming_thoughts = current + message.get("thinking", "") + "\n"
            streaming_placeholder.markdown(f"**[Streaming Thoughts]**\n{st.session_state.streaming_thoughts}")
        else:
            _render_message(Sender.BOT, message)

    with track_sampling_loop():
        st.session_state.messages = await sampling_loop(
            system_prompt_suffix=st.session_state.custom_system_prompt,
            model=st.session_state.model,
            provider=st.session_state.provider,
            messages=st.session_state.messages,
            output_callback=bot_output_callback,
            tool_output_callback=partial(_tool_output_callback, tool_state=st.session_state.tools),
            api_response_callback=partial(_api_response_callback, tab=http_logs_tab, response_state=st.session_state.responses),
            api_key=st.session_state.api_key,
            only_n_most_recent_images=st.session_state.only_n_most_recent_images,
            tool_version=st.session_state.tool_version,
            max_tokens=st.session_state.output_tokens,
            thinking_budget=st.session_state.thinking_budget if st.session_state.thinking else None,
            token_efficient_tools_beta=st.session_state.token_efficient_tools_beta,
        )


def maybe_add_interruption_blocks():
    if not st.session_state.in_sampling_loop:
        return []
    result = []
    last_message = st.session_state.messages[-1]
    previous_tool_use_ids = [block["id"] for block in last_message["content"] if block.get("type") == "tool_use"]
    for tool_use_id in previous_tool_use_ids:
        st.session_state.tools[tool_use_id] = ToolResult(error=INTERRUPT_TOOL_ERROR)
        result.append(BetaToolResultBlockParam(
            tool_use_id=tool_use_id,
            type="tool_result",
            content=INTERRUPT_TOOL_ERROR,
            is_error=True,
        ))
    result.append(BetaTextBlockParam(type="text", text=INTERRUPT_TEXT))
    return result


@contextmanager
def track_sampling_loop():
    st.session_state.in_sampling_loop = True
    yield
    st.session_state.in_sampling_loop = False


def validate_auth(provider: APIProvider, api_key: str | None):
    if provider == APIProvider.ANTHROPIC:
        if not api_key:
            return "Enter your Anthropic API key in the sidebar to continue."
    if provider == APIProvider.BEDROCK:
        import boto3
        if not boto3.Session().get_credentials():
            return "You must have AWS credentials set up to use the Bedrock API."
    if provider == APIProvider.VERTEX:
        import google.auth
        from google.auth.exceptions import DefaultCredentialsError
        if not os.environ.get("CLOUD_ML_REGION"):
            return "Set the CLOUD_ML_REGION environment variable to use the Vertex API."
        try:
            google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        except DefaultCredentialsError:
            return "Your google cloud credentials are not set up correctly."


def load_from_storage(filename: str) -> str | None:
    try:
        file_path = CONFIG_DIR / filename
        if file_path.exists():
            data = file_path.read_text().strip()
            if data:
                return data
    except Exception as e:
        st.write(f"Debug: Error loading {filename}: {e}")
    return None


def save_to_storage(filename: str, data: str) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        file_path = CONFIG_DIR / filename
        file_path.write_text(data)
        file_path.chmod(0o600)
    except Exception as e:
        st.write(f"Debug: Error saving {filename}: {e}")


def _api_response_callback(
    request: httpx.Request | None,
    response: httpx.Response | object | None,
    error: Exception | None,
    tab: DeltaGenerator,
    response_state: dict[str, tuple[httpx.Request, httpx.Response | object | None]],
):
    response_id = datetime.now().isoformat()
    response_state[response_id] = (request, response)
    if error:
        _render_error(error)
    _render_api_response(request, response, response_id, tab)


def _tool_output_callback(tool_output: ToolResult, tool_id: str, tool_state: dict[str, ToolResult]):
    tool_state[tool_id] = tool_output
    _render_message(Sender.TOOL, tool_output)


def _render_api_response(
    request: httpx.Request | None,
    response: httpx.Response | object | None,
    response_id: str,
    tab: DeltaGenerator,
):
    with tab:
        with st.expander(f"Request/Response ({response_id})"):
            newline = "\n\n"
            req_info = f"{request.method} {request.url}" if request else "N/A"
            headers = request.headers.items() if request else []
            st.markdown(f"`{req_info}`{newline}{newline.join(f'`{k}: {v}`' for k, v in headers)}")
            st.json(request.read().decode() if request else "No request data available")
            st.markdown("---")
            if isinstance(response, httpx.Response):
                st.markdown(f"`{response.status_code}`{newline}{newline.join(f'`{k}: {v}`' for k, v in response.headers.items())}")
                try:
                    st.json(response.text)
                except Exception:
                    st.write("Response content not available due to streaming.")
            else:
                st.write(response)


def _render_error(error: Exception):
    if isinstance(error, RateLimitError):
        body = "You have been rate limited."
        if retry_after := error.response.headers.get("retry-after"):
            body += f" **Retry after {str(timedelta(seconds=int(retry_after)))} (HH:MM:SS).**"
        body += f"\n\n{error.message}"
    else:
        body = str(error)
        body += "\n\n**Traceback:**"
        lines = "\n".join(traceback.format_exception(error))
        body += f"\n\n```{lines}```"
    save_to_storage(f"error_{datetime.now().timestamp()}.md", body)
    st.error(f"**{error.__class__.__name__}**\n\n{body}", icon=":material/error:")


def _render_message(sender: Sender, message: str | BetaContentBlockParam | ToolResult):
    """Convert input from the user or output from the agent to a Streamlit message."""
    is_tool_result = not isinstance(message, str | dict)
    if not message or (is_tool_result and st.session_state.hide_images and not hasattr(message, "error") and not hasattr(message, "output")):
        return
    with st.chat_message(sender):
        if is_tool_result:
            message = cast(ToolResult, message)
            if message.output:
                if message.__class__.__name__ == "CLIResult":
                    st.code(message.output)
                else:
                    st.markdown(message.output)
            if message.error:
                st.error(message.error)
            if message.base64_image and not st.session_state.hide_images:
                st.image(base64.b64decode(message.base64_image))
        elif isinstance(message, dict):
            if message["type"] == "text":
                st.write(message["text"])
            elif message["type"] == "thinking":
                st.markdown(f"[Thinking]\n\n{message.get('thinking', '')}")
            elif message["type"] == "tool_use":
                st.code(f'Tool Use: {message["name"]}\nInput: {message["input"]}')
            else:
                raise Exception(f'Unexpected response type {message["type"]}')
        else:
            st.markdown(message)


if __name__ == "__main__":
    asyncio.run(main())
