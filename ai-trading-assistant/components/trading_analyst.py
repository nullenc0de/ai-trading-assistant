import logging
import re
from typing import Dict, Any, Optional
import ollama
from datetime import datetime
import json

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
            
            position_size = float(position_data.get('size', 100))
            
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

Format response exactly as:
ACTION: [action type]
PARAMS: [parameters if needed]
REASON: [single line explanation]"""

            response = await self._generate_llm_response(prompt)
            self.logger.info(f"LLM Response for position analysis ({stock_data['symbol']}):\n{response}")
            
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
            return {'action': 'HOLD', 'params': None, 'reason': f'Analysis error: {str(e)}'}

    def _parse_position_action(self, response: str) -> Dict[str, Any]:
        try:
            action_dict = {
                'action': 'HOLD',
                'params': None,
                'reason': 'Default hold due to parsing error'
            }
            
            lines = [line.strip() for line in response.split('\n') if line.strip()]
            
            for line in lines:
                if ':' not in line:
                    continue
                    
                key, value = [part.strip() for part in line.split(':', 1)]
                key = key.upper()
                
                if key == 'ACTION':
                    action_dict['action'] = value.upper()
                elif key == 'PARAMS':
                    action_dict['params'] = value
                elif key == 'REASON':
                    action_dict['reason'] = value

            return action_dict

        except Exception as e:
            self.logger.error(f"Action parsing error: {str(e)}")
            return {
                'action': 'HOLD',
                'params': None,
                'reason': f'Parse error: {str(e)}'
            }

    async def analyze_setup(self, stock_data: Dict[str, Any]) -> str:
        try:
            prompt = f"""Analyze the following stock data and determine if there is a valid trading setup:

{json.dumps(stock_data, indent=2, default=str)}

Respond with a trading setup in the following format if a high-confidence setup is found:

Symbol: [symbol]
Entry: $[entry price]  
Target: $[price target]
Stop: $[stop loss]
Size: [position size as percentage or fixed amount]
Confidence: [numeric confidence percentage]
Risk/Reward: [risk/reward ratio]  
Reason: [detailed explanation]

If no valid setup is found, respond only with: NO SETUP FOUND
"""
            response = await self._generate_llm_response(prompt)
            self.logger.info(f"LLM Response for setup analysis ({stock_data['symbol']}):\n{response}")
            return response
    
        except Exception as e:
            self.logger.error(f"Setup analysis error: {str(e)}")
            return "NO SETUP FOUND"

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
