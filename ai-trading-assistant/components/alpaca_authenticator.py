import os
import json
import logging
from typing import Dict, Any, Optional
from alpaca.trading.client import TradingClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass

class AlpacaAuthenticator:
    def __init__(self, config_path='alpaca_config.json'):
        """Initialize Alpaca Authentication Manager"""
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
        
        # Initialize logging
        self.logger.setLevel(logging.INFO)
        
        # Ensure config directory exists
        os.makedirs(os.path.dirname(os.path.abspath(config_path)), exist_ok=True)
        
        # Environment variables take precedence
        self.api_key = os.getenv("ALPACA_API_KEY_ID")
        self.secret_key = os.getenv("ALPACA_API_SECRET_KEY")
        
        if self.api_key and self.secret_key:
            self.save_credentials(self.api_key, self.secret_key)

    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration"""
        return {
            "api_key": "",
            "secret_key": "",
            "paper_trading": True,  # Default to paper trading for safety
            "settings": {
                "max_retries": 3,
                "timeout": 30,
                "debug_mode": False
            }
        }

    def save_credentials(self, api_key: str, secret_key: str, paper_trading: bool = True) -> bool:
        """Save Alpaca credentials securely"""
        try:
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
            if self.api_key and self.secret_key:
                return {
                    "api_key": self.api_key,
                    "secret_key": self.secret_key,
                    "paper_trading": True
                }
                
            if not os.path.exists(self.config_path):
                return None
            
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            return config
            
        except Exception as e:
            self.logger.error(f"Error loading Alpaca credentials: {str(e)}")
            return None

    def create_trading_client(self) -> Optional[TradingClient]:
        """Create Alpaca trading client"""
        try:
            creds = self.load_credentials()
            if not creds:
                return None
                
            client = TradingClient(
                api_key=creds['api_key'],
                secret_key=creds['secret_key'],
                paper=creds.get('paper_trading', True)
            )
            
            # Test connection
            client.get_account()
            
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

    def remove_credentials(self) -> bool:
        """Remove saved credentials"""
        try:
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
            return True
        except Exception as e:
            self.logger.error(f"Error removing credentials: {str(e)}")
            return False

    def validate_credentials(self, api_key: str, secret_key: str) -> bool:
        """Validate Alpaca credentials by attempting to create a client"""
        try:
            client = TradingClient(api_key=api_key, secret_key=secret_key, paper=True)
            # Test API connection by getting account info
            client.get_account()
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
            # Test connection
            client.get_account()
            return True
        except Exception:
            return False

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """Get account information"""
        try:
            client = self.create_trading_client()
            if not client:
                return None
                
            account = client.get_account()
            return {
                'account_number': account.account_number,
                'buying_power': float(account.buying_power),
                'cash': float(account.cash),
                'equity': float(account.equity),
                'status': account.status
            }
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {str(e)}")
            return None
