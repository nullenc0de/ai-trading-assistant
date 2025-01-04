import asyncio
import logging
import json
import os
import sys

# Import components
from components.config_manager import ConfigManager
from components.stock_scanner import StockScanner
from components.stock_analyzer import StockAnalyzer
from components.trading_analyst import TradingAnalyst
from components.market_monitor import MarketMonitor
from components.output_formatter import OutputFormatter
from components.performance_tracker import PerformanceTracker
from components.robinhood_authenticator import RobinhoodAuthenticator

class TradingSystem:
    def __init__(self):
        # Setup logging
        self._setup_logging()
        
        # Load configuration
        self.config_manager = ConfigManager('config.json')
        
        # Initialize Robinhood authentication
        self.robinhood_auth = RobinhoodAuthenticator()
        
        # Check for Robinhood credentials
        self._check_robinhood_credentials()
        
        # Initialize components
        self.scanner = StockScanner()
        self.market_monitor = MarketMonitor()
        self.output_formatter = OutputFormatter()
        self.performance_tracker = PerformanceTracker()
        
        # Initialize analyzer and trader with config
        self.analyzer = StockAnalyzer(self.config_manager)
        self.trading_analyst = TradingAnalyst()

    def _check_robinhood_credentials(self):
        """
        Check if Robinhood credentials are saved and prompt if needed
        """
        credentials = self.robinhood_auth.load_credentials()
        
        if not credentials:
            print("\n🤖 Robinhood Integration")
            print("No Robinhood credentials found. Would you like to add them?")
            choice = input("(Y/N): ").strip().lower()
            
            if choice == 'y':
                self.robinhood_auth.save_credentials()
            else:
                print("Skipping Robinhood integration. Trading will be analysis-only.")

    def _setup_logging(self):
        """Configure logging for the application"""
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/trading_system.log'),
                logging.StreamHandler()
            ]
        )

    async def analyze_symbol(self, symbol):
        """
        Analyze a single stock symbol
        
        Args:
            symbol (str): Stock ticker symbol
        """
        try:
            # Analyze stock data
            stock_data = self.analyzer.analyze_stock(symbol)
            
            if stock_data:
                # Get trading setup from AI
                trading_setup = await self.trading_analyst.analyze_setup(stock_data)
                
                # If a valid setup is found
                if trading_setup and 'NO SETUP' not in trading_setup:
                    # Format and display setup
                    formatted_setup = self.output_formatter.format_trading_setup(trading_setup)
                    print(formatted_setup)
                    
                    # Log performance
                    self.performance_tracker.log_trade(
                        symbol=symbol,
                        entry_price=stock_data.get('current_price', 0),
                        confidence=float(trading_setup.split('Confidence: ')[1].split('%')[0]) if 'Confidence:' in trading_setup else 0,
                        setup_details=trading_setup
                    )
                    
                    # Optional: Execute trade if Robinhood credentials are available
                    self._potentially_execute_trade(symbol, trading_setup)
        
        except Exception as e:
            logging.error(f"Error analyzing {symbol}: {str(e)}")

    def _potentially_execute_trade(self, symbol, trading_setup):
        """
        Potentially execute a trade based on setup
        
        Args:
            symbol (str): Stock symbol
            trading_setup (str): Trading setup details
        """
        # Check for Robinhood credentials
        credentials = self.robinhood_auth.load_credentials()
        if not credentials:
            return

        # Extract confidence and other details
        try:
            confidence = float(trading_setup.split('Confidence: ')[1].split('%')[0])
            
            # Only execute high-confidence trades
            if confidence > 80:
                print(f"\n🚀 High-Confidence Trade Detected for {symbol}")
                print("Preparing to execute trade...")
                
                # TODO: Add actual Robinhood trade execution logic
                # This would typically involve using robin-stocks library
                # Example (pseudo-code):
                # robinhood_client.place_buy_order(symbol, quantity)
                
                logging.info(f"Trade setup for {symbol} with {confidence}% confidence")
        
        except Exception as e:
            logging.error(f"Error processing trade execution: {e}")

    async def run(self):
        """Main trading system loop"""
        while True:
            try:
                # Check if market is open
                if self.market_monitor.is_market_open():
                    # Get symbols to analyze
                    symbols = self.scanner.get_symbols()
                    
                    # Log found symbols
                    logging.info(f"Found {len(symbols)} symbols to analyze")
                    
                    # Create tasks for each symbol
                    tasks = [self.analyze_symbol(symbol) for symbol in symbols]
                    
                    # Run analysis concurrently
                    await asyncio.gather(*tasks)
                
                else:
                    # Market closed, wait and check again
                    logging.info("Market is closed. Waiting for next market session.")
                
                # Wait before next scan (configurable)
                await asyncio.sleep(
                    self.config_manager.get('system_settings', {}).get('scan_interval', 60)
                )
            
            except Exception as e:
                logging.error(f"Main loop error: {str(e)}")
                # Wait a bit before retrying
                await asyncio.sleep(60)

def main():
    try:
        # Create trading system
        trading_system = TradingSystem()
        
        # Run the async main loop
        asyncio.run(trading_system.run())
    
    except KeyboardInterrupt:
        print("\nTrading system stopped by user.")
    
    except Exception as e:
        logging.error(f"Unhandled error: {str(e)}")

if __name__ == "__main__":
    main()
import asyncio
import logging
import json
import os

# Import components
from components.config_manager import ConfigManager
from components.stock_scanner import StockScanner
from components.stock_analyzer import StockAnalyzer
from components.trading_analyst import TradingAnalyst
from components.market_monitor import MarketMonitor
from components.output_formatter import OutputFormatter
from components.performance_tracker import PerformanceTracker

class TradingSystem:
    def __init__(self):
        # Setup logging
        self._setup_logging()
        
        # Load configuration
        self.config_manager = ConfigManager('config.json')
        
        # Initialize components
        self.scanner = StockScanner()
        self.market_monitor = MarketMonitor()
        self.output_formatter = OutputFormatter()
        self.performance_tracker = PerformanceTracker()
        
        # Initialize analyzer and trader with config
        self.analyzer = StockAnalyzer(self.config_manager)
        self.trading_analyst = TradingAnalyst()

    def _setup_logging(self):
        """Configure logging for the application"""
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/trading_system.log'),
                logging.StreamHandler()
            ]
        )

    async def analyze_symbol(self, symbol):
        """
        Analyze a single stock symbol
        
        Args:
            symbol (str): Stock ticker symbol
        """
        try:
            # Analyze stock data
            stock_data = self.analyzer.analyze_stock(symbol)
            
            if stock_data:
                # Get trading setup from AI
                trading_setup = await self.trading_analyst.analyze_setup(stock_data)
                
                # If a valid setup is found
                if trading_setup and 'NO SETUP' not in trading_setup:
                    # Format and display setup
                    formatted_setup = self.output_formatter.format_trading_setup(trading_setup)
                    print(formatted_setup)
                    
                    # Log performance
                    self.performance_tracker.log_trade(
                        symbol=symbol,
                        entry_price=stock_data.get('current_price', 0),
                        confidence=float(trading_setup.split('Confidence: ')[1].split('%')[0]) if 'Confidence:' in trading_setup else 0,
                        setup_details=trading_setup
                    )
        
        except Exception as e:
            logging.error(f"Error analyzing {symbol}: {str(e)}")

    async def run(self):
        """Main trading system loop"""
        while True:
            try:
                # Check if market is open
                if self.market_monitor.is_market_open():
                    # Get symbols to analyze
                    symbols = self.scanner.get_symbols()
                    
                    # Log found symbols
                    logging.info(f"Found {len(symbols)} symbols to analyze")
                    
                    # Create tasks for each symbol
                    tasks = [self.analyze_symbol(symbol) for symbol in symbols]
                    
                    # Run analysis concurrently
                    await asyncio.gather(*tasks)
                
                else:
                    # Market closed, wait and check again
                    logging.info("Market is closed. Waiting for next market session.")
                
                # Wait before next scan (configurable)
                await asyncio.sleep(
                    self.config_manager.get('system_settings', {}).get('scan_interval', 60)
                )
            
            except Exception as e:
                logging.error(f"Main loop error: {str(e)}")
                # Wait a bit before retrying
                await asyncio.sleep(60)

def main():
    try:
        # Create trading system
        trading_system = TradingSystem()
        
        # Run the async main loop
        asyncio.run(trading_system.run())
    
    except KeyboardInterrupt:
        print("\nTrading system stopped by user.")
    
    except Exception as e:
        logging.error(f"Unhandled error: {str(e)}")

if __name__ == "__main__":
    main()