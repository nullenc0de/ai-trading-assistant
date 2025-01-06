import logging
import re
from typing import Dict, Any
import ollama
from datetime import datetime
import json

class TradingAnalyst:
    def __init__(self, performance_tracker, position_manager, model="llama3:latest", max_retries=3):
        """
        Initialize the TradingAnalyst with performance tracking and position management.

        :param performance_tracker: Object to track trading performance
        :param position_manager: Object to manage trading positions
        :param model: Ollama model to use for analysis (default: llama3:latest)
        :param max_retries: Maximum number of retry attempts for LLM generation
        """
        self.model = model
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)
        self.performance_tracker = performance_tracker
        self.position_manager = position_manager

    async def analyze_position(self, stock_data: Dict[str, Any], position_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze an existing trading position and determine next action.

        :param stock_data: Current stock market data
        :param position_data: Current position details
        :return: Recommended action for the position
        """
        try:
            entry_price = position_data['entry_price']
            current_price = stock_data['current_price']
            
            # Robust size handling
            position_size = position_data['size']
            if isinstance(position_size, str):
                try:
                    # Handle percentage or fixed size
                    if '%' in position_size.lower():
                        matches = re.findall(r'([\d.]+)\s*%', position_size)
                        position_size = float(matches[0]) if matches else 100
                    else:
                        position_size = float(re.findall(r'[\d.]+', position_size)[0])
                except ValueError:
                    self.logger.warning(f"Invalid position size: {position_size}. Defaulting to 100.")
                    position_size = 100
            
            # Ensure position_size is a numeric value
            position_size = float(position_size)
            
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
            return {'action': 'HOLD','reason': 'Analysis error'}

    async def analyze_setup(self, stock_data: Dict[str, Any]) -> str:
        """
        Analyze stock data to detect potential trading setups.

        :param stock_data: Stock market and technical data
        :return: Detailed trading setup or 'NO SETUP FOUND'
        """
        try:
            prompt = f"""Analyze the following stock data and determine if there is a valid trading setup:

{json.dumps(stock_data, indent=2, default=str)}

Respond with a trading setup in the following format if a high-confidence setup is found:

Symbol: [symbol]
Entry: $[entry price]  
Target: $[price target]
Stop: $[stop loss]
Size: [position size as percentage or fixed amount]
Confidence: [numeric confidence percentage, not followed by %]
Risk/Reward: [risk/reward ratio]  
Reason: [detailed explanation]

Important: Do not include '%' with Confidence. Use a numeric value only.
"""
            response = await self._generate_llm_response(prompt)
            return response
    
        except Exception as e:
            self.logger.error(f"Setup analysis error: {str(e)}")
            return "NO SETUP FOUND"

    async def _generate_llm_response(self, prompt: str) -> str:
        """
        Generate a response from the language model.

        :param prompt: Input prompt for the language model
        :return: Generated response text
        """
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
        """
        Parse the LLM response into a structured action.

        :param response: Raw response text from the language model
        :return: Parsed action dictionary
        """
        try:
            lines = response.split('\n')
            if not lines:
                self.logger.error("Unexpected response format: response is empty")
                return {'action': 'HOLD','reason': 'Parse error: Empty response'}

            action_line = lines[0].split(':')
            if len(action_line) < 2:
                self.logger.error(f"Invalid action line: {lines[0]}")
                return {'action': 'HOLD','reason': 'Parse error: Invalid action line'}

            action_type = action_line[1].strip()

            params_line = None
            if len(lines) > 1 and 'PARAMS:' in lines[1]:
                params_line = lines[1].split(':')
                if len(params_line) < 2:
                    self.logger.error(f"Invalid params line: {lines[1]}")
                else:
                    params = params_line[1].strip()

            reason_line = lines[-1].split(':')
            if len(reason_line) < 2:
                self.logger.error(f"Invalid reason line: {lines[-1]}")
            else:
                reason = reason_line[1].strip()

            return {'action': action_type, 'params': params,'reason': reason}

        except IndexError as e:
            self.logger.error(f"IndexError during parsing: {str(e)}")
            return {'action': 'HOLD','reason': 'Parse error: IndexError'}
        except ValueError as e:
            self.logger.error(f"ValueError during parsing: {str(e)}")
            return {'action': 'HOLD','reason': 'Parse error: ValueError'}

    def _parse_setup(self, response: str) -> Dict[str, Any]:
        """
        Parse trading setup with robust handling of percentage values
        
        Args:
            response (str): Raw setup response
        
        Returns:
            dict: Parsed setup details
        """
        try:
            setup = {}
            lines = response.strip().split('\n')
            
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    
                    # Handle percentage parsing
                    if 'confidence' in key:
# Remove % sign and convert to float
                        value = value.rstrip('%')
                        try:
                            setup['confidence'] = float(value)
                        except ValueError:
                            self.logger.warning(f"Invalid confidence value: {value}")
                    
                    # Handle currency values
                    elif any(prefix in key for prefix in ['entry', 'target','stop']):
                        # Remove $ sign and convert to float
                        value = value.lstrip('$')
                        try:
                            setup[key.replace(' ', '_')] = float(value)
                        except ValueError:
                            self.logger.warning(f"Invalid price value for {key}: {value}")
                    
                    # Handle size with percentage support
                    elif'size' in key:
                        try:
                            # Handle percentage or fixed size
                            if '%' in value.lower():
                                matches = re.findall(r'([\d.]+)\s*%', value)
                                setup['size'] = float(matches[0]) if matches else 100
                            else:
                                # Try to extract numeric value
                                setup['size'] = float(re.findall(r'[\d.]+', value)[0])
                        except ValueError:
                            self.logger.warning(f"Invalid size value: {value}")
                            setup['size'] = value  # Keep the original value even if invalid
                    
                    # Handle risk/reward
                    elif 'risk/reward' in key:
                        try:
                            setup['risk_reward'] = float(value)
                        except ValueError:
                            self.logger.warning(f"Invalid risk/reward value: {value}")
                    
                    # Handle reason or other text fields
                    elif'reason' in key:
                        setup['reason'] = value
                    
                    # Fallback for other numeric or text values
                    else:
                        try:
                            setup[key.replace(' ', '_')] = float(value)
                        except ValueError:
                            setup[key.replace(' ', '_')] = value
            
            return setup
        
        except Exception as e:
            self.logger.error(f"Setup parsing error: {str(e)}")
            return {}
