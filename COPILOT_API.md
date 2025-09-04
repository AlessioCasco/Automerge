# GitHub Copilot API Integration via Proxy

## Current Implementation

The AI confidence score feature now uses the [copilot-api proxy](https://github.com/ericc-ch/copilot-api) to access GitHub Copilot via Claude 4.0.

### Proxy Configuration
- **Endpoint**: `http://localhost:4141/v1/messages`
- **Model**: `claude-sonnet-4`
- **Format**: Anthropic compatible API

### Setup Instructions

1. **Install and start the proxy:**
   ```bash
   npx copilot-api@latest start
   ```

2. **Verify the proxy is running:**
   ```bash
   python test_copilot_proxy.py
   ```

3. **The proxy will provide:**
   - Web dashboard at: `https://ericc-ch.github.io/copilot-api?endpoint=http://localhost:4141/usage`
   - Usage monitoring
   - Rate limiting protection

### API Request Format

The system now uses the Anthropic compatible endpoint:

```json
{
  "model": "claude-4.0",
  "max_tokens": 500,
  "messages": [
    {
      "role": "user",
      "content": "Your prompt here..."
    }
  ]
}
```

### Response Format

The proxy returns responses in Anthropic format:

```json
{
  "content": [
    {
      "text": "SCORE: 85% - Safe provider update with no breaking changes"
    }
  ]
}
```
