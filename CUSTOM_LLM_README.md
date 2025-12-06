# Magentic-UI với Custom LLM Provider

Hướng dẫn sử dụng Magentic-UI với LLM API local của bạn tại `http://localhost:8080/chat`.

## 🏗️ Kiến trúc

```
┌─────────────────────────────────────────────────────────────┐
│                     Magentic-UI                              │
│                  http://localhost:8081                       │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐    │
│  │Orchestrator │  │   Coder     │  │   File Surfer     │    │
│  │(Custom LLM) │  │(Custom LLM) │  │   (Custom LLM)    │    │
│  └──────┬──────┘  └──────┬──────┘  └─────────┬─────────┘    │
│         │                │                   │               │
│         └────────────────┼───────────────────┘               │
│                          │                                   │
│  ┌───────────────────────┴───────────────────────────────┐  │
│  │              Web Surfer (FARA-7B)                      │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │                              │
          ▼                              ▼
┌──────────────────────┐    ┌──────────────────────────────┐
│  Custom LLM API      │    │     FARA-7B Server           │
│  http://localhost:8080│    │     http://localhost:8000    │
│                      │    │     (Optional)               │
│  POST /chat          │    │                              │
│  - message           │    │                              │
│  - model             │    │                              │
└──────────────────────┘    └──────────────────────────────┘
```

## 📁 Files

| File | Mô tả |
|------|-------|
| `custom_llm_client.py` | Adapter để kết nối với Custom LLM API |
| `config_custom_llm.yaml` | Config sử dụng Custom LLM |
| `start_custom_llm.sh` | Script khởi động |

## 🚀 Cách sử dụng

### 1. Đảm bảo Custom LLM API đang chạy

```bash
# Test API
curl --location 'http://localhost:8080/chat' \
    --header 'Authorization: Bearer localApiToken' \
    --form 'message="Hello"' \
    --form 'model="copilot/gpt-4o"'
```

### 2. (Optional) Khởi động FARA-7B Server

```bash
cd /Users/trongpv6/Documents/GitHub/poc-code/fara
./start_fara_server.sh
```

### 3. Chạy Magentic-UI

```bash
cd /Users/trongpv6/Documents/GitHub/poc-code/magentic-ui-custom
./start_custom_llm.sh
```

### 4. Mở trình duyệt

Truy cập: **http://localhost:8081**

## ⚙️ Cấu hình

### Thay đổi API endpoint

Edit `config_custom_llm.yaml`:

```yaml
custom_llm: &custom_llm
  provider: magentic_ui.custom_llm_client.CustomLLMChatCompletionClient
  config:
    base_url: "http://localhost:8080"    # ← Thay đổi URL
    api_key: "localApiToken"              # ← Thay đổi API key
    model: "copilot/gpt-4o"               # ← Thay đổi model
    timeout: 120
```

### Custom LLM Client

File `src/magentic_ui/custom_llm_client.py` chịu trách nhiệm:
- Convert messages từ AutoGen format sang API format của bạn
- Parse response từ API và trả về cho AutoGen

Nếu API format thay đổi, edit file này.

## 🔧 Troubleshooting

### Custom LLM API không phản hồi

```bash
# Kiểm tra port 8080
lsof -i :8080

# Test trực tiếp
curl -v http://localhost:8080/chat ...
```

### Magentic-UI lỗi kết nối

1. Kiểm tra logs của Custom LLM API
2. Đảm bảo response format đúng:
```json
{
    "message": "...",
    "response": "...",    // ← Quan trọng: field này chứa response
    "model": {...}
}
```

## 📝 API Format Reference

### Request (Your API)
```
POST http://localhost:8080/chat
Headers:
  Authorization: Bearer localApiToken
Body (form-data):
  message: "user message here"
  model: "copilot/gpt-4o"
```

### Response (Your API)
```json
{
    "message": "user message",
    "response": "AI response here",
    "model": {
        "id": "gpt-4o",
        "name": "GPT-4o"
    },
    "sessionId": null,
    "memory": null,
    "attachments": [],
    "timestamp": "2025-11-26T15:40:33.589Z"
}
```
