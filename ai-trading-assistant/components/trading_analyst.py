import logging
from typing import Dict, Optional, Any
import ollama
from datetime import datetime

class TradingAnalyst:
    def __init__(self, performance_tracker, position_manager, model="llama3:latest", max_retries=3):
        self.model = model
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        self.performance_tracker = performance_tracker
        self.position_manager = position_manager

    async def analyze_position(self, stock_data: Dict[str, Any], position_data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            entry_price = position_data['entry_price']
            current_price = stock_data['current_price']
            position_size = position_data['size']
            
            unrealized_pl = (current_price - entry_price) * position_size
            unrealized_pl_pct = ((current_price / entry_price) - 1) * 100
            
            prompt = f"""Analyze position and decide next action:

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
3. PARTIAL_EXIT - Exit half position
4. ADJUST_STOPS - Move stops

Format:
ACTION: [action type]
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
