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
                            'temperature': 0.2,     # More focused responses
                            'num_predict': 150,     # Keep responses concise
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
            self.logger.error(f"Setup validation error: {str(e)}\nSetup text: {setup}")
            return False
