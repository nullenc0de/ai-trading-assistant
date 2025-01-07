"""
Configuration Manager Module
--------------------------
Handles loading, validation, and access to system configuration
with backward compatibility for legacy config files.

Author: AI Trading Assistant
Version: 2.0
Last Updated: 2025-01-07
"""

import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

class ConfigManager:
    def __init__(self, config_path='config/config.json'):
        """Initialize Configuration Manager with consolidated config handling"""
        self.config_path = config_path
        self.config_dir = os.path.dirname(os.path.abspath(config_path))
        self.logger = logging.getLogger(__name__)
        
        # Initialize logging
        self.logger.setLevel(logging.INFO)
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Load configuration
        self.config = self._load_configuration()
        
    def _load_configuration(self) -> Dict[str, Any]:
        """Load and merge configuration from all sources"""
        try:
            # Load main config
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)
            else:
                # Create new config from template
                config = self._create_default_config()
                self._save_config(config)
            
            # Version check
            if config.get('version', '1.0') != '2.0':
                config = self._migrate_legacy_config(config)
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error loading configuration: {str(e)}")
            return self._create_default_config()

    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        return {
            "version": "2.0",
            "last_updated": datetime.now().isoformat(),
            
            "account": {
                "starting_balance": 3000.00,
                "risk_management": {
                    "cash_reserve_percent": 10.0,
                    "position_sizing": {
                        "risk_per_trade_percent": 1.0,
                        "min_position_percent": 3.0,
                        "max_position_percent": 20.0,
                        "preferred_share_increment": 5
                    }
                }
            },
            
            "trading": {
                "filters": {
                    "min_price": 2.00,
                    "max_price": 20.00,
                    "min_volume": 500000,
                    "min_rel_volume": 5.0,
                    "max_spread_percent": 0.02
                },
                "rules": {
                    "entry": {
                        "min_setup_confidence": 75
                    }
                }
            },
            
            "system": {
                "scan_interval": 60,
                "max_symbols": 100,
                "performance_tracking": {
                    "log_dir": "logs/performance"
                }
            }
        }

    def _migrate_legacy_config(self, old_config: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate legacy config to new format"""
        try:
            # Start with default config
            new_config = self._create_default_config()
            
            # Map old keys to new structure
            mappings = {
                'trading_filters': 'trading.filters',
                'risk_management': 'account.risk_management',
                'system_settings': 'system',
                'performance_tracking': 'system.performance_tracking'
            }
            
            for old_key, new_key in mappings.items():
                if old_key in old_config:
                    self._set_nested_value(new_config, new_key, old_config[old_key])
            
            # Load and merge money management if exists
            money_mgmt_path = os.path.join(self.config_dir, 'money_management.json')
            if os.path.exists(money_mgmt_path):
                with open(money_mgmt_path, 'r') as f:
                    money_config = json.load(f)
                    if 'account_management' in money_config:
                        new_config['account'].update(money_config['account_management'])
            
            new_config['version'] = '2.0'
            new_config['last_updated'] = datetime.now().isoformat()
            
            return new_config
            
        except Exception as e:
            self.logger.error(f"Error migrating configuration: {str(e)}")
            return self._create_default_config()

    def _set_nested_value(self, config: Dict[str, Any], key_path: str, value: Any) -> None:
        """Set value in nested dictionary using dot notation path"""
        keys = key_path.split('.')
        current = config
        for key in keys[:-1]:
            current = current.setdefault(key, {})
        current[keys[-1]] = value

    def _save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save configuration with backup"""
        try:
            if config is None:
                config = self.config
                
            # Create backup
            if os.path.exists(self.config_path):
                backup_path = f"{self.config_path}.backup"
                os.replace(self.config_path, backup_path)
            
            # Save new config
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            self.logger.info("Configuration saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error saving configuration: {str(e)}")
            if os.path.exists(f"{self.config_path}.backup"):
                os.replace(f"{self.config_path}.backup", self.config_path)

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation"""
        try:
            value = self.config
            for k in key.split('.'):
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def update(self, updates: Dict[str, Any]) -> bool:
        """Update configuration with validation"""
        try:
            # Create temporary config
            temp_config = self.config.copy()
            
            # Apply updates
            for key, value in updates.items():
                self._set_nested_value(temp_config, key, value)
            
            # Validate
            if self._validate_config(temp_config):
                self.config = temp_config
                self._save_config()
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error updating configuration: {str(e)}")
            return False

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration values"""
        try:
            # Required sections
            required_sections = ['account', 'trading', 'system']
            if not all(section in config for section in required_sections):
                return False
            
            # Account validation
            account = config.get('account', {})
            if account.get('starting_balance', 0) <= 0:
                return False
            
            # Trading validation
            trading = config.get('trading', {})
            filters = trading.get('filters', {})
            if filters.get('min_price', 0) >= filters.get('max_price', float('inf')):
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Configuration validation error: {str(e)}")
            return False

    def get_section(self, section: str) -> Dict[str, Any]:
        """Get configuration section"""
        return self.config.get(section, {})
