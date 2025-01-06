import asyncio
import logging
import os
import re
from typing import Dict, Any
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
            'successful_trades': 0
        }

    def _setup_logging(self):
        os.makedirs('logs', exist_ok=True)
        handlers = []
        
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
            
            self.analyzer = StockAnalyzer(self.config_manager)
            self.position_manager = PositionManager(self.performance_tracker)
            self.trading_analyst = TradingAnalyst(
                performance_tracker=self.performance_tracker,
                position_manager=self.position_manager,
                model=self.config_manager.get('llm_configuration.model', 'llama3:latest')
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

    async def _update_state(self, new_state: TradingState):
        old_state = self.current_state
        self.current_state = new_state
        logging.info(f"State transition: {old_state.name} -> {new_state.name}")
        
        if new_state == TradingState.MARKET_SCANNING:
            await self._validate_market_conditions()
        elif new_state == TradingState.COOLDOWN:
            await self._perform_cooldown_tasks()

    async def _validate_market_conditions(self):
        try:
            if self.config_manager.config.get('testing_mode', {}).get('enabled', False):
                return True
                
            market_status = self.market_monitor.get_market_status()
            if not market_status['is_open']:
                check_interval = self.config_manager.config.get('market_check_interval', 60)
                time_until = self.market_monitor.time_until_market_open()
                logging.info(f"Market closed. Check in {check_interval}s. Opens in: {time_until}")
                await asyncio.sleep(check_interval)
                return False
            return True
        except Exception as e:
            logging.error(f"Market validation error: {str(e)}")
            await asyncio.sleep(60)
            return False

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
                            # Extract numeric value if possible
                            try:
                                # Try to find numeric part, handle percentage or fixed size
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
            min_confidence = self.config_manager.get('trading_rules.min_setup_confidence', 75)
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

    async def _perform_cooldown_tasks(self):
        try:
            report = self.performance_tracker.generate_report()
            logging.info(f"Performance Report:\n{report}")
            
            if self.metrics['trades_executed'] > 0:
                success_rate = (self.metrics['successful_trades'] / self.metrics['trades_executed']) * 100
                logging.info(f"Current success rate: {success_rate:.2f}%")
            
            logging.info("Performance Metrics:")
            for metric, value in self.metrics.items():
                logging.info(f"- {metric}: {value}")
            
            self.active_trades.clear()
            await asyncio.sleep(30)
            
        except Exception as e:
            logging.error(f"Cooldown error: {str(e)}")

    async def run(self):
        while True:
            try:
                await self._update_state(TradingState.INITIALIZATION)
                
                if not await self._validate_market_conditions():
                    continue
                
                await self._update_state(TradingState.MARKET_SCANNING)
                
                symbols = await self.scanner.get_symbols(
                    max_symbols=self.config_manager.get('system_settings.max_symbols', 100)
                )
                
                open_positions = self.performance_tracker.get_open_positions()
                active_symbols = open_positions['symbol'].tolist()
                symbols.extend([s for s in active_symbols if s not in symbols])
                
                logging.info(f"Analyzing {len(symbols)} symbols ({len(active_symbols)} active)")
                
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
                
                scan_interval = self.config_manager.get('system_settings.scan_interval', 60)
                await asyncio.sleep(scan_interval)
            
            except Exception as e:
                logging.error(f"Main loop error: {str(e)}")
                await asyncio.sleep(60)

def main():
    try:
        trading_system = TradingSystem()
        asyncio.run(trading_system.run())
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
