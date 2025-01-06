import ollama
import logging
from typing import Dict, Optional, Any
import asyncio
from datetime import datetime, timedelta
import pandas as pd

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
            
            # Handle the action
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

            # Extract prices
            entry = float(lines[1].split('$')[1])
            target = float(lines[2].split('$')[1])
            stop = float(lines[3].split('$')[1])
            
            # Validate entry near current price
            current = data['current_price']
            if not (0.98 * current <= entry <= 1.02 * current):
                return False

            # Validate risk/reward
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
                
                # Calculate P&L for exited portion
                exit_pl = (current_price - position['entry_price']) * exit_size
                
                # Create exit trade record
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

                # Update remaining position
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

            # Force metrics update
            self.performance_tracker._update_metrics()

        except Exception as e:
            self.logger.error(f"Position action error: {str(e)}")
            return None
