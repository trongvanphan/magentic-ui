# Magentic-UI với Custom LLM Provider

Hướng dẫn chi tiết để chạy Magentic-UI với LLM API local của bạn.

## 🏗️ Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────┐
│                      Magentic-UI                                │
│                   http://localhost:8081                         │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────────┐   │
│  │Orchestrator │  │   Coder     │  │     Web Surfer        │   │
│  │             │  │             │  │                       │   │
│  └──────┬──────┘  └──────┬──────┘  └───────────┬───────────┘   │
│         │                │                     │                │
│         └────────────────┴─────────────────────┘                │
│                          │                                      │
│                          ▼                                      │
│              ┌───────────────────────┐                          │
│              │    LLM Proxy Server   │                          │
│              │  http://localhost:8090│                          │
│              │  (OpenAI → Custom API)│                          │
│              └───────────┬───────────┘                          │
└──────────────────────────┼──────────────────────────────────────┘
                           │
                           ▼
              ┌───────────────────────┐
              │   Your Custom LLM API │
              │  http://localhost:8080│
              │                       │
              │  POST /chat           │
              │  {message, model}     │
              └───────────────────────┘
```

## 📁 Cấu trúc files

```
magentic-ui-custom/
├── custom_llm_proxy.py      # Proxy server chuyển đổi OpenAI API → Custom API
├── config_proxy.yaml        # Config cho Magentic-UI
├── venv/                    # Python virtual environment
├── frontend/                # Source code frontend (Gatsby)
└── src/                     # Source code backend
```

## 🚀 Quick Start

### Bước 1: Đảm bảo Custom LLM API đang chạy

```bash
# Test API của bạn
curl -s http://localhost:8080/chat \
  -H "Authorization: Bearer localApiToken" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "model": "copilot/gpt-4o"}'
```

### Bước 2: Khởi động Proxy Server

```bash
cd /Users/trongpv6/Documents/GitHub/poc-code/magentic-ui-custom

# Chạy proxy trong background
nohup ./venv/bin/python custom_llm_proxy.py > /tmp/proxy.log 2>&1 &

# Kiểm tra proxy
curl -s http://localhost:8090/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "copilot/gpt-4o", "messages": [{"role": "user", "content": "Hello"}]}'
```

### Bước 3: Khởi động Magentic-UI

```bash
./venv/bin/magentic-ui \
  --port 8081 \
  --run-without-docker \
  --config ~/.magentic_ui/configs/config_proxy.yaml
```

### Bước 4: Mở trình duyệt

Truy cập: **http://localhost:8081**

## 🛠️ Cấu hình chi tiết

### Custom LLM Proxy (`custom_llm_proxy.py`)

Proxy server chuyển đổi từ OpenAI API format sang Custom API format của bạn.

| Config | Giá trị | Mô tả |
|--------|---------|-------|
| `CUSTOM_LLM_URL` | `http://localhost:8080/chat` | URL của API bạn |
| `CUSTOM_LLM_API_KEY` | `localApiToken` | API key |
| Port | `8090` | Proxy listen port |

**Để thay đổi**, edit file `custom_llm_proxy.py`:

```python
# Configuration
CUSTOM_LLM_URL = "http://localhost:8080/chat"  # ← Thay đổi URL
CUSTOM_LLM_API_KEY = "localApiToken"           # ← Thay đổi API key
```

### Magentic-UI Config (`config_proxy.yaml`)

```yaml
# Tất cả agents sử dụng Custom LLM qua Proxy
custom_llm: &custom_llm
  provider: OpenAIChatCompletionClient
  config:
    model: copilot/gpt-4o
    api_key: "not-needed-for-proxy"
    base_url: "http://localhost:8090/v1"  # ← Proxy URL
    
orchestrator_client: *custom_llm
coder_client: *custom_llm
web_surfer_client: *custom_llm
file_surfer_client: *custom_llm
```

## 🎨 Customize UI (Frontend)

Frontend được build bằng **Gatsby** (React-based).

### Cấu trúc Frontend

```
frontend/
├── src/
│   ├── pages/           # Các trang (routes)
│   │   └── index.tsx    # Trang chính
│   ├── components/      # React components
│   └── styles/          # CSS/Tailwind
├── gatsby-config.ts     # Gatsby config
├── tailwind.config.js   # Tailwind CSS config
└── package.json
```

### Chạy Frontend ở chế độ Development

```bash
cd frontend

# Cài dependencies
npm install --legacy-peer-deps

# Tạo file env
cp .env.default .env.development
# Edit .env.development:
# GATSBY_API_URL=http://localhost:8081/api

# Chạy dev server với hot reload
npm start
# → Frontend chạy tại http://localhost:8000
# → Kết nối tới backend tại http://localhost:8081/api
```

### Build Frontend cho Production

```bash
cd frontend
npm run build
# Output sẽ được copy vào src/magentic_ui/backend/web/ui/
```

### Customize Components

**1. Thay đổi giao diện chat:**
```
frontend/src/components/chat/
```

**2. Thay đổi sidebar:**
```
frontend/src/components/sidebar/
```

**3. Thay đổi theme/colors:**
Edit `frontend/tailwind.config.js`

**4. Thêm trang mới:**
Tạo folder trong `frontend/src/pages/`, ví dụ:
```
frontend/src/pages/about/index.tsx  → Route: /about
```

### Lưu ý khi Customize

1. **Backend API**: Frontend gọi API tại `GATSBY_API_URL` (default: `http://localhost:8081/api`)

2. **Hot Reload**: Chạy `npm start` để thấy thay đổi ngay lập tức

3. **Build lại**: Sau khi sửa, chạy `npm run build` để update production build

## 🔧 Scripts tiện ích

### start_all.sh - Khởi động toàn bộ hệ thống

```bash
#!/bin/bash
# Tạo file này để tiện khởi động

# 1. Start proxy
nohup ./venv/bin/python custom_llm_proxy.py > /tmp/proxy.log 2>&1 &
echo "Proxy started on :8090"

sleep 2

# 2. Start Magentic-UI
./venv/bin/magentic-ui \
  --port 8081 \
  --run-without-docker \
  --config ~/.magentic_ui/configs/config_proxy.yaml

echo "Magentic-UI: http://localhost:8081"
```

### stop_all.sh - Dừng toàn bộ

```bash
#!/bin/bash
pkill -f "custom_llm_proxy.py"
pkill -f "magentic-ui"
echo "All services stopped"
```

## 🐛 Troubleshooting

### Proxy không kết nối được Custom LLM

```bash
# Kiểm tra Custom LLM API
curl http://localhost:8080/chat -H "Content-Type: application/json" \
  -d '{"message": "test", "model": "copilot/gpt-4o"}'

# Xem log proxy
tail -f /tmp/proxy.log
```

### Magentic-UI lỗi "Invalid component class"

Đảm bảo config dùng `OpenAIChatCompletionClient` với `base_url` trỏ đến proxy.

### Frontend không load

1. Kiểm tra đã cài từ PyPI: `pip install magentic-ui`
2. Hoặc build frontend: `cd frontend && npm run build`

### Port đã được sử dụng

```bash
# Kiểm tra port
lsof -i :8081
lsof -i :8090

# Kill process
kill -9 <PID>
```

## 📊 API Format Reference

### Your Custom LLM API

**Request:**
```http
POST http://localhost:8080/chat
Authorization: Bearer localApiToken
Content-Type: application/json

{
  "message": "Hello, how are you?",
  "model": "copilot/gpt-4o"
}
```

**Response:**
```json
{
  "message": "Hello, how are you?",
  "response": "I'm doing well, thank you! How can I help?",
  "model": {"id": "gpt-4o", "name": "GPT-4o"},
  "timestamp": "2025-11-27T01:40:02.360Z"
}
```

### Proxy OpenAI-compatible API

**Request:**
```http
POST http://localhost:8090/v1/chat/completions
Content-Type: application/json

{
  "model": "copilot/gpt-4o",
  "messages": [
    {"role": "system", "content": "You are helpful"},
    {"role": "user", "content": "Hello"}
  ]
}
```

**Response:**
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "model": "copilot/gpt-4o",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "Hi there!"},
    "finish_reason": "stop"
  }]
}
```

## 🔗 Links

- [Magentic-UI GitHub](https://github.com/microsoft/magentic-ui)
- [AutoGen Documentation](https://microsoft.github.io/autogen/)
- [Gatsby Documentation](https://www.gatsbyjs.com/docs/)
