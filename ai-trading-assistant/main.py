import asyncio
import logging
import json
import os
import pandas as pd
import ollama
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Dict, List, Optional, Any

class TradingState(Enum):
    INITIALIZATION = auto()
    MARKET_SCANNING = auto()
    OPPORTUNITY_DETECTION = auto()
    POSITION_MANAGEMENT = auto()
    EXIT_MANAGEMENT = auto()
    COOLDOWN = auto()

class PositionManager:
    def __init__(self, performance_tracker):
        self.performance_tracker = performance_tracker
        self.logger = logging.getLogger(__name__)

    async def handle_position_action(self, symbol: str, action: Dict[str, Any], position: Dict[str, Any], current_data: Dict[str, Any]):
        try:
            action_type = action['action'].upper()
            current_price = current_data['current_price']
            
            if action_type == 'EXIT':
                exit_data = {
                    'status': 'CLOSED',
                    'exit_price': current_price,
                    'exit_time': datetime.now().isoformat(),
                    'profit_loss': (current_price - position['entry_price']) * position['size'],
                    'profit_loss_percent': ((current_price / position['entry_price']) - 1) * 100
                }
                self.performance_tracker.update_trade(symbol, exit_data)
                self.logger.info(f"Closed position in {symbol} at ${current_price:.2f}")

            elif action_type == 'PARTIAL_EXIT':
                current_size = int(position['size'])
                exit_size = current_size // 2
                remaining_size = current_size - exit_size
                
                exit_pl = (current_price - position['entry_price']) * exit_size
                
                exit_trade = {
                    'symbol': symbol,
                    'entry_price': position['entry_price'],
                    'exit_price': current_price,
                    'position_size': exit_size,
                    'status': 'CLOSED',
                    'exit_time': datetime.now().isoformat(),
                    'profit_loss': exit_pl,
                    'profit_loss_percent': ((current_price / position['entry_price']) - 1) * 100,
                    'notes': 'Partial exit'
                }
                self.performance_tracker.log_trade(exit_trade)

                update_data = {
                    'position_size': remaining_size,
                    'notes': f"Partial exit of {exit_size} shares at ${current_price:.2f}"
                }
                self.performance_tracker.update_trade(symbol, update_data)
                self.logger.info(f"Partial exit of {exit_size} shares in {symbol}")

            elif action_type == 'ADJUST_STOPS':
                if 'params' in action and action['params']:
                    try:
                        new_stop = float(action['params'].split('=')[1].strip())
                        update_data = {'stop_price': new_stop}
                        self.performance_tracker.update_trade(symbol, update_data)
                        self.logger.info(f"Adjusted stop to ${new_stop:.2f} for {symbol}")
                    except:
                        self.logger.error(f"Invalid stop price format: {action['params']}")

            elif action_type == 'HOLD':
                self.logger.info(f"Maintaining position in {symbol}: {action.get('reason', '')}")

            self.performance_tracker._update_metrics()

        except Exception as e:
            self.logger.error(f"Position action error: {str(e)}")
            return None

class TradingAnalyst:
    def __init__(self, performance_tracker, model="llama3:latest", max_retries=3):
        self.model = model
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        self.performance_tracker = performance_tracker
        self.position_manager = PositionManager(performance_tracker)

    async def analyze_position(self, stock_data: Dict[str, Any], position_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            entry_price = position_data['entry_price']
            current_price = stock_data['current_price']
            position_size = position_data['size']
            
            unrealized_pl = (current_price - entry_price) * position_size
            unrealized_pl_pct = ((current_price / entry_price) - 1) * 100
            
            prompt = f"""Analyze this position and decide next action:

Position: {stock_data['symbol']}
Entry: ${entry_price:.2f}
Current: ${current_price:.2f}
Target: ${position_data['target_price']:.2f}
Stop: ${position_data['stop_price']:.2f}
Size: {position_size}
Hours Held: {position_data['time_held']:.1f}
P&L: ${unrealized_pl:.2f} ({unrealized_pl_pct:.1f}%)
Risk Multiple: {abs(unrealized_pl_pct) / abs(((entry_price - position_data['stop_price']) / entry_price) * 100):.1f}R

Technical:
RSI: {stock_data.get('technical_indicators', {}).get('rsi')}
VWAP: ${stock_data.get('technical_indicators', {}).get('vwap'):.2f}
ATR: {stock_data.get('technical_indicators', {}).get('atr')}

Choose action:
1. HOLD - Keep position
2. EXIT - Close position
3. PARTIAL_EXIT - 50% reduction
4. ADJUST_STOPS - Move stops

Format:
ACTION: [HOLD/EXIT/PARTIAL_EXIT/ADJUST_STOPS]
PARAMS: [if needed]
REASON: [explanation]"""

            response = await self._generate_llm_response(prompt)
            action = self._parse_position_action(response)
            
            await self.position_manager.handle_position_action(
                stock_data['symbol'], 
                action,
                position_data,
                stock_data
            )
            
            return action

        except Exception as e:
            self.logger.error(f"Position analysis error: {str(e)}")
            return {'action': 'HOLD', 'reason': 'Analysis error'}

    async def _generate_llm_response(self, prompt: str) -> str:
        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    'temperature': 0.2,
                    'num_predict': 150
                }
            )
            return response.get('response', '').strip()
        except Exception as e:
            self.logger.error(f"LLM error: {str(e)}")
            return ""

    def _parse_position_action(self, response: str) -> Dict[str, Any]:
        try:
            lines = response.split('\n')
            action = {
                'action': lines[0].split(':')[1].strip(),
                'params': lines[1].split(':')[1].strip() if len(lines) > 1 and 'PARAMS:' in lines[1] else None,
                'reason': lines[-1].split(':')[1].strip() if len(lines) > 2 else ''
            }
            return action
        except Exception as e:
            self.logger.error(f"Action parse error: {str(e)}")
            return {'action': 'HOLD', 'reason': 'Parse error'}

    async def analyze_setup(self, data: Dict[str, Any]) -> Optional[str]:
        if not self._validate_data(data):
            return "NO SETUP"

        prompt = f"""Analyze for potential trade:

Symbol: {data['symbol']}
Price: ${data['current_price']:.2f}
RSI: {data.get('technical_indicators', {}).get('rsi')}
VWAP: ${data.get('technical_indicators', {}).get('vwap'):.2f}

Format:
TRADING SETUP: {data['symbol']}
Entry: $XX.XX
Target: $XX.XX
Stop: $XX.XX
Size: 100
Reason: [clear reason]
Confidence: XX%
Risk-Reward: X:1

Or respond: NO SETUP"""

        try:
            setup = await self._generate_llm_response(prompt)
            if self._validate_setup(setup, data):
                return setup
            return "NO SETUP"
        except Exception as e:
            self.logger.error(f"Setup analysis error: {str(e)}")
            return "NO SETUP"

    def _validate_data(self, data: Dict[str, Any]) -> bool:
        required = ['symbol', 'current_price', 'technical_indicators']
        return all(data.get(k) for k in required)

    def _validate_setup(self, setup: str, data: Dict[str, Any]) -> bool:
        try:
            if setup == "NO SETUP":
                return True

            lines = setup.split('\n')
            if len(lines) < 7:
                return False

            entry = float(lines[1].split('$')[1])
            target = float(lines[2].split('$')[1])
            stop = float(lines[3].split('$')[1])
            
            current = data['current_price']
            if not (0.98 * current <= entry <= 1.02 * current):
                return False

            risk = abs(entry - stop)
            if risk == 0:
                return False

            reward = abs(target - entry)
            if reward / risk < 2:
                return False

            return True

        except Exception as e:
            self.logger.error(f"Setup validation error: {str(e)}")
            return False

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
        debug_handler.setFormatter(
            logging.Formatter('%(asctime)s - [%(levelname)s] - %(name)s - %(message)s')
        )
        handlers.append(debug_handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
        )
        handlers.append(console_handler)
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        for handler in handlers:
            root_logger.addHandler(handler)
        
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('yfinance').setLevel(logging.WARNING)

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
            self.trading_analyst = TradingAnalyst(
                performance_tracker=self.performance_tracker,
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
            if (self.config_manager.config.get('testing_mode', {}).get('enabled', False) and 
                self.config_manager.config.get('testing_mode', {}).get('override_market_hours', False)):
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
                
                position_action = await self.trading_analyst.analyze_position(
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
                    
                    if self.performance_tracker.log_trade(trade_data):
                        self.metrics['trades_executed'] += 1
                        await self._execute_trade(symbol, setup_details)
                        
        except Exception as e:
            logging.error(f"Symbol analysis error: {str(e)}")

    def _parse_trading_setup(self, setup: str) -> Dict[str, Any]:
        try:
            logging.debug(f"Parsing setup: {setup}")
            
            lines = setup.split('\n')
            setup_dict = {}
            
            for line in lines:
                if 'Entry:' in line:
                    setup_dict['entry_price'] = float(line.split('$')[1].strip())
                elif 'Target:' in line:
                    setup_dict['target_price'] = float(line.split('$')[1].strip())
                elif 'Stop:' in line:
                    setup_dict['stop_price'] = float(line.split('$')[1].strip())
                elif 'Size:' in line:
                    setup_dict['size'] = int(line.split(':')[1].strip().split()[0])
                elif 'Confidence:' in line:
                    setup_dict['confidence'] = float(line.split(':')[1].strip().rstrip('%'))
                elif 'Reason:' in line:
                    setup_dict['reason'] = line.split(':')[1].strip()
            
            return setup_dict
            
        except Exception as e:
            logging.error(f"Setup parsing error: {str(e)}")
            return {}

    async def _execute_trade(self, symbol: str, setup: Dict[str, Any]):
        try:
            credentials = self.robinhood_auth.load_credentials()
            if not credentials:
                return

            min_confidence = self.config_manager.get('trading_rules.min_setup_confidence', 75)
            if setup.get('confidence', 0) <= min_confidence:
                logging.info(f"Setup confidence {setup.get('confidence')}% below threshold")
                return
                
            account_balance = await self.robinhood_auth.get_account_balance()
            position_size = self._calculate_position_size(setup, account_balance)
            
            if position_size <= 0:
                logging.info(f"Invalid position size for {symbol}")
                return

            self.active_trades[symbol] = {
                'entry_price': setup.get('entry_price'),
                'target_price': setup.get('target_price'),
                'stop_price': setup.get('stop_price'),
                'size': position_size,
                'entry_time': datetime.now()
            }
            
            logging.info(f"Trade executed for {symbol}:")
            for key, value in setup.items():
                logging.info(f"- {key}: {value}")
            
        except Exception as e:
            logging.error(f"Trade execution error: {str(e)}")

    def _calculate_position_size(self, setup: Dict[str, Any], account_balance: float) -> int:
        try:
            max_risk_per_trade = self.config_manager.get('risk_management.max_risk_per_trade_percent', 1.0) / 100
            max_position_size = self.config_manager.get('risk_management.max_position_size_percent', 15.0) / 100
            min_reward_risk_ratio = self.config_manager.get('risk_management.min_reward_risk_ratio', 2.0)
            
            entry_price = setup.get('entry_price', 0)
            stop_price = setup.get('stop_price', 0)
            target_price = setup.get('target_price', 0)
            
            if not all([entry_price, stop_price, target_price]):
                return 0

            risk_per_share = abs(entry_price - stop_price)
            if risk_per_share == 0:
                return 0
            
            reward = abs(target_price - entry_price)
            reward_risk_ratio = reward / risk_per_share
            
            if reward_risk_ratio < min_reward_risk_ratio:
                return 0
            
            max_risk_amount = account_balance * max_risk_per_trade
            position_size = int(max_risk_amount / risk_per_share)
            
            max_shares = int((account_balance * max_position_size) / entry_price)
            position_size = min(position_size, max_shares)
            
            min_position_size = self.config_manager.get('risk_management.min_position_size', 100)
            if position_size < min_position_size:
                return 0
                
            return position_size
            
        except Exception as e:
            logging.error(f"Position sizing error: {str(e)}")
            return 0

    async def _perform_cooldown_tasks(self):
        try:
            report = self.performance_tracker.generate_report()
            logging.info(f"Performance Report:\n{report}")
            
            self._update_performance_metrics()
            self.active_trades.clear()
            await asyncio.sleep(30)
            
        except Exception as e:
            logging.error(f"Cooldown error: {str(e)}")

    def _update_performance_metrics(self):
        try:
            if self.metrics['trades_executed'] > 0:
                success_rate = (
                    self.metrics['successful_trades'] / 
                    self.metrics['trades_executed'] * 100
                )
                logging.info(f"Success rate: {success_rate:.2f}%")
            
            logging.info("Performance Metrics:")
            for metric, value in self.metrics.items():
                logging.info(f"- {metric}: {value}")
                
        except Exception as e:
            logging.error(f"Metrics update error: {str(e)}")

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
                await asyncio.gather(*tasks)
                
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
