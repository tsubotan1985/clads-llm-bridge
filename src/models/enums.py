"""Enums for CLADS LLM Bridge."""

from enum import Enum


class ServiceType(Enum):
    """Supported LLM service types."""
    
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"
    VSCODE_PROXY = "vscode_proxy"
    LMSTUDIO = "lmstudio"
    OPENAI_COMPATIBLE = "openai_compatible"
    NONE = "none"
    
    @classmethod
    def get_default_base_urls(cls) -> dict[str, str]:
        """Get default base URLs for each service type."""
        return {
            cls.OPENAI.value: "https://api.openai.com/v1",
            cls.ANTHROPIC.value: "https://api.anthropic.com",
            cls.GEMINI.value: "https://generativelanguage.googleapis.com/v1beta",
            cls.OPENROUTER.value: "https://openrouter.ai/api/v1",
            cls.VSCODE_PROXY.value: "http://127.0.0.1:3000",
            cls.LMSTUDIO.value: "http://127.0.0.1:1234/v1",
            cls.OPENAI_COMPATIBLE.value: "",  # Custom URL required
            cls.NONE.value: ""
        }
    
    def get_default_base_url(self) -> str:
        """Get the default base URL for this service type."""
        return self.get_default_base_urls().get(self.value, "")