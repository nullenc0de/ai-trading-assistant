"""
Alpaca Connection Test Utility
---------------------------
Tests Alpaca credentials and displays account information.

Author: AI Trading Assistant
Version: 1.1
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
        if auth.save_credentials(api_key, secret_key, paper_trading=True):
            print("✅ Credentials saved successfully!")
            return True
    
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
            print(f"Connection: Success ✅")
            print(f"Account ID: {account.id}")
            print(f"Account Status: {account.status}")
            
            print(f"\nAccount Details:")
            print(f"Cash Balance: ${float(account.cash):,.2f}")
            print(f"Portfolio Value: ${float(account.portfolio_value):,.2f}")
            print(f"Buying Power: ${float(account.buying_power):,.2f}")
            print(f"Day Trade Count: {account.daytrade_count}")
            print(f"Pattern Day Trader: {account.pattern_day_trader}")
            
            # Get current positions
            try:
                positions = client.get_all_positions()
                print(f"\nOpen Positions: {len(positions)}")
                if positions:
                    print("\nCurrent Positions:")
                    for pos in positions:
                        print(f"- {pos.symbol}: {float(pos.qty)} shares @ ${float(pos.avg_entry_price):.2f}")
            except Exception:
                print(f"Note: No positions found")
            
            # Account restrictions
            if hasattr(account, 'trading_blocked') and account.trading_blocked:
                print("\nTrading Restrictions: ⚠️")
                if hasattr(account, 'trading_blocked_reason'):
                    print(f"Reason: {account.trading_blocked_reason}")
            else:
                print("\nTrading Status: Ready ✅")
            
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
        print("\n✅ All systems operational!")
        print("Your Alpaca paper trading account is ready to use.")
    else:
        print("\n❌ Connection test failed!")
        print("Please verify your credentials and try again.")

if __name__ == "__main__":
    main()
