"""
LLM Provider implementations.

Each provider implements the BaseLLM interface with provider-specific API calls.
"""

from ariadne.llm.base import BaseLLM, LLMConfig, LLMResponse, LLMProvider
from typing import List, Dict, Any, Optional
import requests
import json


class DeepSeekLLM(BaseLLM):
    """DeepSeek LLM provider (deepseek-chat, deepseek-coder)."""
    
    DEFAULT_BASE_URL = "https://api.deepseek.com"
    DEFAULT_MODEL = "deepseek-chat"
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.DEEPSEEK
    
    def _call_api(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Call DeepSeek API."""
        base_url = self.config.base_url or self.DEFAULT_BASE_URL
        url = f"{base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        
        payload = {
            "model": self.config.model or self.DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        
        # Estimate cost (DeepSeek is cheap)
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        cost = (prompt_tokens * 0.00027 + completion_tokens * 0.0011) / 1000
        
        return LLMResponse(
            content=content,
            raw_response=data,
            model=data.get("model", self.config.model),
            usage=usage,
            cost=cost,
        )


class OpenAILLM(BaseLLM):
    """OpenAI LLM provider (GPT-4, GPT-4o, GPT-3.5)."""
    
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o"
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OPENAI
    
    def _call_api(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Call OpenAI API."""
        base_url = self.config.base_url or self.DEFAULT_BASE_URL
        url = f"{base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        
        payload = {
            "model": self.config.model or self.DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        
        # Calculate cost based on model
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        model = data.get("model", self.config.model)
        
        if "gpt-4o" in model:
            cost = (prompt_tokens * 0.005 + completion_tokens * 0.015) / 1000
        elif "gpt-4" in model:
            cost = (prompt_tokens * 0.03 + completion_tokens * 0.06) / 1000
        else:
            cost = (prompt_tokens * 0.0015 + completion_tokens * 0.002) / 1000
        
        return LLMResponse(
            content=content,
            raw_response=data,
            model=model,
            usage=usage,
            cost=cost,
        )


class AnthropicLLM(BaseLLM):
    """Anthropic LLM provider (Claude 3, Claude 3.5)."""
    
    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"
    DEFAULT_MODEL = "claude-3-5-sonnet-20241022"
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.ANTHROPIC
    
    def _call_api(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Call Anthropic API."""
        base_url = self.config.base_url or self.DEFAULT_BASE_URL
        url = f"{base_url}/messages"
        
        # Convert messages format for Anthropic
        system_msg = ""
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                anthropic_messages.append({
                    "role": "user" if msg["role"] == "user" else "assistant",
                    "content": msg["content"],
                })
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-dangerous-direct-browser-access": "true",
        }
        
        payload = {
            "model": self.config.model or self.DEFAULT_MODEL,
            "messages": anthropic_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        if system_msg:
            payload["system"] = system_msg
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        data = response.json()
        
        content = data["content"][0]["text"]
        usage = {
            "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
            "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
        }
        
        # Estimate cost (Claude pricing)
        cost = (usage["prompt_tokens"] * 0.003 + usage["completion_tokens"] * 0.015) / 1000
        
        return LLMResponse(
            content=content,
            raw_response=data,
            model=data.get("model", self.config.model),
            usage=usage,
            cost=cost,
        )


class QwenLLM(BaseLLM):
    """Alibaba Cloud Qwen LLM provider."""
    
    DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    DEFAULT_MODEL = "qwen-plus"
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.QWEN
    
    def _call_api(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Call Qwen API via DashScope."""
        base_url = self.config.base_url or self.DEFAULT_BASE_URL
        url = f"{base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        
        payload = {
            "model": self.config.model or self.DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        
        return LLMResponse(
            content=content,
            raw_response=data,
            model=data.get("model", self.config.model),
            usage=usage,
        )


class GeminiLLM(BaseLLM):
    """Google Gemini LLM provider."""
    
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
    DEFAULT_MODEL = "gemini-1.5-flash"
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.GEMINI
    
    def _call_api(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Call Google Gemini API."""
        model = self.config.model or self.DEFAULT_MODEL
        base_url = self.config.base_url or self.DEFAULT_BASE_URL
        url = f"{base_url}/models/{model}:generateContent"
        
        # Convert messages format for Gemini
        contents = []
        for msg in messages:
            if msg["role"] != "system":
                contents.append({
                    "role": "user" if msg["role"] == "user" else "model",
                    "parts": [{"text": msg["content"]}],
                })
        
        params = {"key": self.config.api_key}
        
        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", self.config.max_tokens),
                "temperature": kwargs.get("temperature", self.config.temperature),
            },
        }
        
        response = requests.post(
            url,
            params=params,
            json=payload,
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        data = response.json()
        
        content = data["candidates"][0]["content"]["parts"][0]["text"]
        
        return LLMResponse(
            content=content,
            raw_response=data,
            model=model,
        )


class GrokLLM(BaseLLM):
    """xAI Grok LLM provider."""
    
    DEFAULT_BASE_URL = "https://api.x.ai/v1"
    DEFAULT_MODEL = "grok-2-1212"
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.GROK
    
    def _call_api(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Call xAI Grok API."""
        base_url = self.config.base_url or self.DEFAULT_BASE_URL
        url = f"{base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        
        payload = {
            "model": self.config.model or self.DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
        }
        
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        data = response.json()
        
        content = data["choices"][0]["message"]["content"]
        
        return LLMResponse(
            content=content,
            raw_response=data,
            model=data.get("model", self.config.model),
        )
