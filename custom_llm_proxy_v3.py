#!/usr/bin/env python3
"""
LLM Proxy Server v3 with Structured Output Support

Handles structured output (response_format) by:
1. Converting JSON schema to prompt instructions  
2. Extracting and validating JSON from response
3. Cleaning markdown code blocks
"""

import json
import logging
import re
from typing import Any, Dict, Optional

import aiohttp
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Proxy with Structured Output")

# Configuration
CUSTOM_LLM_URL = "http://localhost:8080/v1/chat/completions"
CUSTOM_LLM_API_KEY = "localApiToken"


def extract_json_schema_description(schema: Dict) -> str:
    """Extract a human-readable description from JSON schema"""
    if not schema:
        return ""
    
    def describe_properties(props: Dict, required: list = None, indent: int = 0) -> list:
        lines = []
        required = required or []
        prefix = "  " * indent
        
        for name, prop in props.items():
            prop_type = prop.get("type", "any")
            description = prop.get("description", "")
            is_required = name in required
            req_marker = " (required)" if is_required else " (optional)"
            
            if prop_type == "object" and "properties" in prop:
                lines.append(f"{prefix}- {name}: object{req_marker}")
                nested = describe_properties(
                    prop["properties"], 
                    prop.get("required", []),
                    indent + 1
                )
                lines.extend(nested)
            elif prop_type == "array":
                items = prop.get("items", {})
                items_type = items.get("type", "any")
                lines.append(f"{prefix}- {name}: array of {items_type}{req_marker}")
                if items_type == "object" and "properties" in items:
                    nested = describe_properties(
                        items["properties"],
                        items.get("required", []),
                        indent + 1
                    )
                    lines.extend(nested)
            else:
                enum = prop.get("enum")
                if enum:
                    lines.append(f"{prefix}- {name}: {prop_type} (one of: {', '.join(map(str, enum))}){req_marker}")
                else:
                    lines.append(f"{prefix}- {name}: {prop_type}{req_marker}{' - ' + description if description else ''}")
        
        return lines
    
    # Handle json_schema wrapper
    if "schema" in schema:
        schema = schema["schema"]
    
    name = schema.get("name", "Response")
    props = schema.get("properties", {})
    required = schema.get("required", [])
    
    lines = [f"JSON object with the following structure ({name}):"]
    lines.extend(describe_properties(props, required))
    
    return "\n".join(lines)


def add_structured_output_instruction(messages: list, response_format: Dict) -> list:
    """Add instruction to prompt for structured output"""
    if not response_format:
        return messages
    
    format_type = response_format.get("type")
    
    if format_type == "json_object":
        # Simple JSON mode
        instruction = "\n\nIMPORTANT: You must respond with valid JSON only. No markdown, no explanations, just the JSON object."
    elif format_type == "json_schema":
        # Structured output with schema
        json_schema = response_format.get("json_schema", {})
        schema_desc = extract_json_schema_description(json_schema)
        instruction = f"""

IMPORTANT: You must respond with valid JSON only that matches this exact schema:
{schema_desc}

Rules:
1. Output ONLY the JSON object, no markdown code blocks, no explanations
2. All required fields must be present
3. Use exact field names as specified
4. Ensure valid JSON syntax"""
    else:
        return messages
    
    # Add instruction to the last user message or create system message
    messages = [msg.copy() for msg in messages]  # Deep copy
    
    # Find last user message
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            content = messages[i].get("content", "")
            if isinstance(content, str):
                messages[i]["content"] = content + instruction
            elif isinstance(content, list):
                # Find text item
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        item["text"] = item.get("text", "") + instruction
                        break
            break
    else:
        # No user message found, add as system message
        messages.insert(0, {"role": "system", "content": instruction.strip()})
    
    return messages


def extract_json_from_response(content: str) -> str:
    """Extract JSON from response content"""
    if not content:
        return content
    
    stripped = content.strip()
    
    # Try to parse as-is first
    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        pass
    
    # Remove markdown code blocks
    if "```" in stripped:
        # Try ```json ... ```
        pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
        match = re.search(pattern, stripped)
        if match:
            extracted = match.group(1).strip()
            try:
                json.loads(extracted)
                return extracted
            except json.JSONDecodeError:
                pass
    
    # Try to find JSON object or array
    for pattern in [r'(\{[\s\S]*\})', r'(\[[\s\S]*\])']:
        match = re.search(pattern, stripped)
        if match:
            candidate = match.group(1)
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue
    
    # Return original if nothing works
    return content


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Handle chat completions with structured output support"""
    try:
        body = await request.json()
        
        model = body.get("model", "unknown")
        messages = body.get("messages", [])
        response_format = body.get("response_format")
        
        # Check for images
        has_images = any(
            isinstance(msg.get("content"), list) and 
            any(item.get("type") == "image_url" for item in msg.get("content", []) if isinstance(item, dict))
            for msg in messages
        )
        
        logger.info(f"Request: model={model}, messages={len(messages)}, has_images={has_images}, "
                   f"response_format={response_format.get('type') if response_format else None}")
        
        # Handle structured output
        if response_format:
            messages = add_structured_output_instruction(messages, response_format)
            logger.info(f"Added structured output instruction for type: {response_format.get('type')}")
        
        # Prepare request body - remove response_format as LLM might not support it
        forward_body = {k: v for k, v in body.items() if k != "response_format"}
        forward_body["messages"] = messages
        
        # Forward to LLM API
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {CUSTOM_LLM_API_KEY}",
                "Content-Type": "application/json"
            }
            
            async with session.post(
                CUSTOM_LLM_URL,
                json=forward_body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    
                    # Extract JSON from content if structured output was requested
                    if response_format and "choices" in result:
                        for choice in result["choices"]:
                            if "message" in choice and "content" in choice["message"]:
                                original = choice["message"]["content"]
                                if original:
                                    cleaned = extract_json_from_response(original)
                                    if cleaned != original:
                                        logger.info(f"Extracted JSON from response")
                                    choice["message"]["content"] = cleaned
                    
                    logger.info(f"Response: {resp.status} OK")
                    return JSONResponse(result)
                else:
                    error_text = await resp.text()
                    logger.error(f"LLM API error: {resp.status} - {error_text[:500]}")
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
    """List available models with capabilities"""
    return {
        "object": "list",
        "data": [
            {
                "id": "copilot/gpt-4o",
                "object": "model",
                "owned_by": "custom",
                "capabilities": {
                    "vision": True,
                    "function_calling": True,
                    "json_output": True,
                    "structured_output": True
                }
            }
        ]
    }


@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok", "version": "3.0"}


if __name__ == "__main__":
    print("=" * 60)
    print("  LLM Proxy Server v3 - Structured Output Support")
    print("=" * 60)
    print(f"  LLM API URL: {CUSTOM_LLM_URL}")
    print(f"  Proxy listening on: http://localhost:8090")
    print()
    print("  Features:")
    print("  - Structured output via prompt injection")
    print("  - JSON extraction from markdown")
    print("  - Schema-aware prompting")
    print("=" * 60)
    print()
    
    uvicorn.run(app, host="0.0.0.0", port=8090)
