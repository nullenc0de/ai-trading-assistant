"""
Alpaca Setup Utility
------------------
Sets up and configures Alpaca paper trading credentials.

Author: AI Trading Assistant
Version: 1.1
Last Updated: 2025-01-09
"""

import os
import logging
from components import AlpacaAuthenticator

def setup_logging():
    """Setup basic logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s'
    )

def setup_alpaca():
    """Setup Alpaca credentials interactively"""
    print("\n=== Alpaca Trading Setup ===")
    print("Please enter your Alpaca API credentials:")
    
    api_key = input("API Key: ").strip()
    secret_key = input("Secret Key: ").strip()
    
    # Initialize authenticator
    auth = AlpacaAuthenticator()
    
    # Validate credentials
    print("\nValidating credentials...")
    if auth.validate_credentials(api_key, secret_key):
        # Save credentials (always use paper trading for safety)
        if auth.save_credentials(api_key, secret_key, paper_trading=True):
            print("\n✅ Credentials validated and saved successfully!")
            print("Paper trading mode is enabled for safety.")
            return True
        else:
            print("\n❌ Error saving credentials.")
            return False
    else:
        print("\n❌ Invalid credentials. Please check and try again.")
        return False

def main():
    """Main entry point"""
    setup_logging()
    setup_alpaca()

if __name__ == "__main__":
    main()
