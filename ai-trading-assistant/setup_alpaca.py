"""
Alpaca Setup Script
------------------
Sets up Alpaca credentials securely.
"""

import os
from components import AlpacaAuthenticator

def setup_alpaca():
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

if __name__ == "__main__":
    setup_alpaca()
