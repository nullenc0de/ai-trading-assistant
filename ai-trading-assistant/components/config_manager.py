# components/config_manager.py
import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

class ConfigManager:
    def __init__(self, config_path='config.json'):
        """
        Initialize Configuration Manager with enhanced validation
        
        Args:
            config_path (str): Path to configuration file
        """
        self.config_path = config_path
        self.default_config = {
            # Version tracking
            'config_version': '2.0',
            'last_updated': datetime.now().isoformat(),
            
            # Trading Filters
            'trading_filters': {
                'min_price': 2.00,
                'max_price': 20.00,
                'min_volume': 500000,
                'min_rel_volume': 5.0,
                'max_spread_percent': 0.02
            },
            
            # System Settings
            'system_settings': {
                'scan_interval': 60,
                'max_symbols': 100,
                'parallel_analysis': True,
                'analysis_timeout': 30
            },
            
            # Risk Management
            'risk_management': {
                'max_position_size': 1000,
                'risk_per_trade': 0.02,
                'max_daily_trades': 10,
                'max_daily_loss': 0.03,
                'profit_taking_intervals': [0.5, 0.75, 1.0]
            },
            
            # Trading Rules
            'trading_rules': {
                'min_risk_reward': 2.0,
                'min_setup_confidence': 75,
                'max_spread_percent': 0.02
            },
            
            # LLM Configuration
            'llm_configuration': {
                'model': 'llama3:latest',
                'temperature': 0.7,
                'max_tokens': 300,
                'retry_attempts': 3
            },
            
            # Performance Tracking
            'performance_tracking': {
                'log_dir': 'performance_logs',
                'metrics_update_interval': 300
            }
        }
        
        # Initialize logging
        logging.getLogger(__name__).setLevel(logging.INFO)
        
        # Ensure config directory exists
        config_dir = os.path.dirname(os.path.abspath(self.config_path))
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        
        # Load or create config
        self._load_or_create_config()
        
        # Validate configuration
        self._validate_config()

    def _load_or_create_config(self) -> None:
        """Load existing configuration or create default with enhanced error handling"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    
                    # Version check and update
                    if self._needs_version_update(loaded_config):
                        loaded_config = self._update_config_version(loaded_config)
                    
                    # Merge with defaults (loaded config takes precedence)
                    self.config = self._merge_configs(self.default_config, loaded_config)
            else:
                self.config = self.default_config.copy()
                self._save_config()
            
            logging.info("Configuration loaded successfully")
            
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in config file: {str(e)}")
            self.config = self.default_config.copy()
            self._save_config()
            
        except Exception as e:
            logging.error(f"Error loading configuration: {str(e)}")
            self.config = self.default_config.copy()

    def _validate_config(self) -> None:
        """Validate configuration values"""
        try:
            # Validation rules
            rules = {
                'trading_filters.min_price': lambda x: 0 < x < 1000,
                'trading_filters.max_price': lambda x: x > self.get('trading_filters.min_price'),
                'trading_filters.min_volume': lambda x: x > 0,
                'risk_management.risk_per_trade': lambda x: 0 < x < 0.1,
                'trading_rules.min_risk_reward': lambda x: x > 1,
            }
            
            # Check each rule
            for path, validator in rules.items():
                value = self.get(path)
                if value is not None:
                    if not validator(value):
                        logging.warning(f"Invalid config value for {path}: {value}")
                        self._set_default_value(path)
            
            # Interdependent validations
            if (self.get('risk_management.max_daily_loss') <= 
                self.get('risk_management.risk_per_trade')):
                logging.warning("max_daily_loss must be greater than risk_per_trade")
                self._set_default_value('risk_management.max_daily_loss')
            
        except Exception as e:
            logging.error(f"Configuration validation error: {str(e)}")

    def _set_default_value(self, path: str) -> None:
        """Set default value for a given config path"""
        try:
            keys = path.split('.')
            value = self.default_config
            for key in keys:
                value = value[key]
            
            current = self.config
            for key in keys[:-1]:
                current = current.setdefault(key, {})
            current[keys[-1]] = value
            
        except Exception as e:
            logging.error(f"Error setting default value for {path}: {str(e)}")

    def _needs_version_update(self, config: Dict[str, Any]) -> bool:
        """
        Check if configuration needs version update
        
        Args:
            config (dict): Current configuration
            
        Returns:
            bool: True if update needed
        """
        current_version = config.get('config_version', '1.0')
        return current_version != self.default_config['config_version']

    def _update_config_version(self, old_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update configuration to new version
        
        Args:
            old_config (dict): Old configuration
            
        Returns:
            dict: Updated configuration
        """
        updated_config = old_config.copy()
        
        # Version-specific updates
        if old_config.get('config_version') == '1.0':
            # Add new fields from 2.0
            updated_config.update({
                'trading_filters': {
                    'min_price': old_config.get('min_price', self.default_config['trading_filters']['min_price']),
                    'max_price': old_config.get('max_price', self.default_config['trading_filters']['max_price']),
                    'min_volume': old_config.get('min_volume', self.default_config['trading_filters']['min_volume']),
                    'min_rel_volume': old_config.get('min_rel_volume', self.default_config['trading_filters']['min_rel_volume']),
                    'max_spread_percent': self.default_config['trading_filters']['max_spread_percent']
                }
            })
        
        updated_config['config_version'] = self.default_config['config_version']
        updated_config['last_updated'] = datetime.now().isoformat()
        
        return updated_config

    def _merge_configs(self, default: Dict[str, Any], loaded: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively merge loaded config with defaults
        
        Args:
            default (dict): Default configuration
            loaded (dict): Loaded configuration
            
        Returns:
            dict: Merged configuration
        """
        merged = default.copy()
        
        for key, value in loaded.items():
            if (
                key in merged and 
                isinstance(merged[key], dict) and 
                isinstance(value, dict)
            ):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
                
        return merged

    def _save_config(self) -> None:
        """Save current configuration with backup"""
        try:
            # Create backup of existing config
            if os.path.exists(self.config_path):
                backup_path = f"{self.config_path}.backup"
                os.replace(self.config_path, backup_path)
            
            # Save new config
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            
            logging.info("Configuration saved successfully")
            
        except Exception as e:
            logging.error(f"Error saving configuration: {str(e)}")
            if os.path.exists(f"{self.config_path}.backup"):
                os.replace(f"{self.config_path}.backup", self.config_path)

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with nested key support
        
        Args:
            key (str): Configuration key (dot notation supported)
            default: Default value if key not found
            
        Returns:
            Value for the given key
        """
        try:
            value = self.config
            for k in key.split('.'):
                value = value[k]
            
            # Type checking
            if default is not None and not isinstance(value, type(default)):
                logging.warning(f"Type mismatch for {key}. Expected {type(default)}, got {type(value)}")
                return default
            
            return value
            
        except KeyError:
            return default
        
        except Exception as e:
            logging.error(f"Error getting config value for {key}: {str(e)}")
            return default

    def update(self, updates: Dict[str, Any]) -> bool:
        """
        Update configuration with validation
        
        Args:
            updates (dict): Configuration updates
            
        Returns:
            bool: True if update successful
        """
        try:
            # Create temporary config for validation
            temp_config = self.config.copy()
            temp_config.update(updates)
            
            # Store old config for rollback
            old_config = self.config.copy()
            
            # Update config
            self.config = temp_config
            
            # Validate new config
            self._validate_config()
            
            # Save if validation passes
            self._save_config()
            
            logging.info("Configuration updated successfully")
            return True
            
        except Exception as e:
            logging.error(f"Error updating configuration: {str(e)}")
            self.config = old_config
            return False

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get configuration section
        
        Args:
            section (str): Section name (e.g., 'trading_filters')
            
        Returns:
            dict: Configuration section
        """
        return self.config.get(section, {})

    def reset_to_default(self) -> None:
        """Reset configuration to default values"""
        self.config = self.default_config.copy()
        self._save_config()
        logging.info("Configuration reset to defaults")
