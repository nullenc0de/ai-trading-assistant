"""
Trading Analyst Module
--------------------
Analyzes market data and makes trading decisions using LLM.
Includes position analysis, setup detection, and risk management.

Author: AI Trading Assistant
Version: 2.1
Last Updated: 2025-01-07
"""

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

    def _should_force_exit(self, current_price: float, position_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if position requires forced exit based on risk management rules"""
        try:
            entry_price = float(position_data['entry_price'])
            stop_price = float(position_data['stop_price'])
            
            # Check stop loss violation
            if current_price <= stop_price:
                return {
                    'action': 'EXIT',
                    'reason': f'Stop loss violated: Current price ${current_price:.2f} at or below stop ${stop_price:.2f}'
                }
            
            # Check adverse move (loss > 2%)
            loss_percent = ((current_price - entry_price) / entry_price) * 100
            if loss_percent < -2.0:
                return {
                    'action': 'EXIT',
                    'reason': f'Large adverse move: Position down {abs(loss_percent):.1f}%'
                }
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking force exit conditions: {str(e)}")
            return None

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

            current_price = float(stock_data['current_price'])
            
            # First check for forced exit conditions
            force_exit = self._should_force_exit(current_price, position_data)
            if force_exit:
                self.logger.info(f"Forced exit for {stock_data['symbol']}: {force_exit['reason']}")
                return force_exit

            entry_price = float(position_data['entry_price'])
            position_size = float(position_data.get('size', 100))
            
            # Calculate position metrics
            unrealized_pl = (current_price - entry_price) * position_size
            unrealized_pl_pct = ((current_price - entry_price) / entry_price) * 100
            
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
            
            # Parse and validate LLM action
            action = self._parse_position_action(response)
            
            # Override HOLD if conditions warrant
            if action['action'] == 'HOLD':
                # Exit if we're very close to stop loss (within 10% of distance)
                stop_buffer = (current_price - float(position_data['stop_price'])) / stop_distance
                if stop_buffer < 0.1:
                    action = {
                        'action': 'EXIT',
                        'reason': f'Too close to stop loss (buffer: {stop_buffer:.1%})'
                    }
                
                # Exit if we're down more than 1.5%
                elif unrealized_pl_pct < -1.5:
                    action = {
                        'action': 'EXIT',
                        'reason': f'Position down {abs(unrealized_pl_pct):.1f}%'
                    }
            
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
        return f"""Analyze position and decide next action. BE AGGRESSIVE about cutting losses - exit if down more than 1.5% or near stop loss.

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
1. HOLD - Keep position (only if confident of upside)
2. EXIT - Close position (default choice if any doubt)
3. PARTIAL_EXIT - Exit half position (for reducing risk)
4. ADJUST_STOPS - Move stops (only higher, never lower)

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

            prompt = f"""Analyze the following stock data and determine if there is a valid trading setup.
BE VERY SELECTIVE - only identify high probability setups with clear risk/reward.

{json.dumps(stock_data, indent=2, default=str)}

Respond with a trading setup in the following format ONLY if you find a high-confidence setup with:
- Clear support/resistance levels
- At least 2:1 reward/risk ratio
- Strong technical confirmation
- Clear stop loss level
- Limited downside risk

Format:
Symbol: [symbol]
Entry: $[entry price]
Target: $[price target]
Stop: $[stop loss]
Size: [position size - use 0.5% to 2% of account]
Confidence: [numeric confidence percentage]
Risk/Reward: [risk/reward ratio]
Reason: [detailed explanation]

If no valid setup is found, respond only with: NO SETUP FOUND"""

            response = await self._generate_llm_response(prompt)
            self.logger.info(f"LLM Response for setup analysis ({stock_data['symbol']}):\n{response}")
            
            # Validate the response format
            if "NO SETUP FOUND" in response:
                return response
                
            # Verify that all required fields are present
            required_fields = ['Symbol:', 'Entry:', 'Target:', 'Stop:', 'Confidence:']
            if not all(field in response for field in required_fields):
                self.logger.warning(f"Invalid setup format for {stock_data['symbol']}")
                return "NO SETUP FOUND"
            
            return response
    
        except Exception as e:
            self.logger.error(f"Setup analysis error: {str(e)}")
            return "NO SETUP FOUND"

    def _parse_position_action(self, response: str) -> Dict[str, Any]:
        """Parse LLM response for position action"""
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
                    value = value.upper()
                    if value in ['HOLD', 'EXIT', 'PARTIAL_EXIT', 'ADJUST_STOPS']:
                        action_dict['action'] = value
                elif key == 'PARAMS':
                    if action_dict['action'] == 'ADJUST_STOPS':
                        try:
                            if '=' in value:
                                stop_value = float(value.split('=')[1].strip())
                            else:
                                stop_value = float(value.strip())
                            # Ensure new stop is valid
                            action_dict['params'] = str(stop_value)
                        except ValueError:
                            self.logger.error(f"Invalid stop price parameter: {value}")
                            action_dict['action'] = 'HOLD'
                    else:
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

    async def _generate_llm_response(self, prompt: str) -> str:
        """Generate response from LLM with retries"""
        try:
            for attempt in range(self.max_retries):
                try:
                    response = ollama.generate(
                        model=self.model,
                        prompt=prompt,
                        options={
                            'temperature': 0.2,
                            'num_predict': 300
                        }
                    )
                    return response.get('response', '').strip()
                except Exception as e:
                    if attempt == self.max_retries - 1:
                        raise
                    self.logger.warning(f"LLM attempt {attempt + 1} failed: {str(e)}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"LLM error after {self.max_retries} attempts: {str(e)}")
            return ""
