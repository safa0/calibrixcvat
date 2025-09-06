# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import os
import json
import logging
from pathlib import Path

from django.conf import settings


logger = logging.getLogger(__name__)


@dataclass
class SIFTConfig:
    """Configuration for SIFT algorithm parameters."""
    n_features: int = 0  # 0 means no limit
    n_octave_layers: int = 3
    contrast_threshold: float = 0.04
    edge_threshold: float = 10
    sigma: float = 1.6
    ratio_test_threshold: float = 0.75


@dataclass
class ORBConfig:
    """Configuration for ORB algorithm parameters."""
    n_features: int = 500
    scale_factor: float = 1.2
    n_levels: int = 8
    edge_threshold: int = 31
    first_level: int = 0
    wta_k: int = 2
    patch_size: int = 31
    fast_threshold: int = 20
    cross_check: bool = True
    distance_threshold: Optional[int] = None


@dataclass
class TemplateConfig:
    """Configuration for Template Matching algorithm parameters."""
    method: int = 1  # cv2.TM_CCOEFF_NORMED
    threshold: float = 0.8
    max_matches: int = 100
    min_distance: int = 10
    min_template_size: int = 10


@dataclass
class PipelineSettings:
    """Configuration for the matching pipeline."""
    primary_algorithm: str = "sift"
    fallback_algorithms: list = field(default_factory=lambda: ["orb"])
    confidence_threshold: float = 0.3
    min_matches_threshold: int = 4
    enable_geometric_verification: bool = True
    enable_performance_monitoring: bool = True
    timeout_seconds: int = 30


@dataclass
class RedisSettings:
    """Configuration for Redis/RQ background processing."""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    queue_name: str = "cv_matching"
    low_priority_queue: str = "cv_matching_low"
    job_timeout: int = 300  # 5 minutes
    result_ttl: int = 3600  # 1 hour


@dataclass
class CacheSettings:
    """Configuration for caching."""
    cache_timeout: int = 3600  # 1 hour
    result_retention_days: int = 7
    enable_result_caching: bool = True
    max_cache_size_mb: int = 100


@dataclass
class PerformanceSettings:
    """Configuration for performance monitoring and optimization."""
    enable_benchmarking: bool = True
    benchmark_interval_hours: int = 24
    max_performance_history: int = 1000
    enable_algorithm_recommendation: bool = True
    performance_log_level: str = "INFO"


@dataclass
class CalibrrixMatchingConfig:
    """Main configuration class for Calibrix Matching system."""
    sift: SIFTConfig = field(default_factory=SIFTConfig)
    orb: ORBConfig = field(default_factory=ORBConfig)
    template: TemplateConfig = field(default_factory=TemplateConfig)
    pipeline: PipelineSettings = field(default_factory=PipelineSettings)
    redis: RedisSettings = field(default_factory=RedisSettings)
    cache: CacheSettings = field(default_factory=CacheSettings)
    performance: PerformanceSettings = field(default_factory=PerformanceSettings)
    
    # System settings
    log_level: str = "INFO"
    debug_mode: bool = False
    max_image_size: int = 4096  # Maximum dimension in pixels
    supported_formats: list = field(default_factory=lambda: ['.jpg', '.jpeg', '.png', '.bmp', '.tiff'])


class ConfigManager:
    """
    Configuration manager for the Calibrix Matching system.
    
    Handles loading, validation, and management of configuration parameters
    from various sources including Django settings, environment variables,
    and configuration files.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Optional path to configuration file
        """
        self._config_path = config_path
        self._config: Optional[CalibrrixMatchingConfig] = None
        self._load_configuration()

    def _load_configuration(self) -> None:
        """Load configuration from all available sources."""
        # Start with default configuration
        config_dict = self._get_default_config()
        
        # Override with Django settings
        django_config = self._load_from_django_settings()
        self._deep_update(config_dict, django_config)
        
        # Override with environment variables
        env_config = self._load_from_environment()
        self._deep_update(config_dict, env_config)
        
        # Override with configuration file if provided
        if self._config_path:
            file_config = self._load_from_file(self._config_path)
            self._deep_update(config_dict, file_config)
        
        # Create configuration object
        try:
            self._config = self._create_config_from_dict(config_dict)
            self._validate_configuration()
            logger.info("Configuration loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            # Fallback to default configuration
            self._config = CalibrrixMatchingConfig()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration as dictionary."""
        default_config = CalibrrixMatchingConfig()
        return self._dataclass_to_dict(default_config)

    def _load_from_django_settings(self) -> Dict[str, Any]:
        """Load configuration from Django settings."""
        config = {}
        
        # Define mapping from Django settings to config structure
        setting_mappings = {
            'CALIBRIX_MATCHING_LOG_LEVEL': 'log_level',
            'CALIBRIX_MATCHING_DEBUG': 'debug_mode',
            'CALIBRIX_MATCHING_MAX_IMAGE_SIZE': 'max_image_size',
            'CALIBRIX_MATCHING_CACHE_TIMEOUT': 'cache.cache_timeout',
            'CALIBRIX_MATCHING_RESULT_RETENTION': 'cache.result_retention_days',
            'CALIBRIX_MATCHING_JOB_TIMEOUT': 'redis.job_timeout',
            'CALIBRIX_MATCHING_QUEUE_NAME': 'redis.queue_name',
            'CALIBRIX_MATCHING_PRIMARY_ALGORITHM': 'pipeline.primary_algorithm',
            'CALIBRIX_MATCHING_CONFIDENCE_THRESHOLD': 'pipeline.confidence_threshold',
            'REDIS_HOST': 'redis.host',
            'REDIS_PORT': 'redis.port',
            'REDIS_DB': 'redis.db',
            'REDIS_PASSWORD': 'redis.password',
        }
        
        for setting_name, config_path in setting_mappings.items():
            if hasattr(settings, setting_name):
                value = getattr(settings, setting_name)
                self._set_nested_value(config, config_path, value)
        
        # Load complex settings
        if hasattr(settings, 'CALIBRIX_MATCHING_CONFIG'):
            custom_config = getattr(settings, 'CALIBRIX_MATCHING_CONFIG')
            if isinstance(custom_config, dict):
                self._deep_update(config, custom_config)
        
        return config

    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        
        # Define environment variable mappings
        env_mappings = {
            'CALIBRIX_MATCHING_LOG_LEVEL': 'log_level',
            'CALIBRIX_MATCHING_DEBUG': ('debug_mode', bool),
            'CALIBRIX_MATCHING_MAX_IMAGE_SIZE': ('max_image_size', int),
            'CALIBRIX_MATCHING_CACHE_TIMEOUT': ('cache.cache_timeout', int),
            'CALIBRIX_MATCHING_JOB_TIMEOUT': ('redis.job_timeout', int),
            'CALIBRIX_MATCHING_PRIMARY_ALGORITHM': 'pipeline.primary_algorithm',
            'CALIBRIX_MATCHING_CONFIDENCE_THRESHOLD': ('pipeline.confidence_threshold', float),
            'CALIBRIX_REDIS_HOST': 'redis.host',
            'CALIBRIX_REDIS_PORT': ('redis.port', int),
            'CALIBRIX_REDIS_DB': ('redis.db', int),
            'CALIBRIX_REDIS_PASSWORD': 'redis.password',
            'CALIBRIX_SIFT_N_FEATURES': ('sift.n_features', int),
            'CALIBRIX_SIFT_CONTRAST_THRESHOLD': ('sift.contrast_threshold', float),
            'CALIBRIX_ORB_N_FEATURES': ('orb.n_features', int),
            'CALIBRIX_ORB_SCALE_FACTOR': ('orb.scale_factor', float),
            'CALIBRIX_TEMPLATE_THRESHOLD': ('template.threshold', float),
        }
        
        for env_var, config_info in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                if isinstance(config_info, tuple):
                    config_path, value_type = config_info
                    try:
                        if value_type == bool:
                            value = env_value.lower() in ('true', '1', 'yes', 'on')
                        else:
                            value = value_type(env_value)
                        self._set_nested_value(config, config_path, value)
                    except ValueError:
                        logger.warning(f"Invalid value for {env_var}: {env_value}")
                else:
                    self._set_nested_value(config, config_info, env_value)
        
        return config

    def _load_from_file(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            path = Path(config_path)
            if path.exists():
                with open(path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load configuration from {config_path}: {str(e)}")
        
        return {}

    def _create_config_from_dict(self, config_dict: Dict[str, Any]) -> CalibrrixMatchingConfig:
        """Create configuration object from dictionary."""
        # Extract nested configurations
        sift_config = SIFTConfig(**config_dict.get('sift', {}))
        orb_config = ORBConfig(**config_dict.get('orb', {}))
        template_config = TemplateConfig(**config_dict.get('template', {}))
        pipeline_config = PipelineSettings(**config_dict.get('pipeline', {}))
        redis_config = RedisSettings(**config_dict.get('redis', {}))
        cache_config = CacheSettings(**config_dict.get('cache', {}))
        performance_config = PerformanceSettings(**config_dict.get('performance', {}))
        
        # Create main configuration
        main_config = {k: v for k, v in config_dict.items() 
                      if k not in ['sift', 'orb', 'template', 'pipeline', 'redis', 'cache', 'performance']}
        
        return CalibrrixMatchingConfig(
            sift=sift_config,
            orb=orb_config,
            template=template_config,
            pipeline=pipeline_config,
            redis=redis_config,
            cache=cache_config,
            performance=performance_config,
            **main_config
        )

    def _validate_configuration(self) -> None:
        """Validate configuration values."""
        config = self._config
        
        # Validate pipeline settings
        if config.pipeline.confidence_threshold < 0 or config.pipeline.confidence_threshold > 1:
            raise ValueError("confidence_threshold must be between 0 and 1")
        
        if config.pipeline.min_matches_threshold < 0:
            raise ValueError("min_matches_threshold must be non-negative")
        
        # Validate algorithm-specific settings
        if config.sift.n_features < 0:
            raise ValueError("SIFT n_features must be non-negative")
        
        if config.orb.n_features <= 0:
            raise ValueError("ORB n_features must be positive")
        
        if config.orb.scale_factor <= 1.0:
            raise ValueError("ORB scale_factor must be greater than 1.0")
        
        # Validate template matching settings
        if config.template.threshold < 0 or config.template.threshold > 1:
            raise ValueError("Template threshold must be between 0 and 1")
        
        # Validate Redis settings
        if config.redis.port <= 0 or config.redis.port > 65535:
            raise ValueError("Redis port must be between 1 and 65535")
        
        # Validate cache settings
        if config.cache.cache_timeout <= 0:
            raise ValueError("Cache timeout must be positive")
        
        if config.cache.result_retention_days <= 0:
            raise ValueError("Result retention days must be positive")

    def _deep_update(self, base_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> None:
        """Deep update base_dict with update_dict."""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def _set_nested_value(self, config: Dict[str, Any], path: str, value: Any) -> None:
        """Set nested value in configuration dictionary using dot notation."""
        keys = path.split('.')
        current = config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value

    def _dataclass_to_dict(self, obj) -> Dict[str, Any]:
        """Convert dataclass to dictionary recursively."""
        if hasattr(obj, '__dataclass_fields__'):
            result = {}
            for field_name, field_def in obj.__dataclass_fields__.items():
                value = getattr(obj, field_name)
                if hasattr(value, '__dataclass_fields__'):
                    result[field_name] = self._dataclass_to_dict(value)
                else:
                    result[field_name] = value
            return result
        else:
            return obj

    @property
    def config(self) -> CalibrrixMatchingConfig:
        """Get the current configuration."""
        return self._config

    def get_algorithm_config(self, algorithm: str) -> Dict[str, Any]:
        """
        Get configuration for specific algorithm.
        
        Args:
            algorithm: Algorithm name ('sift', 'orb', 'template')
            
        Returns:
            Algorithm-specific configuration dictionary
        """
        algorithm = algorithm.lower()
        if algorithm == 'sift':
            return self._dataclass_to_dict(self._config.sift)
        elif algorithm == 'orb':
            return self._dataclass_to_dict(self._config.orb)
        elif algorithm == 'template':
            return self._dataclass_to_dict(self._config.template)
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

    def update_configuration(self, updates: Dict[str, Any]) -> None:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of configuration updates
        """
        config_dict = self._dataclass_to_dict(self._config)
        self._deep_update(config_dict, updates)
        
        try:
            self._config = self._create_config_from_dict(config_dict)
            self._validate_configuration()
            logger.info("Configuration updated successfully")
        except Exception as e:
            logger.error(f"Failed to update configuration: {str(e)}")
            raise

    def save_configuration(self, output_path: str) -> None:
        """
        Save current configuration to file.
        
        Args:
            output_path: Path to save configuration file
        """
        try:
            config_dict = self._dataclass_to_dict(self._config)
            with open(output_path, 'w') as f:
                json.dump(config_dict, f, indent=2)
            logger.info(f"Configuration saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            raise

    def get_summary(self) -> Dict[str, Any]:
        """Get configuration summary for display."""
        return {
            'primary_algorithm': self._config.pipeline.primary_algorithm,
            'fallback_algorithms': self._config.pipeline.fallback_algorithms,
            'confidence_threshold': self._config.pipeline.confidence_threshold,
            'enable_geometric_verification': self._config.pipeline.enable_geometric_verification,
            'sift_features': self._config.sift.n_features,
            'orb_features': self._config.orb.n_features,
            'template_threshold': self._config.template.threshold,
            'cache_timeout': self._config.cache.cache_timeout,
            'job_timeout': self._config.redis.job_timeout,
            'debug_mode': self._config.debug_mode
        }


# Global configuration manager instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> CalibrrixMatchingConfig:
    """Get the global configuration instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.config


def get_config_manager() -> ConfigManager:
    """Get the global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def reload_config(config_path: Optional[str] = None) -> None:
    """Reload configuration from all sources."""
    global _config_manager
    _config_manager = ConfigManager(config_path)