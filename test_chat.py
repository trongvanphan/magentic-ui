#!/usr/bin/env python3
"""
Test chat với Custom LLM qua Proxy
"""

import asyncio
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import UserMessage


async def main():
    # Tạo client kết nối tới proxy
    client = OpenAIChatCompletionClient(
        model="copilot/gpt-4o",
        api_key="not-needed",
        base_url="http://127.0.0.1:8090/v1",
        model_info={
            "vision": True,
            "function_calling": True,
            "json_output": True,
            "family": "unknown",
        }
    )
    
    print("Đang gửi tin nhắn 'Hi' tới Custom LLM...")
    
    # Gửi tin nhắn
    response = await client.create(
        messages=[UserMessage(content="Hi", source="user")]
    )
    
    print(f"\n✅ Response: {response.content}")
    print(f"Model: {response.model}")
    

if __name__ == "__main__":
    asyncio.run(main())
