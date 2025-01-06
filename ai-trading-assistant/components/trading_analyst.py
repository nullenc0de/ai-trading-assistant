import ollama
import logging
from typing import Dict, Optional, Any
import asyncio
from datetime import datetime

class TradingAnalyst:
    def __init__(self, model="llama3:latest", max_retries=3):
        self.model = model
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    def _generate_technical_summary(self, data: Dict[str, Any]) -> str:
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
        try:
            entry_price = position_data['entry_price']
            current_price = position_data['current_price']
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

1. HOLD - Keep the position unchanged

2. EXIT - Close the entire position

3. PARTIAL_EXIT - Advanced profit taking
   Parameters needed:
   - exit_percentage: Portion to exit (e.g., 0.5 for 50%)
   - scale_points: Price levels for scaling out [price1, price2]
   - sizes: Portion at each scale point [size1, size2]

4. ADJUST_STOPS - Advanced stop management
   Parameters needed:
   - type: FIXED, TRAILING, or BREAKEVEN
   - value: New stop price for FIXED, percentage for TRAILING, buffer for BREAKEVEN

Respond in this EXACT format:
ACTION: [action type]
PARAMS: [parameters if needed]
REASON: [Clear explanation incorporating multiple factors]

Your analysis and decision:"""

            response = await self._generate_llm_response(prompt)
            action_text = response.strip()
            
            try:
                lines = action_text.split('\n')
                action = {
                    'action': lines[0].split(':')[1].strip(),
                    'params': lines[1].split(':')[1].strip() if len(lines) > 1 and 'PARAMS:' in lines[1] else None,
                    'reason': lines[-1].split(':')[1].strip()
                }
                return action
                
            except Exception as e:
                self.logger.error(f"Error parsing position action: {str(e)}")
                return None

        except Exception as e:
            self.logger.error(f"Error analyzing position: {str(e)}")
            return None

    async def analyze_setup(self, data: Dict[str, Any]) -> Optional[str]:
        symbol = data['symbol']

        try:
            required_fields = ['current_price', 'symbol']
            if not all(data.get(field) for field in required_fields):
                self.logger.warning(f"Missing required data fields for {symbol}")
                return "NO SETUP"

            prompt = self.generate_prompt(data)
            self.logger.info(f"Sending prompt for {symbol}:\n{prompt}")
            
            for attempt in range(self.max_retries):
                try:
                    response = await self._generate_llm_response(prompt)
                    setup = response.strip()
                    
                    self.logger.info(f"LLM Response for {symbol} (Attempt {attempt + 1}):\n{setup}")
                    
                    if not setup:
                        continue
                        
                    if not setup.startswith('TRADING SETUP:') and setup != 'NO SETUP':
                        if attempt == self.max_retries - 1:
                            return "NO SETUP"
                        continue
                    
                    if setup == 'NO SETUP' or self._validate_setup(setup, data):
                        return setup
                    
                    if attempt == self.max_retries - 1:
                        return "NO SETUP"
                        
                except Exception as e:
                    self.logger.error(f"Attempt {attempt + 1} failed for {symbol}: {str(e)}")
                    if attempt == self.max_retries - 1:
                        return "NO SETUP"
                    await asyncio.sleep(1)
                    
        except Exception as e:
            self.logger.error(f"Error analyzing setup for {symbol}: {str(e)}")
            return "NO SETUP"

    async def _generate_llm_response(self, prompt: str) -> str:
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
            
            return response.get('response', '').strip()
            
        except Exception as e:
            self.logger.error(f"Error generating LLM response: {str(e)}")
            return ""

    def _validate_setup(self, setup: str, data: Dict[str, Any]) -> bool:
        try:
            if setup == 'NO SETUP':
                return True
            
            self.logger.debug(f"Validating setup: {setup}")
            
            lines = setup.split('\n')
            if len(lines) < 7:
                self.logger.warning("Setup has insufficient lines")
                return False
            
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
            
            current_price = data['current_price']
            if not (0.8 * current_price <= entry_price <= 1.2 * current_price):
                self.logger.warning(f"Entry price {entry_price} too far from current price {current_price}")
                return False
            
            risk = abs(entry_price - stop_price)
            reward = abs(target_price - entry_price)
            if risk == 0:
                self.logger.warning("Zero risk (entry price equals stop price)")
                return False
                
            risk_reward = reward / risk
            if risk_reward < 2:
                self.logger.warning(f"Risk/reward ratio {risk_reward} below minimum")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating setup: {str(e)}")
            return False
