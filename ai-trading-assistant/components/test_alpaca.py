"""
Alpaca Connection Test Script
--------------------------
Verifies Alpaca credentials and displays account information.

Author: AI Trading Assistant
Version: 1.0
Last Updated: 2025-01-09
"""

import logging
from components import AlpacaAuthenticator

def setup_logging():
    """Setup basic logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s'
    )

def test_alpaca_connection():
    """Test Alpaca connection and display account information"""
    auth = AlpacaAuthenticator()
    client = auth.create_trading_client()
    
    if client:
        try:
            account = client.get_account()
            print("\n=== Alpaca Connection Test ===")
            print(f"Connection: Success")
            print(f"Account ID: {account.id}")
            print(f"Account Status: {account.status}")
            print(f"Trading Type: {'Paper' if account.paper else 'Live'}")
            print(f"\nAccount Details:")
            print(f"Cash: ${float(account.cash):,.2f}")
            print(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
            print(f"Buying Power:
