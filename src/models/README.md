# Data Models

This module contains the Pydantic data models for CLADS LLM Bridge.

## Models

### ServiceType (Enum)
Defines the supported LLM service types:
- `OPENAI` - OpenAI API
- `ANTHROPIC` - Anthropic Claude API  
- `GEMINI` - Google AI Studio (Gemini)
- `OPENROUTER` - OpenRouter API
- `VSCODE_PROXY` - VS Code LM Proxy
- `LMSTUDIO` - LM Studio local server
- `OPENAI_COMPATIBLE` - Custom OpenAI-compatible APIs
- `NONE` - Disabled/no service

### LLMConfig
Configuration for an LLM service including:
- Service type and connection details
- API key (with masking support)
- Model name and public display name
- Enable/disable status
- Timestamps

### UsageRecord
Records API usage for monitoring:
- Client IP and model used
- Token counts (input/output/total)
- Response time and status
- Error messages if applicable

### HealthStatus
Health check results for services:
- Service status (OK/NG)
- Last check timestamp
- Error messages and response times
- Model count if available

## Usage

```python
from models import ServiceType, LLMConfig, UsageRecord, HealthStatus

# Create a new LLM configuration
config = LLMConfig(
    id="openai-1",
    service_type=ServiceType.OPENAI,
    api_key="sk-...",
    model_name="gpt-3.5-turbo",
    public_name="GPT-3.5"
)

# The base URL will be automatically set based on service type
print(config.base_url)  # https://api.openai.com/v1

# API key masking for display
print(config.mask_api_key())  # sk-****...****

# Convert to/from dict for database storage
config_dict = config.to_dict()
restored_config = LLMConfig.from_dict(config_dict)
```