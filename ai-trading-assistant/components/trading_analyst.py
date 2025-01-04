# components/trading_analyst.py
import ollama
import logging
import json
from typing import Dict, Optional, Any
import asyncio
from datetime import datetime

class TradingAnalyst:
    def __init__(self, model="llama3:latest", max_retries=3):
        """
        Initialize Trading Analyst with enhanced LLM configuration
        
        Args:
            model (str): LLM model to use for trading analysis
            max_retries (int): Maximum number of retries for LLM generation
        """
        self.model = model
        self.max_retries = max_retries
        self.setup_cache = {}
        self.last_analysis_time = {}

    def generate_prompt(self, data: Dict[str, Any]) -> str:
        """
        Generate an enhanced prompt for LLM trading analysis
        
        Args:
            data (dict): Stock analysis data
        
        Returns:
            str: Formatted prompt for LLM
        """
        # Technical Analysis Summary
        ta_summary = self._generate_technical_summary(data)
        
        # Volume Profile Analysis
        volume_analysis = self._analyze_volume_profile(data)
        
        # Market Context
        market_context = self._generate_market_context(data)

        prompt = f"""Act as an expert day trader and systematic risk manager focused on technical analysis and price action.
Analyze this stock for a potential day trade setup, prioritizing risk management and clear entry/exit points.

SYMBOL ANALYSIS:
{ta_summary}

VOLUME PROFILE:
{volume_analysis}

MARKET CONTEXT:
{market_context}

TRADING DECISION FRAMEWORK:
1. Validate trend alignment across timeframes
2. Confirm volume supports price action
3. Identify key support/resistance levels
4. Calculate precise entry/exit points
5. Determine position size based on risk
6. Assess overall setup probability

Provide a trading setup following this EXACT format (or respond with 'NO SETUP'):
TRADING SETUP: {data['symbol']}
Entry: $PRICE
Target: $PRICE
Stop: $PRICE
Size: # shares
Reason: [Concise trading rationale]
Confidence: [0-100%]
Risk-Reward Ratio: X:1

Additional Rules:
- Minimum 2:1 reward-risk ratio required
- Entry must be within 2% of current price
- Confidence must be justified by specific technical factors
- Size must respect position limits and volatility"""

        return prompt

    def _generate_technical_summary(self, data: Dict[str, Any]) -> str:
        """Generate technical analysis summary"""
        return f"""TECHNICAL INDICATORS:
- Price: ${data['current_price']:.2f}
- RSI: {data['rsi']:.2f} (Momentum)
- VWAP: ${data['vwap']:.2f} (Institutional reference)
- SMA20: ${data['sma20']:.2f} (Trend)
- EMA9: ${data['ema9']:.2f} (Short-term trend)
- ATR: ${data['atr']:.2f} (Volatility)"""

    def _analyze_volume_profile(self, data: Dict[str, Any]) -> str:
        """Analyze volume profile and trading activity"""
        rel_volume = data['volume'] / data['avg_volume'] if data['avg_volume'] > 0 else 0
        
        return f"""- Current Volume: {data['volume']:,}
- Average Volume: {data['avg_volume']:,}
- Relative Volume: {rel_volume:.1f}x
- Market Cap: ${data['market_cap']:,}
- Beta: {data['beta']:.2f}"""

    def _generate_market_context(self, data: Dict[str, Any]) -> str:
        """Generate broader market context"""
        recent_price = data['recent_price_action'][-5:]  # Last 5 periods
        
        price_changes = [
            (bar['Close'] - bar['Open']) / bar['Open'] * 100 
            for bar in recent_price
        ]
        
        return f"""RECENT PRICE ACTION:
- Last 5 Periods: {', '.join([f'{chg:.1f}%' for chg in price_changes])}
- Average Range: ${sum([bar['High'] - bar['Low'] for bar in recent_price]) / 5:.2f}
- Volume Trend: {'Increasing' if recent_price[-1]['Volume'] > recent_price[0]['Volume'] else 'Decreasing'}"""

    def _validate_setup(self, setup: str, data: Dict[str, Any]) -> bool:
        """
        Validate trading setup meets requirements
        
        Args:
            setup (str): Trading setup
            data (dict): Stock data
            
        Returns:
            bool: True if setup is valid
        """
        try:
            if 'NO SETUP' in setup:
                return True
                
            # Parse setup
            lines = setup.split('\n')
            entry_price = float(lines[1].split('$')[1])
            target_price = float(lines[2].split('$')[1])
            stop_price = float(lines[3].split('$')[1])
            confidence = float(lines[6].split(':')[1].strip().rstrip('%'))
            
            # Calculate risk-reward
            risk = abs(entry_price - stop_price)
            reward = abs(target_price - entry_price)
            risk_reward = reward / risk if risk > 0 else 0
            
            # Validation rules
            current_price = data['current_price']
            price_valid = abs(entry_price - current_price) / current_price <= 0.02
            risk_reward_valid = risk_reward >= 2.0
            confidence_valid = 0 <= confidence <= 100
            
            return all([price_valid, risk_reward_valid, confidence_valid])
            
        except Exception as e:
            logging.error(f"Setup validation error: {str(e)}")
            return False

    async def analyze_setup(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Get trading analysis from Local Language Model with caching and rate limiting
        
        Args:
            data (dict): Stock analysis data
            
        Returns:
            str: Trading setup or None on failure
        """
        symbol = data['symbol']
        current_time = datetime.now()

        # Check cache first
        if symbol in self.setup_cache:
            cache_time, cache_data = self.setup_cache[symbol]
            if (current_time - cache_time).seconds < 300:  # 5-minute cache
                return cache_data

        # Rate limiting
        if symbol in self.last_analysis_time:
            time_since_last = (current_time - self.last_analysis_time[symbol]).seconds
            if time_since_last < 60:  # 1-minute minimum between analyses
                await asyncio.sleep(60 - time_since_last)

        for attempt in range(self.max_retries):
            try:
                # Generate prompt
                prompt = self.generate_prompt(data)
                
                # Call LLM
                response = ollama.generate(
                    model=self.model,
                    prompt=prompt,
                    options={
                        'temperature': 0.7,
                        'top_p': 0.9,
                        'max_tokens': 300,
                        'stop': ['NO SETUP', 'Risk-Reward Ratio:']
                    }
                )
                
                # Extract and validate response
                setup = response['response'].strip()
                
                # Validate setup
                if setup == 'NO SETUP' or (
                    'TRADING SETUP:' in setup and 
                    self._validate_setup(setup, data)
                ):
                    # Update cache and timing
                    self.setup_cache[symbol] = (current_time, setup)
                    self.last_analysis_time[symbol] = current_time
                    return setup
                
                logging.warning(f"Invalid setup generated: {setup}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)  # Brief pause before retry
                
            except Exception as e:
                logging.error(f"LLM analysis attempt {attempt + 1} failed: {str(e)}")
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    return None
        
        return None

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear analysis cache for a symbol or all symbols
        
        Args:
            symbol (str, optional): Specific symbol to clear, or None for all
        """
        if symbol:
            self.setup_cache.pop(symbol, None)
            self.last_analysis_time.pop(symbol, None)
        else:
            self.setup_cache.clear()
            self.last_analysis_time.clear()
            
        logging.info(f"Cleared cache for {'all symbols' if symbol is None else symbol}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            dict: Cache statistics
        """
        current_time = datetime.now()
        
        return {
            'cache_size': len(self.setup_cache),
            'cached_symbols': list(self.setup_cache.keys()),
            'cache_age': {
                symbol: (current_time - timestamp).seconds
                for symbol, (timestamp, _) in self.setup_cache.items()
            }
        }
