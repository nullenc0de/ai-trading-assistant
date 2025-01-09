"""
Alpaca Authentication Module
-------------------------
Handles Alpaca API authentication, credential management, and client creation.

Author: AI Trading Assistant
Version: 2.2
Last Updated: 2025-01-09
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from alpaca.trading.client import TradingClient
from alpaca.data.historical.stock import StockHistoricalDataClient

class AlpacaAuthenticator:
    def __init__(self, config_path='alpaca_config.json'):
        """Initialize Alpaca Authentication Manager"""
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Ensure config directory exists
        os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)

    def save_credentials(self, api_key: str, secret_key: str, paper_trading: bool = True) -> bool:
        """Save Alpaca credentials securely"""
        try:
            # Create full config structure
            config = {
                "api_key": api_key,
                "secret_key": secret_key,
                "paper_trading": paper_trading,
                "settings": {
                    "max_retries": 3,
                    "timeout": 30,
                    "debug_mode": False
                }
            }
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
            
            # Save config with pretty formatting
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            # Set secure permissions
            os.chmod(self.config_path, 0o600)
            
            self.logger.info("Alpaca credentials saved successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving Alpaca credentials: {str(e)}")
            return False

    def load_credentials(self) -> Optional[Dict[str, Any]]:
        """Load Alpaca credentials"""
        try:
            if not os.path.exists(self.config_path):
                self.logger.info("No credentials file found")
                return None
            
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Validate required fields
            if not config.get('api_key') or not config.get('secret_key'):
                self.logger.warning("Incomplete credentials in config")
                return None
                
            return config
            
        except Exception as e:
            self.logger.error(f"Error loading Alpaca credentials: {str(e)}")
            return None

    def create_trading_client(self) -> Optional[TradingClient]:
        """Create Alpaca trading client"""
        try:
            creds = self.load_credentials()
            if not creds:
                self.logger.info("No credentials available to create trading client")
                return None
                
            self.logger.info("Creating Alpaca trading client")
            client = TradingClient(
                api_key=creds['api_key'],
                secret_key=creds['secret_key'],
                paper=creds.get('paper_trading', True)  # Default to paper trading
            )
            
            # Test connection and log account info
            account = client.get_account()
            self.logger.info(f"Connected to Alpaca. Account Status: {account.status}")
            self.logger.info(f"Account Cash: ${float(account.cash):,.2f}")
            self.logger.info(f"Account Equity: ${float(account.equity):,.2f}")
            
            return client
            
        except Exception as e:
            self.logger.error(f"Error creating Alpaca trading client: {str(e)}")
            return None

    def create_data_client(self) -> Optional[StockHistoricalDataClient]:
        """Create Alpaca data client"""
        try:
            creds = self.load_credentials()
            if not creds:
                return None
                
            return StockHistoricalDataClient(
                api_key=creds['api_key'],
                secret_key=creds['secret_key']
            )
            
        except Exception as e:
            self.logger.error(f"Error creating Alpaca data client: {str(e)}")
            return None

    def validate_credentials(self, api_key: str, secret_key: str) -> bool:
        """Validate Alpaca credentials by attempting to create a client"""
        try:
            client = TradingClient(api_key=api_key, secret_key=secret_key, paper=True)
            account = client.get_account()
            self.logger.info(f"Credentials validated successfully. Account ID: {account.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Invalid Alpaca credentials: {str(e)}")
            return False

    def is_authenticated(self) -> bool:
        """Check if credentials are valid and authenticated"""
        try:
            client = self.create_trading_client()
            if not client:
                return False
                
            client.get_account()
            return True
            
        except Exception:
            return False

    def remove_credentials(self) -> bool:
        """Remove saved credentials"""
        try:
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
                self.logger.info("Credentials removed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error removing credentials: {str(e)}")
            return False
