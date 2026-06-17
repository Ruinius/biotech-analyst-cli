from pathlib import Path

from pydantic import BaseModel, Field

from src.core.exceptions import ConfigError, ConfigNotFoundError

CONFIG_FILE_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def get_default_desktop() -> str:
    """Get generic path to the user's Desktop/AI_Native_2026 directory."""
    return "~/Desktop/AI_Native_2026"


class Settings(BaseModel):
    full_name: str = Field(..., description="Full name of the user")
    email: str = Field(..., description="Email address of the user")
    base_folder: str = Field(
        default_factory=get_default_desktop, description="Base directory for targets"
    )
    gemini_api_key: str | None = Field(None, description="Gemini API Key")
    openrouter_api_key: str | None = Field(None, description="OpenRouter API Key")
    deepseek_api_key: str | None = Field(None, description="DeepSeek API Key")
    llm_provider: str = Field(
        "gemini", description="Selected LLM provider (gemini, openrouter, deepseek)"
    )
    llm_model: str | None = Field(None, description="Selected LLM model name")
    gemini_model: str | None = Field(None, description="Gemini model preference")
    openrouter_model: str | None = Field(
        None, description="OpenRouter model preference"
    )
    deepseek_model: str | None = Field(None, description="DeepSeek model preference")

    @property
    def expanded_base_folder(self) -> str:
        if self.base_folder:
            return str(Path(self.base_folder).expanduser())
        return self.base_folder


def config_exists() -> bool:
    """Check if the settings file exists and contains valid config settings."""
    if not CONFIG_FILE_PATH.exists():
        return False
    try:
        required_keys = {"full_name", "email"}
        found_keys = set()
        with open(CONFIG_FILE_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key = line.split("=", 1)[0].strip().lower()
                    if key in required_keys:
                        found_keys.add(key)
        return len(found_keys) == len(required_keys)
    except Exception:
        return False


def load_config() -> Settings:
    """Load configuration from the configuration file."""
    if not config_exists():
        raise ConfigNotFoundError(
            "Configuration file not found. Please run 'ba config' first."
        )
    try:
        data = {}
        with open(CONFIG_FILE_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip().lower()
                    value = value.strip()
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    if value == "":
                        data[key] = None
                    else:
                        data[key] = value

        # Backwards compatibility and fallbacks
        if "base_folder" not in data or not data["base_folder"]:
            data["base_folder"] = get_default_desktop()

        return Settings(**data)
    except Exception as e:
        raise ConfigError(f"Failed to load configuration: {str(e)}")


def save_config(settings: Settings) -> None:
    """Save configuration to the configuration file."""
    try:
        CONFIG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
            for key, value in settings.model_dump().items():
                env_key = key.upper()
                env_value = "" if value is None else str(value)
                f.write(f'{env_key}="{env_value}"\n')
    except Exception as e:
        raise ConfigError(f"Failed to save configuration: {str(e)}")


def mask_key(key: str | None) -> str:
    """Mask a sensitive API key, revealing only a small prefix and suffix."""
    if not key:
        return "Not Set"
    if len(key) <= 8:
        return "****"
    prefix = key[:3]
    suffix = key[-4:]
    return f"{prefix}...{suffix}"
