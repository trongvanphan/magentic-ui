#!/usr/bin/env python3
"""
Custom LLM Proxy Server

Chuyển đổi OpenAI-compatible API sang Custom LLM API format của bạn.

API của bạn:
- POST http://localhost:8080/chat
- Request: form-data với 'message', 'model', 'images' (file)
- Response: {"message": ..., "response": ..., "model": {...}}

OpenAI format:
- POST /v1/chat/completions
- Request: JSON với messages, model (có thể có image base64)
- Response: OpenAI ChatCompletion format
"""

import base64
import json
import logging
import re
import time
import uuid
from typing import Optional, List, Tuple

import aiohttp
from aiohttp import FormData
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Custom LLM Proxy")

# Configuration
CUSTOM_LLM_URL = "http://localhost:8080/chat"
CUSTOM_LLM_API_KEY = "localApiToken"


def clean_json_response(text: str) -> str:
    """Remove markdown code blocks from JSON responses"""
    # Remove ```json ... ``` or ``` ... ```
    pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return text


def extract_images_from_messages(messages: list) -> Tuple[str, List[bytes]]:
    """
    Extract text and images from OpenAI messages format.
    Returns: (text_content, list_of_image_bytes)
    """
    parts = []
    images = []
    
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        # Handle content as list (multimodal)
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        # Extract image from base64 URL
                        image_url = item.get("image_url", {})
                        if isinstance(image_url, dict):
                            url = image_url.get("url", "")
                        else:
                            url = str(image_url)
                        
                        if url.startswith("data:image"):
                            # Parse data URL: data:image/png;base64,xxxxx
                            try:
                                # Split by comma to get base64 part
                                base64_data = url.split(",", 1)[1] if "," in url else ""
                                if base64_data:
                                    image_bytes = base64.b64decode(base64_data)
                                    images.append(image_bytes)
                                    text_parts.append("[Screenshot of current browser state]")
                                    logger.info(f"Extracted image: {len(image_bytes)} bytes")
                            except Exception as e:
                                logger.error(f"Failed to decode image: {e}")
                                text_parts.append("[Image decode failed]")
                        else:
                            text_parts.append(f"[Image URL: {url[:50]}...]")
                else:
                    text_parts.append(str(item))
            content = " ".join(text_parts)
        
        if role == "system":
            parts.append(f"[System]: {content}")
        elif role == "user":
            parts.append(f"[User]: {content}")
        elif role == "assistant":
            parts.append(f"[Assistant]: {content}")
        else:
            parts.append(f"[{role}]: {content}")
    
    text = "\n\n".join(parts)
    return text, images


def create_openai_response(content: str, model: str = "custom-llm") -> dict:
    """Create OpenAI-compatible response"""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }


async def call_custom_llm(message: str, model: str = "copilot/gpt-4o", images: List[bytes] = None) -> Optional[str]:
    """Call your custom LLM API with optional images"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {CUSTOM_LLM_API_KEY}",
            }
            
            logger.info(f"Calling Custom LLM: {CUSTOM_LLM_URL}")
            logger.info(f"Message (first 100 chars): {message[:100]}...")
            
            if images and len(images) > 0:
                # Use form-data with images
                logger.info(f"Sending {len(images)} image(s) with request")
                
                form = FormData()
                form.add_field('message', message)
                form.add_field('model', model)
                
                # Add images
                for i, img_bytes in enumerate(images):
                    # Detect image type from bytes
                    if img_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                        ext = 'png'
                        content_type = 'image/png'
                    elif img_bytes[:2] == b'\xff\xd8':
                        ext = 'jpg'
                        content_type = 'image/jpeg'
                    elif img_bytes[:6] in (b'GIF87a', b'GIF89a'):
                        ext = 'gif'
                        content_type = 'image/gif'
                    elif img_bytes[:4] == b'RIFF' and img_bytes[8:12] == b'WEBP':
                        ext = 'webp'
                        content_type = 'image/webp'
                    else:
                        ext = 'png'
                        content_type = 'image/png'
                    
                    filename = f"screenshot_{i}.{ext}"
                    form.add_field(
                        'images',
                        img_bytes,
                        filename=filename,
                        content_type=content_type
                    )
                    logger.info(f"Added image: {filename} ({len(img_bytes)} bytes, {content_type})")
                
                async with session.post(
                    CUSTOM_LLM_URL,
                    data=form,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=180)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        response_text = result.get("response", "")
                        cleaned = clean_json_response(response_text)
                        logger.info(f"Response (first 100 chars): {cleaned[:100]}...")
                        return cleaned
                    else:
                        error_text = await resp.text()
                        logger.error(f"Custom LLM error: {resp.status} - {error_text}")
                        return None
            else:
                # No images - use JSON payload
                payload = {
                    "message": message,
                    "model": model
                }
                headers["Content-Type"] = "application/json"
                
                async with session.post(
                    CUSTOM_LLM_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        response_text = result.get("response", "")
                        cleaned = clean_json_response(response_text)
                        logger.info(f"Response (first 100 chars): {cleaned[:100]}...")
                        return cleaned
                    else:
                        error_text = await resp.text()
                        logger.error(f"Custom LLM error: {resp.status} - {error_text}")
                        return None
    except Exception as e:
        logger.error(f"Error calling Custom LLM: {e}")
        import traceback
        traceback.print_exc()
        return None


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint"""
    try:
        body = await request.json()
        messages = body.get("messages", [])
        model = body.get("model", "copilot/gpt-4o")
        stream = body.get("stream", False)
        
        # Extract text and images from messages
        text, images = extract_images_from_messages(messages)
        logger.info(f"Converted message (first 200 chars): {text[:200]}...")
        if images:
            logger.info(f"Found {len(images)} image(s) in request")
        
        # Call custom LLM with images if any
        response_text = await call_custom_llm(text, model, images)
        
        if response_text is None:
            raise HTTPException(status_code=500, detail="Failed to get response from Custom LLM")
        
        if stream:
            # Streaming response
            async def generate():
                # Send content in chunks
                chunk = {
                    "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"role": "assistant", "content": response_text},
                            "finish_reason": None
                        }
                    ]
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                
                # Send finish
                finish_chunk = {
                    "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }
                    ]
                }
                yield f"data: {json.dumps(finish_chunk)}\n\n"
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(
                generate(),
                media_type="text/event-stream"
            )
        else:
            # Non-streaming response
            return JSONResponse(create_openai_response(response_text, model))
    
    except Exception as e:
        logger.error(f"Error in chat_completions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {
                "id": "copilot/gpt-4o",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "custom"
            }
        ]
    }


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok"}


if __name__ == "__main__":
    print("=" * 60)
    print("  Custom LLM Proxy Server (with Vision support)")
    print("  Converts OpenAI API -> Your Custom LLM API")
    print("=" * 60)
    print(f"  Custom LLM URL: {CUSTOM_LLM_URL}")
    print(f"  Proxy listening on: http://localhost:8090")
    print("=" * 60)
    print()
    print("  Features:")
    print("    - Converts OpenAI chat format to your API")
    print("    - Extracts base64 images and sends as files")
    print("    - Cleans markdown code blocks from responses")
    print()
    print("  Use this as base_url in Magentic-UI config:")
    print("    base_url: http://localhost:8090/v1")
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8090)
