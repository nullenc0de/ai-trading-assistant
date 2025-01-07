import asyncio
import logging
import os
import re
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd
from enum import Enum, auto
import json

from components.config_manager import ConfigManager
from components.stock_scanner import StockScanner
from components.stock_analyzer import StockAnalyzer 
from components.trading_analyst import TradingAnalyst
from components.market_monitor import MarketMonitor
from components.output_formatter import OutputFormatter
from components.performance_tracker import PerformanceTracker
from components.robinhood_authenticator import RobinhoodAuthenticator
from components.position_manager import PositionManager
from components.account_manager import AccountManager

class TradingState(Enum):
    INITIALIZATION = auto()
    MARKET_SCANNING = auto()
    OPPORTUNITY_DETECTION = auto() 
    POSITION_MANAGEMENT = auto()
    EXIT_MANAGEMENT = auto()
    COOLDOWN = auto()

class TradingSystem:
    def __init__(self):
        self.current_state = TradingState.INITIALIZATION
        self._setup_logging()
        self._init_components()
        self.active_trades = {}
        self.metrics = {
            'trades_analyzed': 0,
            'setups_detected': 0,
            'trades_executed': 0,
            'successful_trades': 0,
            'daily_watchlist': []
        }

    def _setup_logging(self):
        os.makedirs('logs', exist_ok=True)
        handlers = []
        
        file_handler = logging.FileHandler('logs/trading_system.log')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'))
        handlers.append(file_handler)
        
        debug_handler = logging.FileHandler('logs/trading_system_debug.log')
        debug_handler.setLevel(logging.DEBUG)
        debug_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'))
        handlers.append(debug_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s'))
        handlers.append(console_handler)
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        for handler in handlers:
            root_logger.addHandler(handler)

    def _init_components(self):
        try:
            self.config_manager = ConfigManager('config.json')
            self.robinhood_auth = RobinhoodAuthenticator()
            self._check_robinhood_credentials()
            
            self.scanner = StockScanner()
            self.market_monitor = MarketMonitor()
            self.output_formatter = OutputFormatter()
            self.performance_tracker = PerformanceTracker()
            
            # Initialize account_manager before position_manager
            self.account_manager = AccountManager(
                config_manager=self.config_manager,
                robinhood_client=None  # Since we're in analysis-only mode
            )
            
            self.analyzer = StockAnalyzer(self.config_manager)
            # Pass both required arguments
            self.position_manager = PositionManager(
                performance_tracker=self.performance_tracker,
                account_manager=self.account_manager
            )
            
            self.trading_analyst = TradingAnalyst(
                performance_tracker=self.performance_tracker,
                position_manager=self.position_manager,
                model=self.config_manager.get('llm.model', 'llama3:latest')
            )
            
            logging.info("All components initialized successfully")
            
        except Exception as e:
            logging.error(f"Failed to initialize components: {str(e)}")
            raise

    def _check_robinhood_credentials(self):
        try:
            credentials = self.robinhood_auth.load_credentials()
            if not credentials:
                print("\n🤖 Robinhood Integration")
                choice = input("Configure Robinhood? (Y/N): ").strip().lower()
                if choice == 'y':
                    if not self.robinhood_auth.save_credentials():
                        raise Exception("Failed to save credentials")
                else:
                    logging.info("Running in analysis-only mode")
        except Exception as e:
            logging.error(f"Auth error: {str(e)}")
            print("Error setting up Robinhood. Running in analysis-only mode.")

    async def analyze_symbol(self, symbol: str):
        try:
            self.metrics['trades_analyzed'] += 1
            
            stock_data = self.analyzer.analyze_stock(symbol)
            if not stock_data:
                return

            technical_data = stock_data.get('technical_indicators', {})
            logging.info(f"Technical data for {symbol}:")
            logging.info(f"  Price: ${stock_data.get('current_price', 0):.2f}")
            logging.info(f"  RSI: {technical_data.get('rsi', 'N/A')}")
            logging.info(f"  VWAP: ${technical_data.get('vwap', 'N/A')}")
            
            open_positions = self.performance_tracker.get_open_positions()
            if not open_positions.empty and symbol in open_positions['symbol'].values:
                position = open_positions[open_positions['symbol'] == symbol].iloc[0]
                
                await self.trading_analyst.analyze_position(
                    stock_data=stock_data,
                    position_data={
                        'entry_price': position['entry_price'],
                        'current_price': stock_data['current_price'],
                        'target_price': position['target_price'],
                        'stop_price': position['stop_price'],
                        'size': position['position_size'],
                        'time_held': (datetime.now() - pd.to_datetime(position['timestamp'])).total_seconds() / 3600
                    }
                )
                return

            # Only analyze for new setups during regular market hours unless in testing mode
            market_phase = self.market_monitor.get_market_phase()
            if market_phase != 'regular' and not self.config_manager.get('market.testing_mode.enabled', False):
                return

            trading_setup = await self.trading_analyst.analyze_setup(stock_data)
            
            if trading_setup and 'NO SETUP' not in trading_setup:
                self.metrics['setups_detected'] += 1
                setup_details = self._parse_trading_setup(trading_setup)
                
                if setup_details:
                    formatted_setup = self.output_formatter.format_trading_setup(trading_setup)
                    print(formatted_setup)
                    
                    trade_data = {
                        'symbol': setup_details.get('symbol', symbol),
                        'entry_price': setup_details.get('entry', setup_details.get('entry_price')),
                        'target_price': setup_details.get('target', setup_details.get('target_price')),
                        'stop_price': setup_details.get('stop', setup_details.get('stop_price')),
                        'size': setup_details.get('size', 100),
                        'confidence': setup_details.get('confidence'),
                        'reason': setup_details.get('reason', ''),
                        'type': 'PAPER',
                        'status': 'OPEN',
                        'notes': 'Auto-generated by AI analysis'
                    }
                    
                    if self.performance_tracker.log_trade(trade_data):
                        self.metrics['trades_executed'] += 1
                        await self._execute_trade(symbol, setup_details)
                        
        except Exception as e:
            logging.error(f"Symbol analysis error: {str(e)}")

    def _parse_trading_setup(self, setup: str) -> Dict[str, Any]:
        try:
            setup_dict = {}
            lines = setup.strip().split('\n')
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    try:
                        # Symbol
                        if 'symbol' in key:
                            setup_dict['symbol'] = value
                        
                        # Numeric values with robust parsing
                        elif any(prefix in key for prefix in ['entry', 'target', 'stop']):
                            value = value.lstrip('$')
                            try:
                                numeric_value = float(value)
                                setup_dict[key.replace(' ', '_')] = numeric_value
                            except ValueError:
                                logging.warning(f"Could not parse {key}: {value}")
                        
                        # Confidence
                        elif 'confidence' in key:
                            value = value.rstrip('%')
                            try:
                                setup_dict['confidence'] = float(value)
                            except ValueError:
                                logging.warning(f"Invalid confidence: {value}")
                        
                        # Size handling
                        elif 'size' in key:
                            try:
                                if '%' in value.lower():
                                    matches = re.findall(r'([\d.]+)\s*%', value)
                                    if matches:
                                        setup_dict['size'] = float(matches[0])
                                else:
                                    setup_dict['size'] = float(re.findall(r'[\d.]+', value)[0])
                            except:
                                setup_dict['size'] = value
                        
                        # Risk/Reward
                        elif 'risk/reward' in key:
                            setup_dict['risk_reward'] = value
                        
                        # Reason
                        elif 'reason' in key:
                            setup_dict['reason'] = value
                    
                    except Exception as ve:
                        logging.error(f"Error parsing {key}: {value} - {ve}")
            
            return setup_dict
        
        except Exception as e:
            logging.error(f"Setup parsing error: {str(e)}")
            return {}

    async def _execute_trade(self, symbol: str, setup: Dict[str, Any]):
        try:
            min_confidence = self.config_manager.get('trading.rules.entry.min_setup_confidence', 75)
            if setup.get('confidence', 0) <= min_confidence:
                logging.info(f"Setup confidence {setup.get('confidence')}% below threshold")
                return
                
            self.active_trades[symbol] = {
                'entry_price': setup.get('entry', setup.get('entry_price')),
                'target_price': setup.get('target', setup.get('target_price')),
                'stop_price': setup.get('stop', setup.get('stop_price')),
                'size': setup.get('size', 100),
                'entry_time': datetime.now()
            }
            
            logging.info(f"Paper trade executed for {symbol}:")
            for key, value in setup.items():
                logging.info(f"- {key}: {value}")
            
        except Exception as e:
            logging.error(f"Trade execution error: {str(e)}")

    async def _analyze_premarket_movers(self, symbols: List[str]):
        """Analyze pre-market movers and prepare watchlist"""
        try:
            premarket_movers = []
            for symbol in symbols:
                stock_data = self.analyzer.analyze_stock(symbol)
                if not stock_data:
                    continue
                    
                # Calculate pre-market change
                current_price = stock_data['current_price']
                prev_close = stock_data.get('previous_close', current_price)
                change_pct = ((current_price - prev_close) / prev_close) * 100
                volume = stock_data.get('volume_analysis', {}).get('current_volume', 0)
                avg_volume = stock_data.get('volume_analysis', {}).get('avg_volume', 1)
                rel_volume = volume / avg_volume if avg_volume > 0 else 0
                
                # Track significant pre-market activity
                if abs(change_pct) >= 3.0 or rel_volume >= 2.0:
                    premarket_movers.append({
                        'symbol': symbol,
                        'price': current_price,
                        'change_pct': change_pct,
                        'volume': volume,
                        'rel_volume': rel_volume,
                        'technical_indicators': stock_data.get('technical_indicators', {})
                    })
            
            if premarket_movers:
                logging.info("\nPre-market Movers:")
                for mover in sorted(premarket_movers, key=lambda x: abs(x['change_pct']), reverse=True):
                    logging.info(
                        f"{mover['symbol']}: {mover['change_pct']:+.1f}% | "
                        f"${mover['price']:.2f} | {mover['rel_volume']:.1f}x Volume"
                    )
                
                # Update watchlist for regular session
                self.metrics['daily_watchlist'] = [m['symbol'] for m in premarket_movers]
        
        except Exception as e:
            logging.error(f"Pre-market analysis error: {str(e)}")

    async def _generate_eod_report(self):
        """Generate end-of-day analysis and watchlist"""
        try:
            # Get today's performance
            metrics = self.performance_tracker.get_metrics()
            
            logging.info("\nEnd of Day Report:")
            logging.info(f"Total Trades: {metrics.get('total_trades', 0)}")
            logging.info(f"Win Rate: {metrics.get('win_rate', 0):.1f}%")
            logging.info(f"Average Profit/Loss: ${metrics.get('avg_profit_loss', 0):.2f}")
            logging.info(f"Largest Win: ${metrics.get('largest_win', 0):.2f}")
            logging.info(f"Largest Loss: ${metrics.get('largest_loss', 0):.2f}")
            
            # Reset daily metrics
            self.metrics.update({
                'trades_analyzed': 0,
                'setups_detected': 0,
                'trades_executed': 0,
                'successful_trades': 0,
                'daily_watchlist': []
            })
            
            # Clear caches
            self.analyzer.clear_cache()
            self.scanner.clear_cache()
            
        except Exception as e:
            logging.error(f"EOD report error: {str(e)}")

    async def run(self):
        while True:
            try:
                await self._update_state(TradingState.INITIALIZATION)
                
                market_phase = self.market_monitor.get_market_phase()
                market_status = self.market_monitor.get_market_status()
                
                if market_phase == 'closed':
                    current_time = datetime.now(self.market_monitor.timezone).strftime('%H:%M:%S %Z')
                    time_until_open = self.market_monitor.time_until_market_open()
                    
                    if market_status['is_weekend']:
                        logging.info(f"Market closed for weekend. Current time: {current_time}")
                    elif market_status['today_is_holiday']:
                        logging.info(f"Market closed for holiday. Current time: {current_time}")
                    else:
                        hours_until = time_until_open.total_seconds() / 3600
                        logging.info(f"Market closed. Current time: {current_time}. Next session begins in {hours_until:.1f} hours")
                    await asyncio.sleep(300)  # Check every 5 minutes
                    continue
                    
                elif market_phase == 'pre-market':
                    logging.info("Pre-market session. Running pre-market scan...")
                    # Reduced scanning frequency, focus on gap analysis
                    symbols = await self.scanner.get_symbols(max_symbols=50)
                    await self._analyze_premarket_movers(symbols)
                    await asyncio.sleep(300)  # 5-minute delay between pre-market scans
                    continue
                    
                elif market_phase == 'post-market':
                    logging.info("Post-market session. Generating end-of-day report...")
                    await self._generate_eod_report()
                    # After EOD report, transition to closed state
                    await asyncio.sleep(300)
                    continue
                
                # Regular market hours processing
                await self._update_state(TradingState.MARKET_SCANNING)
                
                symbols = await self.scanner.get_symbols(
                    max_symbols=self.config_manager.get('system.max_symbols', 100)
                )
                
                # Add symbols from daily watchlist
                watchlist_symbols = [s for s in self.metrics['daily_watchlist'] if s not in symbols]
                symbols.extend(watchlist_symbols)
                
                # Add symbols from open positions
                open_positions = self.performance_tracker.get_open_positions()
                active_symbols = open_positions['symbol'].tolist()
                symbols.extend([s for s in active_symbols if s not in symbols])
                
                logging.info(f"Analyzing {len(symbols)} symbols "
                           f"({len(active_symbols)} active, {len(watchlist_symbols)} watchlist)")
                
                if not symbols:
                    await asyncio.sleep(60)
                    continue
                
                await self._update_state(TradingState.OPPORTUNITY_DETECTION)
                
                tasks = [self.analyze_symbol(symbol) for symbol in symbols]
                
                try:
                    await asyncio.gather(*tasks)
                except Exception as e:
                    logging.error(f"Error during symbol analysis: {str(e)}")
                
                await self._update_state(TradingState.COOLDOWN)
                
                scan_interval = self.config_manager.get('system.scan_interval', 60)
                await asyncio.sleep(scan_interval)
            
            except Exception as e:
                logging.error(f"Main loop error: {str(e)}")
                await asyncio.sleep(60)

    async def _update_state(self, new_state: TradingState):
        old_state = self.current_state
        self.current_state = new_state
        logging.info(f"State transition: {old_state.name} -> {new_state.name}")

def main():
    try:
        # Setup logging before anything else
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('trading_system.log')
            ]
        )
        
        logging.info("Starting trading system...")
        
        # Create and run the trading system
        trading_system = TradingSystem()
        
        # Run the async event loop
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(trading_system.run())
        except KeyboardInterrupt:
            logging.info("Shutting down trading system...")
        finally:
            loop.close()
            
    except KeyboardInterrupt:
        print("\nTrading system stopped by user.")
        logging.info("User initiated shutdown")
    except Exception as e:
        logging.critical(f"Fatal error: {str(e)}")
        raise
    finally:
        logging.info("Trading system shutdown complete")

if __name__ == "__main__":
    main()
