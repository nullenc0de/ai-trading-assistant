# components/trading_analyst.py
import ollama
import logging
import json

class TradingAnalyst:
    def __init__(self, model="llama3:latest", max_retries=3):
        """
        Initialize Trading Analyst with LLM configuration
        
        Args:
            model (str): LLM model to use for trading analysis
            max_retries (int): Maximum number of retries for LLM generation
        """
        self.model = model
        self.max_retries = max_retries

    def generate_prompt(self, data):
        """
        Generate a comprehensive prompt for LLM trading analysis
        
        Args:
            data (dict): Stock analysis data
        
        Returns:
            str: Formatted prompt for LLM
        """
        prompt = f"""Act as an expert day trader and systematic risk manager. 
Analyze this stock for a potential day trade setup with a focus on disciplined risk management.

SYMBOL DETAILS:
- Symbol: {data['symbol']}
- Current Price: ${data['current_price']:.2f}

TECHNICAL INDICATORS:
1. RSI (Relative Strength Index): {data['rsi']:.2f}
   - Indicates momentum and potential overbought/oversold conditions
2. VWAP (Volume Weighted Average Price): ${data['vwap']:.2f}
   - Key reference point for institutional trading
3. SMA20 (20-Day Simple Moving Average): ${data['sma20']:.2f}
   - Trend and support/resistance indicator
4. EMA9 (9-Day Exponential Moving Average): ${data['ema9']:.2f}
   - Short-term trend indicator
5. ATR (Average True Range): ${data['atr']:.2f}
   - Volatility and potential stop-loss reference

VOLUME ANALYSIS:
- Current Volume: {data['volume']:,}
- Average Volume: {data['avg_volume']:,}
- Relative Volume: {data['volume']/data['avg_volume']:.1f}x

RECENT PRICE ACTION:
{json.dumps(data['recent_price_action'], indent=2)}

TRADING DECISION FRAMEWORK:
1. Assess momentum and trend strength
2. Identify clear entry and exit points
3. Calculate risk-reward ratio
4. Determine position sizing

Provide a trading setup following this EXACT format:
TRADING SETUP: {data['symbol']}
Entry: $PRICE
Target: $PRICE
Stop: $PRICE
Size: # shares
Reason: [Concise trading rationale]
Confidence: [0-100%]
Risk-Reward Ratio: X:1

If no clear, high-probability setup exists, respond with 'NO SETUP'."""
        return prompt

    async def analyze_setup(self, data):
        """
        Get trading analysis from Local Language Model
        
        Args:
            data (dict): Stock analysis data
        
        Returns:
            str: Trading setup or 'NO SETUP'
        """
        for attempt in range(self.max_retries):
            try:
                # Generate prompt
                prompt = self.generate_prompt(data)
                
                # Call LLM
                response = ollama.generate(
                    model=self.model,
                    prompt=prompt,
                    # Optional: add generation parameters for more controlled output
                    options={
                        'temperature': 0.7,  # Some creativity but not too random
                        'top_p': 0.9,        # Focused response
                        'max_tokens': 300    # Limit response length
                    }
                )
                
                # Extract and validate response
                setup = response['response'].strip()
                
                # Basic validation
                if setup == 'NO SETUP' or 'TRADING SETUP:' in setup:
                    return setup
                
                logging.warning(f"Invalid LLM response: {setup}")
                return "NO SETUP"
            
            except Exception as e:
                logging.error(f"LLM analysis attempt {attempt + 1} failed: {str(e)}")
                
                # Last attempt
                if attempt == self.max_retries - 1:
                    return "NO SETUP"
        
        return "NO SETUP"