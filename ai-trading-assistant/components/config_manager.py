# components/config_manager.py
import os
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime

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
            'min_price': 2.00,
            'max_price': 20.00,
            'min_volume': 500000,
            'min_rel_volume': 5.0,
            
            # System Settings
            'scan_interval': 60,
            'max_symbols': 100,
            'parallel_analysis': True,
            'analysis_timeout': 30,
            
            # Risk Management
            'max_position_size': 1000,
            'risk_per_trade': 0.02,
            'max_daily_trades': 10,
            'max_daily_loss': 0.03,
            'profit_taking_intervals': [0.5, 0.75, 1.0],
            
            # Trading Rules
            'min_risk_reward': 2.0,
            'min_setup_confidence': 75,
            'max_spread_percent': 0.02,
            
            # LLM Configuration
            'llm_model': 'llama3:latest',
            'llm_temperature': 0.7,
            'llm_max_tokens': 300,
            'llm_retry_attempts': 3,
            
            # Performance Tracking
            'performance_log_dir': 'performance_logs',
            'metrics_update_interval': 300
        }
        
        # Initialize configuration
        self._load_or_create_config()
        
        # Validate configuration
        self._validate_config()

    def _load_or_create_config(self) -> None:
        """Load existing configuration or create default with enhanced error handling"""
        try:
            # Ensure config directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    
                    # Version check and update
                    if self._needs_version_update(loaded_config):
                        loaded_config = self._update_config_version(loaded_config)
                    
                    # Merge with defaults (loaded config takes precedence)
                    self.config = {**self.default_config, **loaded_config}
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
                'min_price': lambda x: 0 < x < 1000,
                'max_price': lambda x: x > self.config['min_price'],
                'min_volume': lambda x: x > 0,
                'risk_per_trade': lambda x: 0 < x < 0.1,
                'min_risk_reward': lambda x: x > 1,
            }
            
            # Check each rule
            for key, validator in rules.items():
                value = self.config.get(key)
                if value is not None:
                    if not validator(value):
                        logging.warning(f"Invalid config value for {key}: {value}")
                        self.config[key] = self.default_config[key]
            
            # Interdependent validations
            if self.config['max_daily_loss'] <= self.config['risk_per_trade']:
                logging.warning("max_daily_loss must be greater than risk_per_trade")
                self.config['max_daily_loss'] = self.default_config['max_daily_loss']
            
        except Exception as e:
            logging.error(f"Configuration validation error: {str(e)}")

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
                'parallel_analysis': True,
                'analysis_timeout': 30,
                'profit_taking_intervals': [0.5, 0.75, 1.0],
                'metrics_update_interval': 300
            })
        
        updated_config['config_version'] = self.default_config['config_version']
        updated_config['last_updated'] = datetime.now().isoformat()
        
        return updated_config

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
        Get configuration value with type checking
        
        Args:
            key (str): Configuration key
            default: Default value if key not found
            
        Returns:
            Value for the given key
        """
        value = self.config.get(key, default)
        
        # Type checking
        if default is not None and value is not None:
            if not isinstance(value, type(default)):
                logging.warning(f"Type mismatch for {key}. Expected {type(default)}, got {type(value)}")
                return default
        
        return value

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
            section (str): Section name (e.g., 'risk_management')
            
        Returns:
            dict: Configuration section
        """
        return {
            k: v for k, v in self.config.items()
            if k.startswith(f"{section}_")
        }

    def reset_to_default(self) -> None:
        """Reset configuration to default values"""
        self.config = self.default_config.copy()
        self._save_config()
        logging.info("Configuration reset to defaults")
