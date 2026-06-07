import os


class LLMClient:
    def __init__(self, config):
        self.config = config
        self.llm_config = config.get("llm", {})
        self.mode = config.get("general", {}).get("mode", "dry_run")
        self.api_key = self._resolve_key("api_key")
        self.model = self.llm_config.get("model", "claude-sonnet-4-20250514")
        self.max_tokens = self.llm_config.get("max_tokens", 4096)

    def _resolve_key(self, key_name):
        raw = self.llm_config.get(key_name, "")
        if isinstance(raw, str) and raw.startswith("${") and raw.endswith("}"):
            env_var = raw[2:-1]
            return os.environ.get(env_var, "")
        return raw

    def call(self, system_prompt, user_prompt, temperature=0.7):
        if self.mode == "dry_run":
            return self._mock(system_prompt, user_prompt)
        return self._real(system_prompt, user_prompt, temperature)

    def _mock(self, system_prompt, user_prompt):
        content = f"[DRY-RUN] Response for: {user_prompt[:100]}..."
        return {
            "mode": "dry_run",
            "model": self.model,
            "system_length": len(system_prompt),
            "user_length": len(user_prompt),
            "content": content,
        }

    def _real(self, system_prompt, user_prompt, temperature):
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package not installed. Run: pip install anthropic"
            )
        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = ""
        if response.content:
            text = response.content[0].text
        return {
            "mode": "production",
            "model": self.model,
            "content": text,
        }
