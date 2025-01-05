import asyncio
import logging
import json
import os
import pandas as pd
from datetime import datetime
from enum import Enum, auto
from typing import Dict, List, Optional, Any

from components.config_manager import ConfigManager
from components.stock_scanner import StockScanner
from components.stock_analyzer import StockAnalyzer
from components.trading_analyst import TradingAnalyst
from components.market_monitor import MarketMonitor
from components.output_formatter import OutputFormatter
from components.performance_tracker import PerformanceTracker
from components.robinhood_authenticator import RobinhoodAuthenticator

class TradingState(Enum):
    """Trading system state enumeration"""
    INITIALIZATION = auto()
    MARKET_SCANNING = auto()
    OPPORTUNITY_DETECTION = auto()
    POSITION_MANAGEMENT = auto()
    EXIT_MANAGEMENT = auto()
    COOLDOWN = auto()

class TradingSystem:
    def __init__(self):
        """Initialize Trading System with enhanced state management"""
        # Current state
        self.current_state = TradingState.INITIALIZATION
        
        # Setup logging
        self._setup_logging()
        
        # System components initialization
        self._init_components()
        
        # Active trades tracking
        self.active_trades: Dict[str, Dict[str, Any]] = {}
        
        # Performance metrics
        self.metrics = {
            'trades_analyzed': 0,
            'setups_detected': 0,
            'trades_executed': 0,
            'successful_trades': 0
        }

    def _init_components(self):
        """Initialize system components with proper error handling"""
        try:
            # Load configuration
            self.config_manager = ConfigManager('config.json')
            logging.info("Configuration loaded successfully")
            
            # Initialize Robinhood authentication
            self.robinhood_auth = RobinhoodAuthenticator()
            
            # Check for Robinhood credentials
            self._check_robinhood_credentials()
            
            # Initialize other components
            self.scanner = StockScanner()
            self.market_monitor = MarketMonitor()
            self.output_formatter = OutputFormatter()
            self.performance_tracker = PerformanceTracker()
            
            # Initialize analyzer and trader with config
            self.analyzer = StockAnalyzer(self.config_manager)
            self.trading_analyst = TradingAnalyst(
                model=self.config_manager.get('llm_configuration.model', 'llama3:latest')
            )
            
            logging.info("All components initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize components: {str(e)}")
            raise

    def _setup_logging(self):
        """Configure enhanced logging system"""
        try:
            # Create logs directory if it doesn't exist
            os.makedirs('logs', exist_ok=True)
            
            # Configure different log levels with file rotation
            handlers = []
            
            # Debug log handler (file only)
            debug_handler = logging.FileHandler('logs/trading_system_debug.log')
            debug_handler.setLevel(logging.DEBUG)
            debug_handler.setFormatter(
                logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')
            )
            handlers.append(debug_handler)
            
            # Info log handler (console)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(
                logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
            )
            handlers.append(console_handler)
            
            # Configure root logger
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.DEBUG)
            
            # Remove any existing handlers
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            # Add our configured handlers
            for handler in handlers:
                root_logger.addHandler(handler)
            
            # Reduce noise from HTTP client and yfinance
            logging.getLogger('urllib3').setLevel(logging.WARNING)
            logging.getLogger('yfinance').setLevel(logging.WARNING)
            
        except Exception as e:
            print(f"Failed to setup logging: {str(e)}")
            raise

    def _check_robinhood_credentials(self):
        """Verify and manage Robinhood authentication"""
        try:
            credentials = self.robinhood_auth.load_credentials()
            
            if not credentials:
                print("\n🤖 Robinhood Integration")
                print("No credentials found. Would you like to configure Robinhood integration?")
                choice = input("(Y/N): ").strip().lower()
                
                if choice == 'y':
                    if not self.robinhood_auth.save_credentials():
                        raise Exception("Failed to save Robinhood credentials")
                else:
                    logging.info("Skipping Robinhood integration. Running in analysis-only mode.")
            
        except Exception as e:
            logging.error(f"Robinhood authentication error: {str(e)}")
            print("Error setting up Robinhood integration. Running in analysis-only mode.")

    async def _update_state(self, new_state: TradingState):
        """Update system state with logging and validation"""
        old_state = self.current_state
        self.current_state = new_state
        
        logging.info(f"State transition: {old_state.name} -> {new_state.name}")
        
        # Perform state-specific initialization
        if new_state == TradingState.MARKET_SCANNING:
            await self._validate_market_conditions()
        elif new_state == TradingState.COOLDOWN:
            await self._perform_cooldown_tasks()

    async def _validate_market_conditions(self):
        """Validate current market conditions"""
        try:
            market_status = self.market_monitor.get_market_status()
            
            if not market_status['is_open']:
                time_until = self.market_monitor.time_until_market_open()
                wait_seconds = min(time_until.seconds, 3600)  # Max wait 1 hour
                
                logging.info(f"Market closed. Waiting {wait_seconds} seconds before next check")
                await asyncio.sleep(wait_seconds)
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error validating market conditions: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute on error
            return False

    async def analyze_symbol(self, symbol: str):
        """Analyze a single stock symbol and manage existing positions"""
        try:
            self.metrics['trades_analyzed'] += 1
            
            # Get current stock data first
            stock_data = self.analyzer.analyze_stock(symbol)
            if not stock_data:
                logging.debug(f"No analyzable data for {symbol}")
                return

            # Print the technical indicators
            technical_data = stock_data.get('technical_indicators', {})
            logging.info(f"Technical data for {symbol}:")
            logging.info(f"  Price: ${stock_data.get('current_price', 0):.2f}")
            logging.info(f"  RSI: {technical_data.get('rsi', 'N/A')}")
            logging.info(f"  VWAP: ${technical_data.get('vwap', 'N/A')}")
            
            # Check for existing position
            open_positions = self.performance_tracker.get_open_positions()
            if not open_positions.empty and symbol in open_positions['symbol'].values:
                existing_position = open_positions[open_positions['symbol'] == symbol].iloc[0]
                
                # Get position management decision
                position_action = await self.trading_analyst.analyze_position(
                    stock_data=stock_data,
                    position_data={
                        'entry_price': existing_position['entry_price'],
                        'current_price': stock_data['current_price'],
                        'target_price': existing_position['target_price'],
                        'stop_price': existing_position['stop_price'],
                        'size': existing_position['position_size'],
                        'time_held': (datetime.now() - pd.to_datetime(existing_position['timestamp'])).total_seconds() / 3600  # hours
                    }
                )
                
                # Handle position action
                if position_action:
                    await self._handle_position_action(symbol, position_action, existing_position, stock_data)
                return
            
            # If no position exists, look for new setup
            trading_setup = await self.trading_analyst.analyze_setup(stock_data)
            
            # Process new setup
            if trading_setup and 'NO SETUP' not in trading_setup:
                self.metrics['setups_detected'] += 1
                
                # Parse setup details
                setup_details = self._parse_trading_setup(trading_setup)
                if not setup_details:
                    logging.error(f"Failed to parse setup for {symbol}")
                    return
                
                # Format and display setup
                formatted_setup = self.output_formatter.format_trading_setup(trading_setup)
                print(formatted_setup)
                
                # Create paper trade data
                trade_data = {
                    'symbol': symbol,
                    'entry_price': setup_details.get('entry_price'),
                    'target_price': setup_details.get('target_price'),
                    'stop_price': setup_details.get('stop_price'),
                    'size': setup_details.get('size', 100),
                    'confidence': setup_details.get('confidence'),
                    'reason': setup_details.get('reason', ''),
                    'type': 'PAPER',
                    'status': 'OPEN',
                    'notes': 'Auto-generated by AI analysis'
                }
                
                # Log the paper trade
                if self.performance_tracker.log_trade(trade_data):
                    self.metrics['trades_executed'] += 1
                    logging.info(f"Paper trade created for {symbol}")
                    await self._execute_trade(symbol, setup_details)
            
            else:
                logging.debug(f"No valid setup found for {symbol}")
                
        except Exception as e:
            logging.error(f"Error analyzing {symbol}: {str(e)}")

    async def _handle_position_action(self, symbol: str, action: Dict[str, Any], position: pd.Series, current_data: Dict[str, Any]):
        """Handle advanced position management actions"""
        try:
            action_type = action.get('action', '').upper()
            
            if action_type == 'HOLD':
                logging.info(f"Maintaining position in {symbol}: {action.get('reason', 'No reason provided')}")
                return
                
            elif action_type == 'EXIT':
                # Close the full position
                exit_data = {
                    'status': 'CLOSED',
                    'exit_price': current_data['current_price'],
                    'exit_time': datetime.now().isoformat(),
                    'notes': f"Full exit: {action.get('reason', 'No reason provided')}"
                }
                self.performance_tracker.update_trade(symbol, exit_data)
                logging.info(f"Closed position in {symbol}: {action.get('reason', 'No reason provided')}")
                
            elif action_type == 'PARTIAL_EXIT':
                if 'scale_points' in action and 'sizes' in action:
                    # Handle scaling out at multiple price points
                    scale_points = action['scale_points']
                    sizes = action['sizes']
                    current_price = current_data['current_price']
                    
                    # Find which scale points we've hit
                    for price, size in zip(scale_points, sizes):
                        if current_price >= price:
                            exit_size = int(position['position_size'] * size)
                            remaining_size = position['position_size'] - exit_size
                            
                            # Update position
                            exit_data = {
                                'position_size': remaining_size,
                                'notes': f"Scale out {exit_size} shares at ${price}: {action.get('reason', 'No reason provided')}"
                            }
                            self.performance_tracker.update_trade(symbol, exit_data)
                            logging.info(f"Scaled out {exit_size} shares in {symbol} at ${price}")
                            
                else:
                    # Traditional partial exit
                    exit_percentage = action.get('exit_percentage', 0.5)
                    exit_size = int(position['position_size'] * exit_percentage)
                    remaining_size = position['position_size'] - exit_size
                    
                    exit_data = {
                        'position_size': remaining_size,
                        'notes': f"Partial exit ({exit_size} shares): {action.get('reason', 'No reason provided')}"
                    }
                    self.performance_tracker.update_trade(symbol, exit_data)
                    logging.info(f"Partial exit of {exit_size} shares in {symbol}")
                
            elif action_type == 'ADJUST_STOPS':
                stop_type = action.get('stop_type', 'FIXED')
                value = action.get('value', 0)
                current_price = current_data['current_price']
                entry_price = position['entry_price']
                
                if stop_type == 'FIXED':
                    new_stop = value
                elif stop_type == 'TRAILING':
                    # Calculate trailing stop based on percentage
                    trail_amount = current_price * (value / 100)
                    new_stop = current_price - trail_amount
                elif stop_type == 'BREAKEVEN':
                    # Move stop to entry plus buffer
                    new_stop = entry_price + value
                else:
                    logging.warning(f"Unknown stop type: {stop_type}")
                    return
                
                # Update the stop
                update_data = {
                    'stop_price': new_stop,
                    'notes': f"Stop adjusted to ${new_stop:.2f} ({stop_type}): {action.get('reason', 'No reason provided')}"
                }
                self.performance_tracker.update_trade(symbol, update_data)
                logging.info(f"Adjusted {stop_type} stop to ${new_stop:.2f} for {symbol}")
            
            else:
                logging.warning(f"Unknown position action type: {action_type}")
                
        except Exception as e:
            logging.error(f"Error handling position action: {str(e)}")
            return None

    def _parse_trading_setup(self, setup: str) -> Dict[str, Any]:
        """Parse trading setup string into structured data"""
        try:
            # Log the setup being parsed
            logging.debug(f"Parsing trading setup: {setup}")
            
            # Extract key components using string parsing
            lines = setup.split('\n')
            
            # Initialize empty dict for setup details
            setup_dict = {}
            
            # Parse each line
            for line in lines:
                if 'Entry:' in line:
                    setup_dict['entry_price'] = float(line.split('$')[1].strip())
                elif 'Target:' in line:
                    setup_dict['target_price'] = float(line.split('$')[1].strip())
                elif 'Stop:' in line:
                    setup_dict['stop_price'] = float(line.split('$')[1].strip())
                elif 'Size:' in line:
                    # Extract just the number from "100 shares" or similar
                    setup_dict['size'] = int(line.split(':')[1].strip().split()[0])
                elif 'Confidence:' in line:
                    setup_dict['confidence'] = float(line.split(':')[1].strip().rstrip('%'))
                elif 'Reason:' in line:
                    setup_dict['reason'] = line.split(':')[1].strip()
            
            # Log parsed values
            logging.debug(f"Parsed setup: {setup_dict}")
            return setup_dict
            
        except Exception as e:
            logging.error(f"Error parsing trading setup: {str(e)}\nSetup text: {setup}")
            return {}

    async def _execute_trade(self, symbol: str, setup: Dict[str, Any]):
        """Execute trade based on setup details"""
        try:
            # Check for Robinhood credentials
            credentials = self.robinhood_auth.load_credentials()
            if not credentials:
                return

            # Validate confidence threshold
            min_confidence = self.config_manager.get('trading_rules.min_setup_confidence', 75)
            current_confidence = setup.get('confidence', 0)
            if current_confidence <= min_confidence:
                logging.info(f"Setup confidence {current_confidence}% below threshold for {symbol}")
                return

            # Add to active trades
            self.active_trades[symbol] = {
                'entry_price': setup.get('entry_price'),
                'target_price': setup.get('target_price'),
                'stop_price': setup.get('stop_price'),
                'size': setup.get('size'),
                'entry_time': datetime.now()
            }
            
            # Log trade execution
            logging.info(f"Paper trade executed for {symbol}:")
            for key, value in setup.items():
                logging.info(f"- {key}: {value}")
            
        except Exception as e:
            logging.error(f"Error executing trade: {str(e)}")

    async def _perform_cooldown_tasks(self):
        """Execute post-trade analysis and system maintenance"""
        try:
            # Generate performance report
            report = self.performance_tracker.generate_report()
            logging.info(f"Performance Report:\n{report}")
            
            # Update metrics
            self._update_performance_metrics()
            
            # Clean up any stale data
            self.active_trades.clear()
            
            # Brief cooldown period
            await asyncio.sleep(30)
            
        except Exception as e:
            logging.error(f"Error in cooldown tasks: {str(e)}")

    def _update_performance_metrics(self):
        """Update system performance metrics"""
        try:
            # Calculate success rate
            if self.metrics['trades_executed'] > 0:
                success_rate = (
                    self.metrics['successful_trades'] / 
                    self.metrics['trades_executed'] * 100
                )
                logging.info(f"Current success rate: {success_rate:.2f}%")
            
            # Log other metrics
            logging.info("Performance Metrics:")
            for metric, value in self.metrics.items():
                logging.info(f"- {metric}: {value}")
                
        except Exception as e:
            logging.error(f"Error updating metrics: {str(e)}")

    async def run(self):
        """Main trading system loop with enhanced state management"""
        while True:
            try:
                # Start in initialization state
                await self._update_state(TradingState.INITIALIZATION)
                
                # Validate market conditions
                if not await self._validate_market_conditions():
                    continue
                
                # Update state to market scanning
                await self._update_state(TradingState.MARKET_SCANNING)
                
                # Get symbols to analyze
                symbols = await self.scanner.get_symbols(
                    max_symbols=self.config_manager.get('system_settings.max_symbols', 100)
                )
                logging.info(f"Found {len(symbols)} symbols to analyze")
                
                if not symbols:
                    logging.warning("No symbols found to analyze")
                    await asyncio.sleep(60)
                    continue
                
                # Update state to opportunity detection
                await self._update_state(TradingState.OPPORTUNITY_DETECTION)
                
                # Create analysis tasks
                tasks = [self.analyze_symbol(symbol) for symbol in symbols]
                
                # Run analysis concurrently
                await asyncio.gather(*tasks)
                
                # Move to cooldown state
                await self._update_state(TradingState.COOLDOWN)
                
                # Configure scan interval
                scan_interval = self.config_manager.get('system_settings.scan_interval', 60)
                await asyncio.sleep(scan_interval)
            
            except Exception as e:
                logging.error(f"Main loop error: {str(e)}")
                await asyncio.sleep(60)  # Error cooldown


def main():
    """Entry point with enhanced error handling"""
    try:
        # Create trading system
        trading_system = TradingSystem()
        
        # Run the async main loop
        asyncio.run(trading_system.run())
    
    except KeyboardInterrupt:
        print("\nTrading system stopped by user.")
        logging.info("Trading system shutdown initiated by user")
    
    except Exception as e:
        logging.critical(f"Fatal error in trading system: {str(e)}")
        raise
    
    finally:
        logging.info("Trading system shutdown complete")


if __name__ == "__main__":
    main()
