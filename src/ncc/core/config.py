"""
Core configuration management for NCC.

Handles loading and managing configuration from various sources including
environment variables, config files, and defaults.
"""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NCCConfig(BaseSettings):
    """Main configuration for Network Command Center."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="NCC_",
        case_sensitive=False,
    )

    # Application settings
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    workers: int = Field(default=64, description="Number of parallel tasks (default=64)")
    username: Optional[str] = Field(default=None, description="Username for device authentication")
    password: Optional[str] = Field(default=None, description="Password for device authentication")

    # Database settings
    database_url: str = Field(
        default="sqlite:///ncc.db",
        description="Database connection URL"
    )
    
    # Supported vendors
    supported_vendors: dict = {
        'ios': 'Cisco IOS',
        'nxos': 'Cisco NX-OS',
        'nxos_ssh': 'Cisco NX-OS (SSH)',
        'iosxr': 'Cisco IOS-XR',
        'iosxr_netconf': 'Cisco IOS-XR (NETCONF)',
        'junos': 'Juniper JunOS',
        'eos': 'Arista EOS',
    }

"""    
    # Inventory settings
    inventory_cache_ttl: int = Field(
        default=300,
        description="Inventory cache TTL in seconds"
    )
    
    # Discovery settings
    discovery_timeout: int = Field(
        default=5,
        description="Network discovery timeout in seconds"
    )
    discovery_threads: int = Field(
        default=10,
        description="Number of threads for discovery"
    )
    
    # Automation settings
    automation_max_workers: int = Field(
        default=20,
        description="Maximum concurrent workers for automation tasks"
    )
    automation_timeout: int = Field(
        default=30,
        description="Default timeout for automation tasks in seconds"
    )
    jinja_template_dir: Optional[Path] = Field(
        default=None,
        description="Directory for Jinja2 templates"
    )
    
    # Web interface settings (when enabled)
    web_host: str = Field(default="127.0.0.1", description="Web server host")
    web_port: int = Field(default=8000, description="Web server port")
    web_secret_key: Optional[str] = Field(
        default=None,
        description="Django secret key"
    )
"""

def get_config() -> NCCConfig:
    """Get the current configuration instance."""
    return NCCConfig()


# Global config instance
config = get_config()
