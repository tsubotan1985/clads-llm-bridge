"""Health check service for LLM configurations."""

import asyncio
import aiohttp
import time
from typing import List, Dict, Optional
from datetime import datetime

from ..database.connection import DatabaseConnection
from ..models.llm_config import LLMConfig
from ..models.health_status import HealthStatus
from ..models.enums import ServiceType


class HealthService:
    """Service for checking health of LLM configurations."""
    
    def __init__(self, db_path: str = None):
        """Initialize the health service.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path or "data/clads_llm_bridge.db"
        self.db = DatabaseConnection(self.db_path)
        self.timeout = 30  # 30 seconds timeout for health checks
    
    async def test_llm_config(self, config: LLMConfig) -> HealthStatus:
        """Test a single LLM configuration.
        
        Args:
            config: LLMConfig object to test
            
        Returns:
            HealthStatus object with test results
        """
        start_time = time.time()
        
        try:
            if config.service_type == ServiceType.NONE:
                return HealthStatus(
                    service_id=config.id,
                    status="OK",
                    last_checked=datetime.utcnow(),
                    response_time_ms=0,
                    model_count=0
                )
            
            # Test based on service type
            if config.service_type == ServiceType.OPENAI:
                result = await self._test_openai(config)
            elif config.service_type == ServiceType.ANTHROPIC:
                result = await self._test_anthropic(config)
            elif config.service_type == ServiceType.GEMINI:
                result = await self._test_gemini(config)
            elif config.service_type == ServiceType.OPENROUTER:
                result = await self._test_openrouter(config)
            elif config.service_type == ServiceType.VSCODE_PROXY:
                result = await self._test_vscode_proxy(config)
            elif config.service_type == ServiceType.LMSTUDIO:
                result = await self._test_lmstudio(config)
            elif config.service_type == ServiceType.OPENAI_COMPATIBLE:
                result = await self._test_openai_compatible(config)
            else:
                result = HealthStatus(
                    service_id=config.id,
                    status="NG",
                    last_checked=datetime.utcnow(),
                    error_message="Unsupported service type"
                )
            
            # Calculate response time
            response_time = int((time.time() - start_time) * 1000)
            result.response_time_ms = response_time
            
            return result
            
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            return HealthStatus(
                service_id=config.id,
                status="NG",
                last_checked=datetime.utcnow(),
                error_message=str(e),
                response_time_ms=response_time
            )
    
    async def _test_openai(self, config: LLMConfig) -> HealthStatus:
        """Test OpenAI API configuration."""
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(f"{config.base_url}/models", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    model_count = len(data.get("data", []))
                    return HealthStatus(
                        service_id=config.id,
                        status="OK",
                        last_checked=datetime.utcnow(),
                        model_count=model_count
                    )
                else:
                    error_text = await response.text()
                    return HealthStatus(
                        service_id=config.id,
                        status="NG",
                        last_checked=datetime.utcnow(),
                        error_message=f"HTTP {response.status}: {error_text}"
                    )
    
    async def _test_anthropic(self, config: LLMConfig) -> HealthStatus:
        """Test Anthropic API configuration."""
        headers = {
            "x-api-key": config.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        # Anthropic doesn't have a models endpoint, so we test with a simple completion
        data = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "Hi"}]
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.post(f"{config.base_url}/messages", headers=headers, json=data) as response:
                if response.status == 200:
                    return HealthStatus(
                        service_id=config.id,
                        status="OK",
                        last_checked=datetime.utcnow(),
                        model_count=1  # We can't get exact count, so assume 1
                    )
                else:
                    error_text = await response.text()
                    return HealthStatus(
                        service_id=config.id,
                        status="NG",
                        last_checked=datetime.utcnow(),
                        error_message=f"HTTP {response.status}: {error_text}"
                    )
    
    async def _test_gemini(self, config: LLMConfig) -> HealthStatus:
        """Test Google AI Studio (Gemini) API configuration."""
        # For Gemini, we test by listing models
        url = f"{config.base_url}/models?key={config.api_key}"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    model_count = len(data.get("models", []))
                    return HealthStatus(
                        service_id=config.id,
                        status="OK",
                        last_checked=datetime.utcnow(),
                        model_count=model_count
                    )
                else:
                    error_text = await response.text()
                    return HealthStatus(
                        service_id=config.id,
                        status="NG",
                        last_checked=datetime.utcnow(),
                        error_message=f"HTTP {response.status}: {error_text}"
                    )
    
    async def _test_openrouter(self, config: LLMConfig) -> HealthStatus:
        """Test OpenRouter API configuration."""
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(f"{config.base_url}/models", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    model_count = len(data.get("data", []))
                    return HealthStatus(
                        service_id=config.id,
                        status="OK",
                        last_checked=datetime.utcnow(),
                        model_count=model_count
                    )
                else:
                    error_text = await response.text()
                    return HealthStatus(
                        service_id=config.id,
                        status="NG",
                        last_checked=datetime.utcnow(),
                        error_message=f"HTTP {response.status}: {error_text}"
                    )
    
    async def _test_vscode_proxy(self, config: LLMConfig) -> HealthStatus:
        """Test VS Code LM Proxy configuration."""
        # VS Code LM Proxy doesn't require authentication
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(f"{config.base_url}/v1/models") as response:
                if response.status == 200:
                    data = await response.json()
                    model_count = len(data.get("data", []))
                    return HealthStatus(
                        service_id=config.id,
                        status="OK",
                        last_checked=datetime.utcnow(),
                        model_count=model_count
                    )
                else:
                    error_text = await response.text()
                    return HealthStatus(
                        service_id=config.id,
                        status="NG",
                        last_checked=datetime.utcnow(),
                        error_message=f"HTTP {response.status}: {error_text}"
                    )
    
    async def _test_lmstudio(self, config: LLMConfig) -> HealthStatus:
        """Test LM Studio configuration."""
        # LM Studio uses OpenAI-compatible API without authentication
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(f"{config.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    model_count = len(data.get("data", []))
                    return HealthStatus(
                        service_id=config.id,
                        status="OK",
                        last_checked=datetime.utcnow(),
                        model_count=model_count
                    )
                else:
                    error_text = await response.text()
                    return HealthStatus(
                        service_id=config.id,
                        status="NG",
                        last_checked=datetime.utcnow(),
                        error_message=f"HTTP {response.status}: {error_text}"
                    )
    
    async def _test_openai_compatible(self, config: LLMConfig) -> HealthStatus:
        """Test OpenAI-compatible API configuration."""
        headers = {}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        headers["Content-Type"] = "application/json"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(f"{config.base_url}/models", headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    model_count = len(data.get("data", []))
                    return HealthStatus(
                        service_id=config.id,
                        status="OK",
                        last_checked=datetime.utcnow(),
                        model_count=model_count
                    )
                else:
                    error_text = await response.text()
                    return HealthStatus(
                        service_id=config.id,
                        status="NG",
                        last_checked=datetime.utcnow(),
                        error_message=f"HTTP {response.status}: {error_text}"
                    )
    
    async def test_all_configs(self, configs: List[LLMConfig]) -> List[HealthStatus]:
        """Test all LLM configurations concurrently.
        
        Args:
            configs: List of LLMConfig objects to test
            
        Returns:
            List of HealthStatus objects
        """
        tasks = [self.test_llm_config(config) for config in configs]
        return await asyncio.gather(*tasks, return_exceptions=False)
    
    def save_health_status(self, status: HealthStatus) -> bool:
        """Save health status to database.
        
        Args:
            status: HealthStatus object to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.db.execute_update("""
                INSERT OR REPLACE INTO health_status 
                (service_id, status, last_checked, error_message, 
                 response_time_ms, model_count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                status.service_id,
                status.status,
                status.last_checked.isoformat(),
                status.error_message,
                status.response_time_ms,
                status.model_count
            ))
            return True
        except Exception as e:
            print(f"Error saving health status: {e}")
            return False
    
    def get_health_status(self, service_id: str) -> Optional[HealthStatus]:
        """Get health status for a service.
        
        Args:
            service_id: The service ID
            
        Returns:
            HealthStatus object or None if not found
        """
        try:
            rows = self.db.execute_query("""
                SELECT service_id, status, last_checked, error_message,
                       response_time_ms, model_count
                FROM health_status
                WHERE service_id = ?
            """, (service_id,))
            
            if not rows:
                return None
            
            row = rows[0]
            return HealthStatus(
                service_id=row['service_id'],
                status=row['status'],
                last_checked=datetime.fromisoformat(row['last_checked']),
                error_message=row['error_message'],
                response_time_ms=row['response_time_ms'],
                model_count=row['model_count']
            )
        except Exception as e:
            print(f"Error getting health status: {e}")
            return None
    
    def get_all_health_status(self) -> Dict[str, HealthStatus]:
        """Get all health statuses.
        
        Returns:
            Dictionary mapping service_id to HealthStatus
        """
        try:
            rows = self.db.execute_query("""
                SELECT service_id, status, last_checked, error_message,
                       response_time_ms, model_count
                FROM health_status
            """)
            
            statuses = {}
            for row in rows:
                status = HealthStatus(
                    service_id=row['service_id'],
                    status=row['status'],
                    last_checked=datetime.fromisoformat(row['last_checked']),
                    error_message=row['error_message'],
                    response_time_ms=row['response_time_ms'],
                    model_count=row['model_count']
                )
                statuses[row['service_id']] = status
            
            return statuses
        except Exception as e:
            print(f"Error getting all health statuses: {e}")
            return {}