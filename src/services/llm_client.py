import httpx

from src.core.config import load_config


class LLMClient:
    """Unified client for invoking Gemini, OpenRouter, or DeepSeek APIs."""

    def __init__(self):
        try:
            self.settings = load_config()
        except Exception:
            self.settings = None

    def query(self, prompt: str, system_instruction: str | None = None) -> str:
        """Call the configured LLM API provider with the given prompt."""
        if not self.settings:
            return "Error: Configuration settings not found."

        api_key = (
            self.settings.gemini_api_key
            or self.settings.openrouter_api_key
            or self.settings.deepseek_api_key
        )
        if not api_key:
            return "Error: No API key configured. Please run 'ba config' first."

        # Let's support Gemini direct, OpenRouter, or DeepSeek
        if self.settings.gemini_api_key:
            return self._call_gemini(prompt, system_instruction)
        elif self.settings.openrouter_api_key:
            return self._call_openrouter(prompt, system_instruction)
        elif self.settings.deepseek_api_key:
            return self._call_deepseek(prompt, system_instruction)
        else:
            return "Error: Selected API provider key not configured."

    def _call_gemini(self, prompt: str, system_instruction: str | None = None) -> str:
        """Invoke Gemini API directly using HTTP POST."""
        api_key = self.settings.gemini_api_key
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"

        contents = [{"parts": [{"text": prompt}]}]
        if system_instruction:
            system_instruction_payload = {"parts": [{"text": system_instruction}]}
            payload = {
                "contents": contents,
                "systemInstruction": system_instruction_payload,
            }
        else:
            payload = {"contents": contents}

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, json=payload)
                if response.status_code != 200:
                    return f"API Error (HTTP {response.status_code}): {response.text}"

                res_data = response.json()
                text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return text
        except Exception as e:
            return f"Failed to call Gemini API: {str(e)}"

    def _call_openrouter(
        self, prompt: str, system_instruction: str | None = None
    ) -> str:
        """Invoke OpenRouter API."""
        api_key = self.settings.openrouter_api_key
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": "google/gemma-2-9b-it:free", "messages": messages}

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    return f"API Error (HTTP {response.status_code}): {response.text}"

                res_data = response.json()
                text = res_data["choices"][0]["message"]["content"]
                return text
        except Exception as e:
            return f"Failed to call OpenRouter API: {str(e)}"

    def _call_deepseek(self, prompt: str, system_instruction: str | None = None) -> str:
        """Invoke DeepSeek API."""
        api_key = self.settings.deepseek_api_key
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {"model": "deepseek-chat", "messages": messages}

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    return f"API Error (HTTP {response.status_code}): {response.text}"

                res_data = response.json()
                text = res_data["choices"][0]["message"]["content"]
                return text
        except Exception as e:
            return f"Failed to call DeepSeek API: {str(e)}"
