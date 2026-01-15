"""Configuration loader."""
import json
import os
from pathlib import Path
from ..models.config import AppConfig


def load_config(config_path: str = None) -> AppConfig:
    """Load configuration from file."""
    if config_path is None:
        # Default config path
        base_dir = Path(__file__).parent.parent.parent
        config_path = base_dir / "config" / "default_config.json"

    if not os.path.exists(config_path):
        # Return default config
        return AppConfig()

    with open(config_path, 'r') as f:
        config_dict = json.load(f)

    return AppConfig(**config_dict)


def save_config(config: AppConfig, config_path: str = None):
    """Save configuration to file."""
    if config_path is None:
        base_dir = Path(__file__).parent.parent.parent
        config_path = base_dir / "config" / "default_config.json"

    with open(config_path, 'w') as f:
        json.dump(config.model_dump(), f, indent=2)
