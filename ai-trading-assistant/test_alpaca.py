"""
Alpaca Connection Test Script
--------------------------
Tests Alpaca credentials and connection.

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

def configure_alpaca():
    """Configure Alpaca credentials"""
    auth = AlpacaAuthenticator()
    
    print("\n=== Alpaca Configuration ===")
    print("Please enter your Alpaca API credentials:")
    api_key = input("API Key: ").strip()
    secret_key = input("Secret Key: ").strip()
    
    print("\nValidating credentials...")
    if auth.validate_credentials(api_key, secret_key):
        auth.save_credentials(api_key, secret_key, paper_trading=True)
        print("✅ Credentials saved successfully!")
        return True
    else:
        print("❌ Invalid credentials")
        return False

def test_connection():
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
            print(f"Buying Power: ${float(account.buying_power):,.2f}")
            print(f"Daytrade Count: {account.daytrade_count}")
            print(f"Pattern Day Trader: {'Yes' if account.pattern_day_trader else 'No'}")
            
            positions = client.get_all_positions()
            print(f"\nOpen Positions: {len(positions)}")
            if positions:
                print("\nCurrent Positions:")
                for pos in positions:
                    print(f"- {pos.symbol}: {pos.qty} shares @ ${float(pos.avg_entry_price):.2f}")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error getting account details: {str(e)}")
            return False
    else:
        print("\n❌ Failed to connect to Alpaca")
        print("Please check your credentials in alpaca_config.json")
        return False

def main():
    """Main entry point"""
    setup_logging()
    
    auth = AlpacaAuthenticator()
    if not auth.is_authenticated():
        print("No valid credentials found.")
        if not configure_alpaca():
            return
    
    print("\nTesting Alpaca Connection...")
    if test_connection():
        print("\n✅ Alpaca connection test completed successfully!")
    else:
        print("\n❌ Alpaca connection test failed!")
        print("Please verify your credentials and try again.")

if __name__ == "__main__":
    main()
