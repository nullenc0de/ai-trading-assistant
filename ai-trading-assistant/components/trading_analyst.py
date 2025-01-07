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
        """Analyze an existing position and determine action"""
        try:
            # Validate required data
            required_stock_fields = ['symbol', 'current_price']
            required_position_fields = ['entry_price', 'target_price', 'stop_price']
            
            if not all(field in stock_data for field in required_stock_fields):
                raise ValueError("Missing required stock data fields")
            if not all(field in position_data for field in required_position_fields):
                raise ValueError("Missing required position data fields")

            entry_price = float(position_data['entry_price'])
            current_price = float(stock_data['current_price'])
            position_size = float(position_data.get('size', 100))
            
            # Calculate position metrics
            unrealized_pl = (current_price - entry_price) * position_size
            unrealized_pl_pct = ((current_price / entry_price) - 1) * 100
            
            # Risk multiple calculation with validation
            stop_distance = abs(entry_price - float(position_data['stop_price']))
            if stop_distance > 0:
                risk_multiple = abs(unrealized_pl_pct) / abs((stop_distance / entry_price) * 100)
            else:
                risk_multiple = 0

            prompt = self._generate_position_prompt(
                stock_data, position_data, unrealized_pl, unrealized_pl_pct, risk_multiple
            )

            response = await self._generate_llm_response(prompt)
            self.logger.info(f"LLM Response for position analysis ({stock_data['symbol']}):\n{response}")
            
            action = self._parse_position_action(response)
            
            if action['action'] not in ['HOLD', 'EXIT', 'PARTIAL_EXIT', 'ADJUST_STOPS']:
                self.logger.warning(f"Invalid action type received: {action['action']}")
                action['action'] = 'HOLD'
            
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

    def _generate_position_prompt(self, stock_data: Dict[str, Any], position_data: Dict[str, Any],
                                unrealized_pl: float, unrealized_pl_pct: float, risk_multiple: float) -> str:
        """Generate position analysis prompt"""
        return f"""Analyze position and decide next action:

Position: {stock_data['symbol']}
Entry: ${position_data['entry_price']:.2f}
Current: ${stock_data['current_price']:.2f}
Target: ${position_data['target_price']:.2f}
Stop: ${position_data['stop_price']:.2f}
Size: {position_data.get('size', 100)}
P&L: ${unrealized_pl:.2f} ({unrealized_pl_pct:.1f}%)
Risk Multiple: {risk_multiple:.1f}R

Technical:
RSI: {stock_data.get('technical_indicators', {}).get('rsi', 'N/A')}
VWAP: ${stock_data.get('technical_indicators', {}).get('vwap', 'N/A')}
ATR: {stock_data.get('technical_indicators', {}).get('atr', 'N/A')}

Choose action:
1. HOLD - Keep position
2. EXIT - Close position
3. PARTIAL_EXIT - Exit half position
4. ADJUST_STOPS - Move stops

Format response exactly as:
ACTION: [action type]
PARAMS: [parameters if needed]
REASON: [single line explanation]"""

    async def analyze_setup(self, stock_data: Dict[str, Any]) -> str:
        """Analyze potential new trading setup"""
        try:
            # Validate stock data
            if not isinstance(stock_data, dict) or 'symbol' not in stock_data:
                return "NO SETUP FOUND"

            prompt = f"""Analyze the following stock data and determine if there is a valid trading setup:

{json.dumps(stock_data, indent=2, default=str)}

Respond with a trading setup in the following format if a high-confidence setup is found:

Symbol: [symbol]
Entry: $[entry price]
Target: $[price target]
Stop: $[stop loss]
Size: [position size]
Confidence: [numeric confidence percentage]
Risk/Reward:
