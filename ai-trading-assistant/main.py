"""
Trading System Main Module
------------------------
Main entry point for the trading system with improved broker handling 
and complete trading functionality.

Author: AI Trading Assistant
Version: 2.2  
Last Updated: 2025-01-09
"""

import asyncio
import logging
import os 
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, List
from components import (
    ConfigManager, MarketMonitor, OutputFormatter, PerformanceTracker,
    RobinhoodAuthenticator, AlpacaAuthenticator, StockAnalyzer, StockScanner,
    TradingAnalyst, BrokerManager, BrokerType
)

class TradingSystem:
    def __init__(self):
        """Initialize Trading System"""
        # Initialize system metrics
        self.metrics = {
            'trades_analyzed': 0,
            'setups_detected': 0,
            'trades_executed': 0, 
            'successful_trades': 0,
            'daily_watchlist': []
        }
        
        # Initialize components 
        self._setup_logging()
        self._init_components()

        # Store active trades
        self.active_trades = {}
        
    def _init_components(self):
        """Initialize system components"""
        self.config_manager = ConfigManager()
        
        self.market_monitor = MarketMonitor(
            timezone=self.config_manager.get('trading.market_timezone', 'US/Eastern')
        )
        self.output_formatter = OutputFormatter()
        self.performance_tracker = PerformanceTracker(
            log_dir=self.config_manager.get('system.performance_tracking.log_dir', 'performance_logs')
        )

        alpaca_auth = AlpacaAuthenticator()
        robinhood_auth = RobinhoodAuthenticator()
        
        if self.config_manager.get('trading.broker.preferred') == 'robinhood':
            robinhood_client = robinhood_auth.create_client()
            self.broker_manager = BrokerManager(
                self.config_manager, robinhood_client=robinhood_client
            )
        else:
            alpaca_client = alpaca_auth.create_trading_client()
            self.broker_manager = BrokerManager(
                self.config_manager, alpaca_client=alpaca_client
            )
            
        self.scanner = StockScanner()
        self.analyzer = StockAnalyzer(
            config=self.config_manager.get_section('trading.filters')
        )
        self.analyst = TradingAnalyst(
            self.performance_tracker, 
            self.broker_manager,
            model=self.config_manager.get('system.llm.model', 'llama3')
        )

    def _setup_logging(self):
        """Setup logging configuration"""
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
            
    async def _generate_eod_report(self):
        """Generate end-of-day analysis and performance report"""
        try:
            # Get performance metrics with error handling
            try:
                metrics = self.performance_tracker.get_metrics()
            except Exception as e:
                logging.error(f"Error getting performance metrics: {str(e)}")
                metrics = {}
            
            # Get broker metrics with error handling  
            try:
                broker_metrics = self.broker_manager.get_account_metrics()
            except Exception as e:
                logging.error(f"Error getting broker metrics: {str(e)}")
                broker_metrics = {}
            
            # Format the report with safe gets
            report_lines = [
                "\n=== End of Day Report ===",
                f"Date: {datetime.now().strftime('%Y-%m-%d')}",  
                f"Broker: {self.broker_manager.broker_type.value}",
                "\nAccount Summary:",
                f"Current Balance: ${broker_metrics.get('current_balance', 0.0):.2f}",
                f"Day's P&L: ${broker_metrics.get('unrealized_pl', 0.0):.2f}",
                f"Buying Power: ${broker_metrics.get('buying_power', 0.0):.2f}",
                
                "\nToday's Trading Activity:",
                f"Trades Analyzed: {self.metrics.get('trades_analyzed', 0)}",
                f"Setups Detected: {self.metrics.get('setups_detected', 0)}",  
                f"Trades Executed: {self.metrics.get('trades_executed', 0)}",
                
                "\nOverall Performance:",
                f"Total Trades: {metrics.get('total_trades', 0)}",
                f"Win Rate: {metrics.get('win_rate', 0.0):.1f}%",  
                f"Average P&L: ${metrics.get('avg_profit_loss', 0.0):.2f}",
                f"Largest Win: ${metrics.get('largest_win', 0.0):.2f}",
                f"Largest Loss: ${metrics.get('largest_loss', 0.0):.2f}",
                
                "\nRisk Metrics:", 
                f"Open Positions: {metrics.get('open_trades', 0)}",
                f"Current Drawdown: {broker_metrics.get('drawdown', 0.0):.1f}%",
                f"High Water Mark: ${broker_metrics.get('high_water_mark', 0.0):.2f}"
            ]
            
            # Log the report
            for line in report_lines:
                logging.info(line)
            
            # Reset daily metrics
            self.metrics.update({
                'trades_analyzed': 0,
                'setups_detected': 0,  
                'trades_executed': 0,
                'successful_trades': 0,
                'daily_watchlist': []
            })
            
            # Clear caches with error handling
            try:
                self.analyzer.clear_cache()
            except Exception as e:
                logging.warning(f"Error clearing analyzer cache: {str(e)}")
                
            try:    
                self.scanner.clear_cache()
            except Exception as e:
                logging.warning(f"Error clearing scanner cache: {str(e)}")
        
        except Exception as e:
            logging.error(f"Error generating EOD report: {str(e)}")
            return

    async def _handle_premarket(self):
        """Handle pre-market analysis"""
        try:
            logging.info("Pre-market session. Running pre-market scan...")
            symbols = await self.scanner.get_symbols(max_symbols=50)
            await self._analyze_premarket_movers(symbols)
            await asyncio.sleep(300)  # 5-minute delay between pre-market scans

        except Exception as e:
            logging.error(f"Pre-market handling error: {str(e)}")

    async def _handle_postmarket(self):
        """Handle post-market wrap-up"""
        try:
            logging.info("Post-market session. Generating end-of-day report...")
            await self._generate_eod_report()
            await asyncio.sleep(300)

        except Exception as e:
            logging.error(f"Post-market handling error: {str(e)}")

    async def _handle_regular_trading(self):
        """Handle regular trading hours"""
        try:
            symbols = await self.scanner.get_symbols(
                max_symbols=self.config_manager.get('system.max_symbols', 100)
            )

            # Add watchlist symbols
            watchlist_symbols = [s for s in self.metrics['daily_watchlist'] if s not in symbols]
            symbols.extend(watchlist_symbols)

            # Add open position symbols
            open_positions = self.performance_tracker.get_open_positions()
            active_symbols = open_positions['symbol'].tolist()
            symbols.extend([s for s in active_symbols if s not in symbols])

            logging.info(f"Analyzing {len(symbols)} symbols "
                       f"({len(active_symbols)} active, {len(watchlist_symbols)} watchlist)")

            if symbols:
                tasks = [self.analyze_symbol(symbol) for symbol in symbols]
                await asyncio.gather(*tasks)

            scan_interval = self.config_manager.get('system.scan_interval', 60)
            await asyncio.sleep(scan_interval)

        except Exception as e:
            logging.error(f"Regular trading handling error: {str(e)}")

    async def _execute_trade(self, symbol: str, setup_details: Dict[str, Any]):
        """Execute a trade based on the trading setup"""
        try:
            # Prepare trade parameters  
            trade_params = {
                'symbol': symbol,
                'quantity': setup_details.get('size', 100),
                'order_type': setup_details.get('order_type', 'market'),
                'entry_price': setup_details.get('entry', None),
                'stop_loss': setup_details.get('stop', None),
                'take_profit': setup_details.get('target', None)
            }

            # Use broker manager to execute trade
            execution_result = await self.broker_manager.place_trade(trade_params)

            if execution_result.get('status') == 'success':
                logging.info(f"Trade executed for {symbol}: {trade_params}")  
                self.metrics['successful_trades'] += 1
            else:
                logging.warning(f"Trade execution failed for {symbol}: {execution_result.get('reason', 'Unknown error')}")

        except Exception as e:
            logging.error(f"Trade execution error for {symbol}: {str(e)}")

    def _parse_trading_setup(self, setup: str) -> Optional[Dict[str, Any]]:
        """Parse the trading setup string into a dictionary"""
        try:
            setup_dict = {}
            lines = setup.strip().split("\n")

            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()

                    # Handle different field types
                    if 'price' in key or 'stop' in key or 'target' in key:
                        try:
                            value = float(value.replace(", ", "").strip())
                        except ValueError:
                            logging.warning(f"Invalid price format: {value}")
                            continue

                    elif 'confidence' in key:
                        try:
                            value = float(value.rstrip('%'))
                        except ValueError:
                            logging.warning(f"Invalid confidence format: {value}")
                            continue

                    setup_dict[key] = value

            return setup_dict if setup_dict else None

        except Exception as e:
            logging.error(f"Error parsing trading setup: {str(e)}")
            return None

    async def _handle_closed_market(self, market_status: Dict[str, Any]):
        """Handle closed market state"""
        current_time = datetime.now(self.market_monitor.timezone).strftime('%H:%M:%S %Z')
        time_until_open = self.market_monitor.time_until_market_open()

        if market_status['is_weekend']:
            logging.info(f"Market closed for weekend. Current time: {current_time}")
        elif market_status['today_is_holiday']:
            logging.info(f"Market closed for holiday. Current time: {current_time}")
        else:
            hours_until = time_until_open.total_seconds() / 3600
            logging.info(f"Market closed. Current time: {current_time}. "
                      f"Next session begins in {hours_until:.1f} hours")

        await asyncio.sleep(300)  # Check every 5 minutes

    async def run(self):
        """Main trading system loop"""
        while True:
            try:
                # Check market status
                market_phase = self.market_monitor.get_market_phase()
                market_status = self.market_monitor.get_market_status()

                if market_phase == 'closed':
                    await self._handle_closed_market(market_status)
                elif market_phase == 'pre-market':
                    await self._handle_premarket()  
                elif market_phase == 'post-market':
                    await self._handle_postmarket()
                else:  # Regular trading hours
                    await self._handle_regular_trading()

            except Exception as e:
                logging.error(f"Main loop error: {str(e)}")
                await asyncio.sleep(60)

def main():
    """Main entry point""" 
    try:
        logging.info("Starting trading system...")
        trading_system = TradingSystem()

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
