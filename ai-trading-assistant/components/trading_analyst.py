import asyncio
import logging
from typing import Dict, Optional, Any
from datetime import datetime
import pandas as pd
import ollama

class TradingAnalyst:
    def __init__(self, model="llama3:latest", max_retries=3):
        self.model = model
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    async def analyze_position(self, stock_data: Dict[str, Any], position_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            entry_price = position_data['entry_price']
            current_price = stock_data['current_price']
            position_size = position_data['size']
            
            unrealized_pl = (current_price - entry_price) * position_size
            unrealized_pl_pct = ((current_price / entry_price) - 1) * 100
            atr = stock_data.get('technical_indicators', {}).get('atr', 'N/A')
            
            prompt = f"""You are managing an existing trading position. Analyze the current market conditions and decide the next action.

POSITION STATUS:
Symbol: {stock_data['symbol']}
Entry Price: ${entry_price:.2f}
Current Price: ${current_price:.2f}
Target Price: ${position_data['target_price']:.2f}
Stop Price: ${position_data['stop_price']:.2f}
Position Size: {position_size} shares
Hours Held: {position_data['time_held']:.1f}

CURRENT TECHNICAL DATA:
Price: ${current_price:.2f}
RSI: {stock_data.get('technical_indicators', {}).get('rsi', 'N/A')}
VWAP: ${stock_data.get('technical_indicators', {}).get('vwap', 'N/A')}
ATR: {atr if atr != 'N/A' else 'Not Available'}

POSITION METRICS:
Unrealized P&L: ${unrealized_pl:.2f}
Unrealized P&L %: {unrealized_pl_pct:.1f}%
Risk Multiple: {abs(unrealized_pl_pct) / abs(((entry_price - position_data['stop_price']) / entry_price) * 100):.1f}R

Choose one of these actions and provide a clear reason:

1. HOLD - Keep position unchanged
2. EXIT - Close entire position
3. PARTIAL_EXIT - Reduce position size
4. ADJUST_STOPS - Modify stop loss

Respond in this EXACT format:
ACTION: [HOLD/EXIT/PARTIAL_EXIT/ADJUST_STOPS]
PARAMS: [parameters if needed]
REASON: [Clear explanation]"""

            response = await self._generate_llm_response(prompt)
            return self._parse_position_action(response)

        except Exception as e:
            self.logger.error(f"Error analyzing position: {str(e)}")
            return {'action': 'HOLD', 'params': None, 'reason': 'Error in analysis'}

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
                'reason': lines[-1].split(':')[1].strip()
            }
            return action
        except Exception as e:
            self.logger.error(f"Error parsing action: {str(e)}")
            return {'action': 'HOLD', 'params': None, 'reason': 'Parse error'}

    async def analyze_setup(self, data: Dict[str, Any]) -> Optional[str]:
        try:
            if not self._validate_data(data):
                return "NO SETUP"

            prompt = self._generate_setup_prompt(data)
            setup = await self._generate_llm_response(prompt)

            if self._validate_setup(setup, data):
                return setup
            return "NO SETUP"

        except Exception as e:
            self.logger.error(f"Setup analysis error: {str(e)}")
            return "NO SETUP"

    def _validate_data(self, data: Dict[str, Any]) -> bool:
        required = ['symbol', 'current_price']
        return all(data.get(field) for field in required)

    def _generate_setup_prompt(self, data: Dict[str, Any]) -> str:
        return f"""Analyze this stock data and provide a trading setup if valid.

STOCK DATA:
Symbol: {data['symbol']}
Price: ${data['current_price']:.2f}
RSI: {data.get('technical_indicators', {}).get('rsi', 'N/A')}
VWAP: ${data.get('technical_indicators', {}).get('vwap', 'N/A')}

Respond with setup in this format or 'NO SETUP':
TRADING SETUP: {data['symbol']}
Entry: $XX.XX
Target: $XX.XX
Stop: $XX.XX
Size: 100
Reason: Clear reason
Confidence: XX%
Risk-Reward: X:1"""

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
            
            current_price = data['current_price']
            if not (0.98 * current_price <= entry <= 1.02 * current_price):
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

    async def handle_position_action(self, symbol: str, action: Dict[str, Any], position: pd.Series, current_data: Dict[str, Any]):
        try:
            action_type = action['action'].upper()
            
            if action_type == 'HOLD':
                return

            elif action_type == 'EXIT':
                exit_data = {
                    'status': 'CLOSED',
                    'exit_price': current_data['current_price'],
                    'exit_time': datetime.now().isoformat(),
                    'profit_loss': (current_data['current_price'] - position['entry_price']) * position['position_size']
                }
                return exit_data

            elif action_type == 'PARTIAL_EXIT':
                current_size = position['position_size']
                exit_size = current_size // 2
                remaining = current_size - exit_size
                exit_pl = (current_data['current_price'] - position['entry_price']) * exit_size
                
                update_data = {
                    'position_size': remaining,
                    'partial_exit_price': current_data['current_price'],
                    'partial_exit_time': datetime.now().isoformat(),
                    'partial_exit_pl': exit_pl
                }
                return update_data

            elif action_type == 'ADJUST_STOPS':
                stop_type = action.get('params', {}).get('type', 'FIXED')
                value = action.get('params', {}).get('value', position['stop_price'])
                
                return {
                    'stop_price': value,
                    'stop_type': stop_type
                }

        except Exception as e:
            self.logger.error(f"Position action error: {str(e)}")
            return None
