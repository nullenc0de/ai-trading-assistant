# components/config_manager.py
import os
import json
import logging

class ConfigManager:
    def __init__(self, config_path='config.json'):
        """
        Initialize Configuration Manager
        
        Args:
            config_path (str): Path to configuration file
        """
        self.config_path = config_path
        self.default_config = {
            # Trading Filters
            'min_price': 2.00,
            'max_price': 20.00,
            'min_volume': 500000,
            'min_rel_volume': 5.0,
            
            # System Settings
            'scan_interval': 60,  # seconds between scans
            'max_symbols': 100,   # max symbols to analyze per scan
            
            # Risk Management
            'max_position_size': 1000,  # max shares per trade
            'risk_per_trade': 0.02,     # 2% of account per trade
            
            # LLM Configuration
            'llm_model': 'llama3:latest',
            'llm_temperature': 0.7,
            'llm_max_tokens': 300,
            
            # Performance Tracking
            'performance_log_dir': 'performance_logs'
        }
        
        # Load or create config
        self._load_or_create_config()

    def _load_or_create_config(self):
        """
        Load existing configuration or create default
        """
        try:
            # Ensure config directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            # Try to load existing config
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    loaded_config = json.load(f)
                    # Merge loaded config with defaults (loaded takes precedence)
                    self.config = {**self.default_config, **loaded_config}
            else:
                # Create default config file
                self.config = self.default_config.copy()
                self._save_config()
        
        except Exception as e:
            logging.error(f"Error loading configuration: {str(e)}")
            # Fall back to default config
            self.config = self.default_config.copy()

    def _save_config(self):
        """
        Save current configuration to file
        """
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving configuration: {str(e)}")

    def get(self, key, default=None):
        """
        Get configuration value
        
        Args:
            key (str): Configuration key
            default: Default value if key not found
        
        Returns:
            Value for the given key
        """
        return self.config.get(key, default)

    def update(self, updates):
        """
        Update configuration
        
        Args:
            updates (dict): Configuration updates
        """
        try:
            # Update config
            self.config.update(updates)
            
            # Save updated config
            self._save_config()
            
            logging.info("Configuration updated successfully")
        
        except Exception as e:
            logging.error(f"Error updating configuration: {str(e)}")