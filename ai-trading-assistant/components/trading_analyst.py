# components/trading_analyst.py
import ollama
import logging
from typing import Dict, Optional, Any
import asyncio
from datetime import datetime

class TradingAnalyst:
    def __init__(self, model="llama3:latest", max_retries=3):
        """Initialize Trading Analyst"""
        self.model = model
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    def _generate_technical_summary(self, data: Dict[str, Any]) -> str:
        """Generate technical analysis summary with safety checks"""
        price = data.get('current_price', 0)
        rsi = data.get('technical_indicators', {}).get('rsi', 'N/A')
        vwap = data.get('technical_indicators', {}).get('vwap', 'N/A')
        sma20 = data.get('technical_indicators', {}).get('sma20', 'N/A')
        ema9 = data.get('technical_indicators', {}).get('ema9', 'N/A')
        atr = data.get('technical_indicators', {}).get('atr', 'N/A')
        
        return f"""TECHNICAL INDICATORS:
- Price: ${price:.2f}
- RSI: {rsi if rsi != 'N/A' else 'Not Available'}
- VWAP: ${vwap if vwap != 'N/A' else 'Not Available'}
- SMA20: ${sma20 if sma20 != 'N/A' else 'Not Available'}
- EMA9: ${ema9 if ema9 != 'N/A' else 'Not Available'}
- ATR: {atr if atr != 'N/A' else 'Not Available'}"""

    def generate_prompt(self, data: Dict[str, Any]) -> str:
        """Generate an enhanced prompt for LLM trading analysis"""
        return f"""You are a skilled stock trader. Analyze this data and provide a trading setup if valid.

CURRENT STOCK DATA:
Symbol: {data['symbol']}
Price: ${data['current_price']:.2f}
RSI: {data.get('technical_indicators', {}).get('rsi', 'N/A')}
VWAP: ${data.get('technical_indicators', {}).get('vwap', 'N/A')}

Respond with a trading setup EXACTLY like this example or 'NO SETUP':

TRADING SETUP: {data['symbol']}
Entry: $XX.XX
Target: $XX.XX
Stop: $XX.XX
Size: X
Reason: One clear reason for the trade
Confidence: XX%
Risk-Reward Ratio: X:1

RULES:
1. Entry must be within 2% of current price
2. Risk-Reward ratio must be at least 2:1
3. Size must be 100 shares for now
4. Must include all fields exactly as shown

Your response:"""

    async def analyze_position(self, stock_data: Dict[str, Any], position_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze existing position and recommend state transition"""
        try:
            # Generate position analysis prompt
            prompt = f"""You are managing an existing trading position. Analyze the current market conditions and decide the next state transition.

POSITION STATUS:
Symbol: {stock_data['symbol']}
Entry Price: ${position_data['entry_price']:.2f}
Current Price: ${position_data['current_price']:.2f}
Target Price: ${position_data['target_price']:.2f}
Stop Price: ${position_data['stop_price']:.2f}
Position Size: {position_data['size']} shares
Hours Held: {position_data['time_held']:.1f}

CURRENT TECHNICAL DATA:
Price: ${stock_data['current_price']:.2f}
RSI: {stock_data.get('technical_indicators', {}).get('rsi', 'N/A')}
VWAP: ${stock_data.get('technical_indicators', {}).get('vwap', 'N/A')}

Unrealized P&L: ${(position_data['current_price'] - position_data['entry_price']) * position_data['size']:.2f}
Unrealized P&L %: {((position_data['current_price'] / position_data['entry_price']) - 1) * 100:.1f}%

Choose one of these actions and provide a clear reason:
1. HOLD - Keep the position unchanged
2. EXIT - Close the entire position
3. PARTIAL_EXIT - Specify exit_percentage (e.g., 0.5 for 50%)
4. ADJUST_STOPS - Provide new_stop price

Factors to consider:
- Position profitability and risk/reward
- Technical indicators and trend
- Time held vs typical holding period
- Price action relative to key levels

Respond in this EXACT format:
ACTION: [action type]
PARAMS: [additional parameters if needed]
REASON: [One clear reason for this action]

Your analysis and decision:"""

            # Get LLM response
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    'temperature': 0.2,
                    'num_predict': 150
                }
            )
            
            action_text = response.get('response', '').strip()
            self.logger.info(f"Position analysis for {stock_data['symbol']}:\n{action_text}")
            
            # Parse action
            try:
                lines = action_text.split('\n')
                action = {
                    'action': lines[0].split(':')[1].strip(),
                    'reason': lines[-1].split(':')[1].strip()
                }
                
                # Parse additional parameters if present
                if 'PARAMS:' in action_text:
                    params_line = [l for l in lines if 'PARAMS:' in l][0]
                    params_str = params_line.split(':')[1].strip()
                    
                    # Parse parameters
                    if 'exit_percentage' in params_str:
                        action['exit_percentage'] = float(params_str.split('=')[1].strip())
                    elif 'new_stop' in params_str:
                        action['new_stop'] = float(params_str.split('=')[1].strip())
                
                return action
                
            except Exception as e:
                self.logger.error(f"Error parsing position action: {str(e)}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error analyzing position: {str(e)}")
            return None

    async def analyze_setup(self, data: Dict[str, Any]) -> Optional[str]:
        """Get trading analysis from LLM with enhanced debugging"""
        symbol = data['symbol']

        try:
            # Basic data validation
            required_fields = ['current_price', 'symbol']
            if not all(data.get(field) for field in required_fields):
                self.logger.warning(f"Missing required data fields for {symbol}")
                return "NO SETUP"

            # Generate prompt
            prompt = self.generate_prompt(data)
            
            # Log the prompt for debugging
            self.logger.info(f"Sending prompt for {symbol}:\n{prompt}")
            
            # Try multiple times if needed
            for attempt in range(self.max_retries):
                try:
                    response = ollama.generate(
                        model=self.model,
                        prompt=prompt,
                        options={
                            'temperature': 0.2,
                            'num_predict': 150,
                            'top_k': 10,
                            'top_p': 0.5
                        }
                    )
                    
                    setup = response.get('response', '').strip()
                    
                    # Log the raw response
                    self.logger.info(f"LLM Response for {symbol} (Attempt {attempt + 1}):\n{setup}")
                    
                    if not setup:
                        self.logger.warning(f"Empty response for {symbol} on attempt {attempt + 1}")
                        continue
                        
                    # Basic format check
                    if not setup.startswith('TRADING SETUP:') and setup != 'NO SETUP':
                        self.logger.warning(f"Invalid response format for {symbol} on attempt {attempt + 1}")
                        if attempt == self.max_retries - 1:
                            return "NO SETUP"
                        continue
                    
                    # Validate setup
                    if setup == 'NO SETUP' or self._validate_setup(setup, data):
                        return setup
                    
                    if attempt == self.max_retries - 1:
                        self.logger.warning(f"All validation attempts failed for {symbol}")
                        return "NO SETUP"
                        
                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} failed for {symbol}: {str(e)}")
                    if attempt == self.max_retries - 1:
                        return "NO SETUP"
                    await asyncio.sleep(1)  # Brief pause between retries
                    
        except Exception as e:
            self.logger.error(f"Error analyzing setup for {symbol}: {str(e)}")
            return "NO SETUP"

    def _validate_setup(self, setup: str, data: Dict[str, Any]) -> bool:
        """Validate trading setup meets requirements"""
        try:
            if setup == 'NO SETUP':
                return True
            
            # Log the setup being validated
            self.logger.debug(f"Validating setup: {setup}")
            
            # Split into lines and check minimum length
            lines = setup.split('\n')
            if len(lines) < 7:  # Need at least 7 lines for a valid setup
                self.logger.warning("Setup has insufficient lines")
                return False
            
            # Extract values with better error handling
            try:
                for line in lines:
                    if 'Entry:' in line:
                        entry_price = float(line.split('$')[1].strip())
                    elif 'Target:' in line:
                        target_price = float(line.split('$')[1].strip())
                    elif 'Stop:' in line:
                        stop_price = float(line.split('$')[1].strip())
            except (IndexError, ValueError) as e:
                self.logger.warning(f"Error parsing price values: {e}")
                return False
            
            # Validate prices are reasonable
            current_price = data['current_price']
            if not (0.8 * current_price <= entry_price <= 1.2 * current_price):
                self.logger.warning(f"Entry price {entry_price} too far from current price {current_price}")
                return False
            
            # Validate risk/reward
            risk = abs(entry_price - stop_price)
            reward = abs(target_price - entry_price)
            if risk == 0:
                self.logger.warning("Zero risk (entry price equals stop price)")
                return False
                
            risk_reward = reward / risk
            if risk_reward < 2:  # Minimum 2:1 reward/risk
                self.logger.warning(f"Risk/reward ratio {risk_reward} below minimum")
                return False
            
            return True
            
        except Exception as e:
            self
