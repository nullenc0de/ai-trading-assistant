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
        self.setup_cache = {}
        self.last_analysis_time = {}
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

    def _analyze_volume_profile(self, data: Dict[str, Any]) -> str:
        """Analyze volume profile with safety checks"""
        volume = data.get('volume_analysis', {}).get('current_volume', 0)
        avg_volume = data.get('volume_analysis', {}).get('avg_volume', 0)
        volume_ratio = data.get('volume_analysis', {}).get('volume_ratio', 0)
        market_cap = data.get('market_data', {}).get('market_cap', 0)
        beta = data.get('market_data', {}).get('beta', 0)
        
        return f"""- Current Volume: {volume:,}
- Average Volume: {avg_volume:,}
- Relative Volume: {volume_ratio:.1f}x
- Market Cap: ${market_cap:,}
- Beta: {beta:.2f}"""

    def generate_prompt(self, data: Dict[str, Any]) -> str:
        """Generate an enhanced prompt for LLM trading analysis"""
        ta_summary = self._generate_technical_summary(data)
        volume_analysis = self._analyze_volume_profile(data)

        prompt = f"""You are an expert AI stock trader. Analyze this stock data and if a valid trading setup exists, respond with it in the EXACT format shown below. If no valid setup exists, respond only with 'NO SETUP'.

SYMBOL ANALYSIS:
{ta_summary}

VOLUME PROFILE:
{volume_analysis}

Here is the EXACT format you must use for a trading setup. STRICTLY follow this format or respond with 'NO SETUP':

TRADING SETUP: {data['symbol']}
Entry: $XX.XX
Target: $XX.XX
Stop: $XX.XX
Size: 100
Reason: Clear and concise reason for trade
Confidence: 85%
Risk-Reward Ratio: 2.5:1

Required format rules:
1. Must include TRADING SETUP: followed by symbol
2. Entry/Target/Stop must use $ followed by price
3. Must include all seven lines exactly as shown
4. Entry price must be within 20% of current price
5. Risk-reward must be at least 2:1
6. Confidence must be between 0-100%

If you cannot format the response EXACTLY like this, respond with 'NO SETUP' instead.

Your response:"""

    async def analyze_setup(self, data: Dict[str, Any]) -> Optional[str]:
        """Get trading analysis from LLM with enhanced debugging"""
        symbol = data['symbol']
        current_time = datetime.now()

        try:
            # Basic data validation
            required_fields = ['current_price', 'symbol']
            if not all(data.get(field) for field in required_fields):
                self.logger.warning(f"Missing required data fields for {symbol}")
                return "NO SETUP"

            # Generate prompt
            prompt = self.generate_prompt(data)
            
            # Log the prompt for debugging
            self.logger.debug(f"Generated prompt for {symbol}:\n{prompt}")
            
            # Try multiple times if needed
            for attempt in range(self.max_retries):
                try:
                    response = ollama.generate(
                        model=self.model,
                        prompt=prompt,
                        options={
                            'temperature': 0.7,
                            'top_p': 0.9,
                            'max_tokens': 300,
                            'stop': ['\n\n', '\n\n\n']
                        }
                    )
                    
                    setup = response['response'].strip()
                    
                    # Log the raw response
                    self.logger.info(f"LLM Response for {symbol} (Attempt {attempt + 1}):\n{setup}")
                    
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
                entry_price = float(lines[1].split('$')[1].strip())
                target_price = float(lines[2].split('$')[1].strip())
                stop_price = float(lines[3].split('$')[1].strip())
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

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """Clear analysis cache"""
        if symbol:
            self.setup_cache.pop(symbol, None)
            self.last_analysis_time.pop(symbol, None)
            self.logger.info(f"Cleared cache for {symbol}")
        else:
            self.setup_cache.clear()
            self.last_analysis_time.clear()
            self.logger.info("Cleared all cache")
