"""
Custom LLM Client Adapter for Magentic-UI

This adapter converts between the standard OpenAI-compatible format 
and your custom LLM API format.

Your API format:
- Endpoint: POST http://localhost:8080/chat
- Request: form-data with 'message', 'model'
- Response: {"message": ..., "response": ..., "model": {...}}
"""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Mapping, Optional, Sequence, Union
import aiohttp
from dataclasses import dataclass

from autogen_core.models import (
    ChatCompletionClient,
    CreateResult,
    LLMMessage,
    ModelFamily,
    ModelInfo,
    RequestUsage,
    SystemMessage,
    UserMessage,
    AssistantMessage,
)
from autogen_core import CancellationToken
from autogen_core.tools import ToolSchema

logger = logging.getLogger(__name__)


@dataclass
class CustomLLMConfig:
    """Configuration for the Custom LLM Client"""
    base_url: str = "http://localhost:8080"
    api_key: str = "localApiToken"
    model: str = "copilot/gpt-4o"
    timeout: int = 120


class CustomLLMChatCompletionClient(ChatCompletionClient):
    """
    Custom Chat Completion Client that adapts your LLM API to AutoGen format.
    
    Your API:
    - POST /chat with form-data: message, model
    - Response: {"message": ..., "response": ..., "model": {...}}
    
    AutoGen expects:
    - messages: List of LLMMessage
    - Returns: CreateResult with content
    """
    
    component_type = "model"
    component_provider_override = "custom_llm_client.CustomLLMChatCompletionClient"
    
    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        api_key: str = "localApiToken",
        model: str = "copilot/gpt-4o",
        timeout: int = 120,
        **kwargs
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self._total_usage = RequestUsage(prompt_tokens=0, completion_tokens=0)
        
        # Model info - adjust based on your model's capabilities
        self._model_info = ModelInfo(
            vision=True,  # Set to False if model doesn't support images
            function_calling=True,  # Set to False if no function calling
            json_output=True,
            family=ModelFamily.UNKNOWN,
            structured_output=False,
            multiple_system_messages=False,
        )
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    def _messages_to_text(self, messages: Sequence[LLMMessage]) -> str:
        """Convert LLMMessage list to a single text string for your API"""
        parts = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                parts.append(f"[System]: {msg.content}")
            elif isinstance(msg, UserMessage):
                # Handle multimodal content
                if isinstance(msg.content, str):
                    parts.append(f"[User]: {msg.content}")
                elif isinstance(msg.content, list):
                    # Extract text from multimodal content
                    text_parts = []
                    for item in msg.content:
                        if isinstance(item, str):
                            text_parts.append(item)
                        elif hasattr(item, 'text'):
                            text_parts.append(item.text)
                    parts.append(f"[User]: {' '.join(text_parts)}")
            elif isinstance(msg, AssistantMessage):
                if isinstance(msg.content, str):
                    parts.append(f"[Assistant]: {msg.content}")
        
        return "\n\n".join(parts)
    
    async def create(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[ToolSchema] = [],
        json_output: Optional[bool] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[CancellationToken] = None,
    ) -> CreateResult:
        """
        Send messages to your custom LLM API and return the response.
        """
        session = await self._get_session()
        
        # Convert messages to single text
        message_text = self._messages_to_text(messages)
        
        # Add tool information if available
        if tools:
            tool_descriptions = []
            for tool in tools:
                tool_descriptions.append(f"- {tool['name']}: {tool.get('description', '')}")
            message_text += f"\n\n[Available Tools]:\n" + "\n".join(tool_descriptions)
        
        # Prepare form data for your API
        form_data = aiohttp.FormData()
        form_data.add_field('message', message_text)
        form_data.add_field('model', self.model)
        
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }
        
        try:
            async with session.post(
                f"{self.base_url}/chat",
                data=form_data,
                headers=headers
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API error {response.status}: {error_text}")
                
                data = await response.json()
                
                # Extract response from your API format
                content = data.get("response", "")
                
                # Estimate token usage (rough approximation)
                prompt_tokens = len(message_text.split()) * 1.3
                completion_tokens = len(content.split()) * 1.3
                
                usage = RequestUsage(
                    prompt_tokens=int(prompt_tokens),
                    completion_tokens=int(completion_tokens)
                )
                self._total_usage = RequestUsage(
                    prompt_tokens=self._total_usage.prompt_tokens + usage.prompt_tokens,
                    completion_tokens=self._total_usage.completion_tokens + usage.completion_tokens
                )
                
                return CreateResult(
                    content=content,
                    usage=usage,
                    finish_reason="stop",
                    cached=False,
                )
                
        except asyncio.TimeoutError:
            raise Exception(f"Request timed out after {self.timeout}s")
        except aiohttp.ClientError as e:
            raise Exception(f"HTTP error: {str(e)}")
    
    async def create_stream(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[ToolSchema] = [],
        json_output: Optional[bool] = None,
        extra_create_args: Mapping[str, Any] = {},
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncGenerator[Union[str, CreateResult], None]:
        """
        Streaming version - falls back to non-streaming since your API doesn't support it
        """
        result = await self.create(
            messages=messages,
            tools=tools,
            json_output=json_output,
            extra_create_args=extra_create_args,
            cancellation_token=cancellation_token,
        )
        yield result
    
    @property
    def model_info(self) -> ModelInfo:
        return self._model_info
    
    def actual_usage(self) -> RequestUsage:
        return self._total_usage
    
    def total_usage(self) -> RequestUsage:
        return self._total_usage
    
    def count_tokens(
        self,
        messages: Sequence[LLMMessage],
        *,
        tools: Sequence[ToolSchema] = [],
    ) -> int:
        """Estimate token count"""
        text = self._messages_to_text(messages)
        # Rough estimation: ~1.3 tokens per word
        return int(len(text.split()) * 1.3)
    
    @property
    def capabilities(self) -> ModelInfo:
        return self._model_info
    
    async def close(self) -> None:
        """Close the HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    def dump_component(self) -> Dict[str, Any]:
        """Serialize component for config"""
        return {
            "provider": self.component_provider_override,
            "config": {
                "base_url": self.base_url,
                "api_key": self.api_key,
                "model": self.model,
                "timeout": self.timeout,
            }
        }
    
    @classmethod
    def load_component(cls, config: Dict[str, Any]) -> "CustomLLMChatCompletionClient":
        """Load from config"""
        cfg = config.get("config", config)
        return cls(
            base_url=cfg.get("base_url", "http://localhost:8080"),
            api_key=cfg.get("api_key", "localApiToken"),
            model=cfg.get("model", "copilot/gpt-4o"),
            timeout=cfg.get("timeout", 120),
        )


# For backward compatibility with AutoGen component loading
def load_component(config: Dict[str, Any]) -> CustomLLMChatCompletionClient:
    return CustomLLMChatCompletionClient.load_component(config)
