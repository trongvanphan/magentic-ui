#!/usr/bin/env python3
"""
Simple LLM Proxy Server

LLM API của bạn đã hỗ trợ OpenAI format với base64 images.
Proxy này chỉ cần:
1. Forward request đến LLM API
2. Clean markdown code blocks từ JSON responses

API của bạn:
- POST http://localhost:8080/v1/chat/completions (OpenAI compatible)
- Request: OpenAI format với messages, model, images base64
- Response: OpenAI ChatCompletion format
"""

import json
import logging
import re

import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Simple LLM Proxy")

# Configuration - Your LLM API endpoint
CUSTOM_LLM_URL = "http://localhost:8080/v1/chat/completions"
CUSTOM_LLM_API_KEY = "localApiToken"


def clean_json_in_content(content: str) -> str:
    """Remove markdown code blocks from JSON responses in content"""
    if not content:
        return content
    
    # Check if content looks like it should be JSON
    stripped = content.strip()
    if stripped.startswith("```"):
        # Remove ```json ... ``` or ``` ... ```
        pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(pattern, stripped)
        if match:
            return match.group(1).strip()
    
    return content


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Forward OpenAI-compatible requests to your LLM API"""
    try:
        body = await request.json()
        
        # Log request info
        model = body.get("model", "unknown")
        messages = body.get("messages", [])
        has_images = any(
            isinstance(msg.get("content"), list) and 
            any(item.get("type") == "image_url" for item in msg.get("content", []) if isinstance(item, dict))
            for msg in messages
        )
        logger.info(f"Request: model={model}, messages={len(messages)}, has_images={has_images}")
        
        # Forward to your LLM API
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {CUSTOM_LLM_API_KEY}",
                "Content-Type": "application/json"
            }
            
            async with session.post(
                CUSTOM_LLM_URL,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=180)
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    # Clean markdown from content if present
                    if "choices" in result:
                        for choice in result["choices"]:
                            if "message" in choice and "content" in choice["message"]:
                                original = choice["message"]["content"]
                                cleaned = clean_json_in_content(original)
                                if cleaned != original:
                                    logger.info(f"Cleaned markdown from response")
                                choice["message"]["content"] = cleaned
                    
                    logger.info(f"Response: {resp.status} OK")
                    return JSONResponse(result)
                else:
                    error_text = await resp.text()
                    logger.error(f"LLM API error: {resp.status} - {error_text[:200]}")
                    raise HTTPException(status_code=resp.status, detail=error_text)
                    
    except aiohttp.ClientError as e:
        logger.error(f"Connection error: {e}")
        raise HTTPException(status_code=502, detail=f"LLM API connection error: {str(e)}")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {"id": "copilot/gpt-4o", "object": "model", "owned_by": "custom"},
            {"id": "claude-sonnet-4.5", "object": "model", "owned_by": "custom"}
        ]
    }


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok"}


if __name__ == "__main__":
    print("=" * 60)
    print("  Simple LLM Proxy Server")
    print("  Forwards OpenAI requests to your LLM API")
    print("=" * 60)
    print(f"  LLM API URL: {CUSTOM_LLM_URL}")
    print(f"  Proxy listening on: http://localhost:8090")
    print("=" * 60)
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8090)
