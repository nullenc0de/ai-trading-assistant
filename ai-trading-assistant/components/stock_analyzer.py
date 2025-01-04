# components/stock_analyzer.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

class StockAnalyzer:
    def __init__(self, config):
        """
        Initialize Stock Analyzer with enhanced technical analysis
        
        Args:
            config (ConfigManager): Configuration manager instance
        """
        self.trading_filters = {
            'min_price': config.get('min_price', 2.00),
            'max_price': config.get('max_price', 20.00),
            'min_volume': config.get('min_volume', 500000),
            'min_rel_volume': config.get('min_rel_volume', 5.0),
            'max_spread_percent': config.get('max_spread_percent', 0.02)
        }
        
        # Cache for technical analysis
        self.analysis_cache = {}
        self.cache_duration = timedelta(minutes=5)

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate comprehensive technical indicators
        
        Args:
            df (pd.DataFrame): Price and volume data
        
        Returns:
            pd.DataFrame: DataFrame with added technical indicators
        """
        try:
            # Validate required columns
            required_columns = ['Close', 'High', 'Low', 'Volume', 'Open']
            if not all(col in df.columns for col in required_columns):
                raise ValueError("Missing required columns for indicator calculation")

            # Price-based indicators
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
            df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
            
            # Trend Detection
            df['trend'] = np.where(df['EMA_9'] > df['EMA_21'], 1, 
                                 np.where(df['EMA_9'] < df['EMA_21'], -1, 0))

            # RSI Calculation
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(window=14).mean()
            avg_loss = loss.rolling(window=14).mean()
            rs = avg_gain / avg_loss
            df['RSI'] = 100 - (100 / (1 + rs))

            # VWAP Calculation
            df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()

            # Bollinger Bands
            df['BB_middle'] = df['Close'].rolling(window=20).mean()
            bb_std = df['Close'].rolling(window=20).std()
            df['BB_upper'] = df['BB_middle'] + (bb_std * 2)
            df['BB_lower'] = df['BB_middle'] - (bb_std * 2)
            
            # ATR for volatility
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            df['ATR'] = ranges.max(axis=1).rolling(14).mean()

            # Volume Analysis
            df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
            df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA']
            
            # Price Momentum
            df['ROC'] = df['Close'].pct_change(periods=10) * 100
            
            # Support and Resistance Levels
            df['Pivot'] = (df['High'] + df['Low'] + df['Close']) / 3
            df['R1'] = 2 * df['Pivot'] - df['Low']
            df['S1'] = 2 * df['Pivot'] - df['High']

            return df

        except Exception as e:
            logging.error(f"Error calculating technical indicators: {str(e)}")
            return df

    def analyze_stock(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Comprehensive stock analysis with caching
        
        Args:
            symbol (str): Stock ticker symbol
        
        Returns:
            dict or None: Analyzed stock data
        """
        try:
            # Check cache first
            if symbol in self.analysis_cache:
                cache_time, cache_data = self.analysis_cache[symbol]
                if datetime.now() - cache_time < self.cache_duration:
                    return cache_data

            # Fetch stock data
            stock = yf.Ticker(symbol)
            
            # Get historical data for multiple timeframes
            data = {
                '1m': stock.history(period='1d', interval='1m'),
                '5m': stock.history(period='5d', interval='5m'),
                'daily': stock.history(period='1mo', interval='1d')
            }
            
            # Validate data availability
            if any(df.empty for df in data.values()):
                logging.warning(f"Insufficient historical data for {symbol}")
                return None

            # Get current trading data
            current_price = data['1m']['Close'].iloc[-1]
            current_volume = data['1m']['Volume'].sum()
            
            # Get stock info
            stock_info = stock.info

            # Calculate average volume
            avg_volume = stock_info.get('averageVolume', 0)
            rel_volume = current_volume / avg_volume if avg_volume > 0 else 0

            # Apply trading filters
            if not self._passes_filters(current_price, current_volume, rel_volume):
                return None

            # Calculate technical indicators for different timeframes
            technical_data = {
                timeframe: self.calculate_technical_indicators(df)
                for timeframe, df in data.items()
            }

            # Analyze price action patterns
            patterns = self._analyze_price_patterns(technical_data['1m'])

            # Format analysis results
            analysis_result = self._format_analysis_results(
                symbol, technical_data, stock_info, patterns
            )

            # Cache the results
            self.analysis_cache[symbol] = (datetime.now(), analysis_result)

            return analysis_result

        except Exception as e:
            logging.error(f"Error analyzing {symbol}: {str(e)}")
            return None

    def _passes_filters(self, price: float, volume: int, rel_volume: float) -> bool:
        """
        Enhanced trading filter validation
        
        Args:
            price (float): Current stock price
            volume (int): Current trading volume
            rel_volume (float): Relative volume ratio
        
        Returns:
            bool: True if stock passes filters
        """
        filters = self.trading_filters
        
        # Basic filters
        basic_filters = [
            price >= filters['min_price'],
            price <= filters['max_price'],
            volume >= filters['min_volume'],
            rel_volume >= filters['min_rel_volume']
        ]
        
        if not all(basic_filters):
            return False
            
        return True

    def _analyze_price_patterns(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Analyze price action patterns
        
        Args:
            df (pd.DataFrame): Price data
            
        Returns:
            list: Detected patterns
        """
        patterns = []
        
        try:
            # Get recent candles
            recent = df.tail(5)
            
            # Analyze candlestick patterns
            for i in range(len(recent)):
                candle = recent.iloc[i]
                body = abs(candle['Open'] - candle['Close'])
                upper_wick = candle['High'] - max(candle['Open'], candle['Close'])
                lower_wick = min(candle['Open'], candle['Close']) - candle['Low']
                
                pattern = {
                    'timestamp': candle.name,
                    'type': 'bullish' if candle['Close'] > candle['Open'] else 'bearish',
                    'body_size': body,
                    'upper_wick': upper_wick,
                    'lower_wick': lower_wick,
                    'volume': candle['Volume']
                }
                
                patterns.append(pattern)
                
        except Exception as e:
            logging.error(f"Error analyzing price patterns: {str(e)}")
        
        return patterns

    def _format_analysis_results(
        self, 
        symbol: str, 
        technical_data: Dict[str, pd.DataFrame],
        stock_info: Dict[str, Any],
        patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Format comprehensive analysis results
        
        Args:
            symbol (str): Stock symbol
            technical_data (dict): Technical analysis data
            stock_info (dict): Stock information
            patterns (list): Detected price patterns
            
        Returns:
            dict: Formatted analysis results
        """
        # Get most recent data points
        minute_data = technical_data['1m'].tail(5)
        
        return {
            'symbol': symbol,
            'current_price': minute_data['Close'].iloc[-1],
            'day_range': {
                'high': minute_data['High'].max(),
                'low': minute_data['Low'].min()
            },
            'technical_indicators': {
                'rsi': minute_data['RSI'].iloc[-1],
                'vwap': minute_data['VWAP'].iloc[-1],
                'sma20': minute_data['SMA_20'].iloc[-1],
                'ema9': minute_data['EMA_9'].iloc[-1],
                'atr': minute_data['ATR'].iloc[-1],
                'roc': minute_data['ROC'].iloc[-1]
            },
            'volume_analysis': {
                'current_volume': stock_info.get('volume', 0),
                'avg_volume': stock_info.get('averageVolume', 0),
                'volume_ratio': minute_data['Volume_Ratio'].iloc[-1]
            },
            'price_levels': {
                'support': minute_data['S1'].iloc[-1],
                'resistance': minute_data['R1'].iloc[-1],
                'pivot': minute_data['Pivot'].iloc[-1]
            },
            'market_data': {
                'market_cap': stock_info.get('marketCap', 0),
                'beta': stock_info.get('beta', 0),
                'sector': stock_info.get('sector', 'Unknown')
            },
            'price_patterns': patterns,
            'recent_price_action': minute_data[['Open', 'High', 'Low', 'Close', 'Volume']].to_dict('records')
        }

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear analysis cache
        
        Args:
            symbol (str, optional): Specific symbol to clear, or None for all
        """
        if symbol:
            self.analysis_cache.pop(symbol, None)
        else:
            self.analysis_cache.clear()
            
        logging.info(f"Cleared analysis cache for {'all symbols' if symbol is None else symbol}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get analysis cache statistics
        
        Returns:
            dict: Cache statistics
        """
        current_time = datetime.now()
        
        return {
            'cache_size': len(self.analysis_cache),
            'cached_symbols': list(self.analysis_cache.keys()),
            'cache_age': {
                symbol: (current_time - timestamp).seconds
                for symbol, (timestamp, _) in self.analysis_cache.items()
            }
        }

    def analyze_support_resistance(self, df: pd.DataFrame, periods: int = 20) -> Dict[str, float]:
        """
        Calculate support and resistance levels using price action
        
        Args:
            df (pd.DataFrame): Price data
            periods (int): Lookback periods
            
        Returns:
            dict: Support and resistance levels
        """
        try:
            # Get recent highs and lows
            highs = df['High'].tail(periods)
            lows = df['Low'].tail(periods)
            
            # Calculate potential levels
            resistance_level = self._calculate_resistance(highs)
            support_level = self._calculate_support(lows)
            
            return {
                'support': support_level,
                'resistance': resistance_level,
                'mid_point': (support_level + resistance_level) / 2
            }
            
        except Exception as e:
            logging.error(f"Error calculating support/resistance: {str(e)}")
            return {
                'support': df['Low'].min(),
                'resistance': df['High'].max(),
                'mid_point': df['Close'].mean()
            }

    def _calculate_support(self, prices: pd.Series) -> float:
        """
        Calculate support level using price clustering
        
        Args:
            prices (pd.Series): Price data
            
        Returns:
            float: Support level
        """
        # Find price clusters
        clusters = pd.cut(prices, bins=10)
        
        # Get most frequent price level
        support = clusters.value_counts().index[0].mid
        
        return float(support)

    def _calculate_resistance(self, prices: pd.Series) -> float:
        """
        Calculate resistance level using price clustering
        
        Args:
            prices (pd.Series): Price data
            
        Returns:
            float: Resistance level
        """
        # Find price clusters
        clusters = pd.cut(prices, bins=10)
        
        # Get most frequent price level
        resistance = clusters.value_counts().index[-1].mid
        
        return float(resistance)

    def check_momentum(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze price momentum using multiple indicators
        
        Args:
            df (pd.DataFrame): Price data
            
        Returns:
            dict: Momentum analysis results
        """
        try:
            # Calculate momentum indicators
            roc = df['ROC'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            volume_ratio = df['Volume_Ratio'].iloc[-1]
            
            # Determine trend strength
            trend_strength = abs(df['trend'].tail(5).mean())
            
            return {
                'momentum': 'bullish' if roc > 0 else 'bearish',
                'strength': trend_strength,
                'overbought': rsi > 70,
                'oversold': rsi < 30,
                'volume_confirmed': volume_ratio > 1.5,
                'metrics': {
                    'roc': roc,
                    'rsi': rsi,
                    'volume_ratio': volume_ratio
                }
            }
            
        except Exception as e:
            logging.error(f"Error checking momentum: {str(e)}")
            return {
                'momentum': 'neutral',
                'strength': 0,
                'overbought': False,
                'oversold': False,
                'volume_confirmed': False,
                'metrics': {}
            }

    def validate_setup(self, setup: Dict[str, Any]) -> bool:
        """
        Validate trading setup against current market conditions
        
        Args:
            setup (dict): Trading setup parameters
            
        Returns:
            bool: True if setup is valid
        """
        try:
            # Get current market data
            symbol = setup['symbol']
            current_data = self.analyze_stock(symbol)
            
            if not current_data:
                return False
            
            # Validate price levels
            current_price = current_data['current_price']
            entry_price = setup['entry_price']
            
            # Price deviation check
            price_valid = abs(entry_price - current_price) / current_price <= 0.02
            
            # Volume validation
            volume_valid = current_data['volume_analysis']['volume_ratio'] > 1.0
            
            # Momentum check
            momentum = self.check_momentum(
                pd.DataFrame(current_data['recent_price_action'])
            )
            
            momentum_aligned = (
                (momentum['momentum'] == 'bullish' and entry_price > current_price) or
                (momentum['momentum'] == 'bearish' and entry_price < current_price)
            )
            
            return all([price_valid, volume_valid, momentum_aligned])
            
        except Exception as e:
            logging.error(f"Error validating setup: {str(e)}")
            return False
