"""Tests for config module - M3.4 API Key Management.

Tests cover:
- Config file creation and loading
- API key get/set with env var precedence
- Default agent and model settings
- Config round-trip through save/load
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch
import tempfile
import yaml

from alienbio import config


@pytest.fixture
def temp_config_dir(tmp_path):
    """Use a temporary directory for config during tests."""
    config_dir = tmp_path / ".config" / "alienbio"
    config_file = config_dir / "config.yaml"

    # Clear any existing API key env vars to isolate tests
    env_vars_to_clear = [
        "ANTHROPIC_API_KEY", "ALIENBIO_ANTHROPIC_API_KEY",
        "OPENAI_API_KEY", "ALIENBIO_OPENAI_API_KEY",
        "GOOGLE_API_KEY", "ALIENBIO_GOOGLE_API_KEY",
    ]
    clean_env = {k: v for k, v in os.environ.items() if k not in env_vars_to_clear}

    # Patch the config module's paths and clear env vars
    with patch.object(config, 'CONFIG_DIR', config_dir), \
         patch.object(config, 'CONFIG_FILE', config_file), \
         patch.dict(os.environ, clean_env, clear=True):
        yield config_dir, config_file


class TestConfigBasics:
    """Basic config functionality tests."""

    def test_default_config_structure(self):
        """Default config has expected structure."""
        assert "api_keys" in config.DEFAULT_CONFIG
        assert "default_agent" in config.DEFAULT_CONFIG
        assert "providers" in config.DEFAULT_CONFIG

    def test_get_config_path(self):
        """get_config_path returns Path object."""
        path = config.get_config_path()
        assert isinstance(path, Path)
        assert path.name == "config.yaml"


class TestConfigLoadSave:
    """Tests for loading and saving config."""

    def test_load_config_returns_defaults_when_missing(self, temp_config_dir):
        """load_config returns defaults when file doesn't exist."""
        cfg = config.load_config()
        assert cfg == config.DEFAULT_CONFIG

    def test_save_then_load_roundtrip(self, temp_config_dir):
        """Config survives save/load round-trip."""
        test_config = {
            "api_keys": {"anthropic": "test-key-123"},
            "default_agent": "anthropic",
            "providers": {"anthropic": {"default_model": "claude-3"}},
        }

        config.save_config(test_config)
        loaded = config.load_config()

        assert loaded["api_keys"]["anthropic"] == "test-key-123"
        assert loaded["default_agent"] == "anthropic"
        assert loaded["providers"]["anthropic"]["default_model"] == "claude-3"

    def test_ensure_config_dir_creates_directory(self, temp_config_dir):
        """ensure_config_dir creates the config directory."""
        config_dir, _ = temp_config_dir
        assert not config_dir.exists()

        config.ensure_config_dir()

        assert config_dir.exists()

    def test_save_config_creates_file(self, temp_config_dir):
        """save_config creates the config file."""
        _, config_file = temp_config_dir
        assert not config_file.exists()

        config.save_config({"api_keys": {}})

        assert config_file.exists()


class TestApiKeyManagement:
    """Tests for API key get/set functions."""

    def test_set_api_key(self, temp_config_dir):
        """set_api_key stores key in config."""
        config.set_api_key("anthropic", "sk-ant-test123")

        cfg = config.load_config()
        assert cfg["api_keys"]["anthropic"] == "sk-ant-test123"

    def test_get_api_key_from_config(self, temp_config_dir):
        """get_api_key retrieves from config file."""
        config.set_api_key("openai", "sk-openai-test456")

        key = config.get_api_key("openai")
        assert key == "sk-openai-test456"

    def test_get_api_key_returns_none_when_missing(self, temp_config_dir):
        """get_api_key returns None when key not found."""
        key = config.get_api_key("nonexistent")
        assert key is None

    def test_get_api_key_env_var_takes_precedence(self, temp_config_dir):
        """Environment variable overrides config file."""
        # Set key in config
        config.set_api_key("anthropic", "config-key")

        # Set env var
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            key = config.get_api_key("anthropic")

        assert key == "env-key"

    def test_get_api_key_alienbio_env_var(self, temp_config_dir):
        """ALIENBIO_*_API_KEY env var works."""
        with patch.dict(os.environ, {"ALIENBIO_ANTHROPIC_API_KEY": "alienbio-env-key"}):
            key = config.get_api_key("anthropic")

        assert key == "alienbio-env-key"

    def test_remove_api_key(self, temp_config_dir):
        """remove_api_key removes key from config."""
        config.set_api_key("anthropic", "test-key")
        assert config.get_api_key("anthropic") == "test-key"

        result = config.remove_api_key("anthropic")

        assert result is True
        assert config.get_api_key("anthropic") is None

    def test_remove_api_key_returns_false_when_missing(self, temp_config_dir):
        """remove_api_key returns False when key doesn't exist."""
        result = config.remove_api_key("nonexistent")
        assert result is False


class TestListProviders:
    """Tests for listing providers."""

    def test_list_providers_from_config(self, temp_config_dir):
        """list_providers returns providers from config."""
        config.set_api_key("anthropic", "key1")
        config.set_api_key("openai", "key2")

        providers = config.list_providers()

        assert "anthropic" in providers
        assert "openai" in providers

    def test_list_providers_includes_env_vars(self, temp_config_dir):
        """list_providers includes providers from env vars."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            providers = config.list_providers()

        assert "anthropic" in providers

    def test_list_providers_no_duplicates(self, temp_config_dir):
        """list_providers doesn't duplicate providers."""
        config.set_api_key("anthropic", "config-key")

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            providers = config.list_providers()

        # Should only appear once
        assert providers.count("anthropic") == 1


class TestDefaultAgent:
    """Tests for default agent setting."""

    def test_set_default_agent(self, temp_config_dir):
        """set_default_agent stores setting."""
        config.set_default_agent("anthropic")

        agent = config.get_default_agent()
        assert agent == "anthropic"

    def test_get_default_agent_returns_none_initially(self, temp_config_dir):
        """get_default_agent returns None when not set."""
        agent = config.get_default_agent()
        assert agent is None


class TestDefaultModel:
    """Tests for default model per provider."""

    def test_get_default_model_from_defaults(self, temp_config_dir):
        """get_default_model returns default from DEFAULT_CONFIG."""
        # Anthropic has a default model in DEFAULT_CONFIG
        model = config.get_default_model("anthropic")
        assert model is not None
        assert "claude" in model.lower()

    def test_set_default_model(self, temp_config_dir):
        """set_default_model stores model setting."""
        config.set_default_model("anthropic", "claude-opus-4-20250514")

        model = config.get_default_model("anthropic")
        assert model == "claude-opus-4-20250514"

    def test_get_default_model_returns_none_for_unknown(self, temp_config_dir):
        """get_default_model returns None for unknown provider."""
        model = config.get_default_model("unknown_provider")
        assert model is None


class TestApiKeyTesting:
    """Tests for API key validation."""

    def test_test_api_key_no_key_returns_false(self, temp_config_dir):
        """test_api_key returns False when no key found."""
        # Ensure no keys exist
        cfg = config.load_config()
        cfg["api_keys"] = {}
        config.save_config(cfg)

        success, message = config.test_api_key("anthropic")

        assert success is False
        assert "No API key" in message

    def test_test_api_key_unknown_provider(self, temp_config_dir):
        """test_api_key returns error for unknown provider."""
        # Use a fresh provider name that won't have env vars
        config.set_api_key("custom_provider", "some-key")

        success, message = config.test_api_key("custom_provider")

        assert success is False
        assert "not implemented" in message


class TestConfigIntegration:
    """Integration tests for config workflow."""

    def test_full_workflow(self, temp_config_dir):
        """Test complete config workflow."""
        # Initially no keys in config (env vars are cleared by fixture)
        cfg = config.load_config()
        cfg["api_keys"] = {}
        config.save_config(cfg)

        providers = config.list_providers()
        assert providers == [], f"Expected empty, got {providers}"

        # Add keys
        config.set_api_key("anthropic", "sk-ant-123")
        config.set_api_key("openai", "sk-openai-456")

        # Set defaults
        config.set_default_agent("anthropic")
        config.set_default_model("anthropic", "claude-opus-4-20250514")

        # Verify
        assert "anthropic" in config.list_providers()
        assert "openai" in config.list_providers()
        assert config.get_api_key("anthropic") == "sk-ant-123"
        assert config.get_default_agent() == "anthropic"
        assert config.get_default_model("anthropic") == "claude-opus-4-20250514"

        # Remove one
        config.remove_api_key("openai")
        assert "openai" not in config.list_providers()
        assert "anthropic" in config.list_providers()
