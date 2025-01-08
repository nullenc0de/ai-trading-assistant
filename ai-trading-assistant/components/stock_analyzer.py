import yfinance as yf
import pandas as pd
import numpy as np
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

class StockAnalyzer:
    def __init__(self, config):
        """Initialize Stock Analyzer with enhanced technical analysis"""
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
        self.logger = logging.getLogger(__name__)

    def analyze_stock(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Analyze stock with improved error handling"""
        try:
            # Validate symbol first
            if not isinstance(symbol, str) or not symbol.strip():
                self.logger.warning(f"Invalid symbol provided: {symbol}")
                return None

            # Check cache first
            if symbol in self.analysis_cache:
                cache_time, cache_data = self.analysis_cache[symbol]
                if datetime.now() - cache_time < self.cache_duration:
                    return cache_data

            # Fetch stock data with error handling
            try:
                stock = yf.Ticker(symbol)
                
                # Get historical data with proper error handling
                data = {}
                intervals = {
                    '1m': '1d',
                    '5m': '5d',
                    'daily': '1mo'
                }
                
                for interval, period in intervals.items():
                    try:
                        df = stock.history(period=period, interval=interval)
                        if not df.empty:
                            data[interval] = df
                    except Exception as e:
                        self.logger.warning(f"Could not fetch {interval} data for {symbol}: {str(e)}")
                        continue
                
                # If we couldn't get any data, return None
                if not data:
                    self.logger.warning(f"No data available for {symbol}")
                    return None

                # Continue with analysis only if we have minimum required data
                if '1m' not in data:
                    self.logger.warning(f"Insufficient historical data for {symbol}")
                    return None

                # Get current trading data
                current_price = data['1m']['Close'].iloc[-1]
                current_volume = data['1m']['Volume'].sum()
                
                # Get stock info with error handling
                try:
                    stock_info = stock.info
                except Exception as e:
                    self.logger.warning(f"Could not fetch info for {symbol}: {str(e)}")
                    stock_info = {}

                # Calculate necessary metrics
                avg_volume = stock_info.get('averageVolume', 0)
                rel_volume = current_volume / avg_volume if avg_volume > 0 else 0

                if not self._passes_filters(current_price, current_volume, rel_volume):
                    return None

                # Calculate technical indicators for available timeframes
                technical_data = {}
                for timeframe, df in data.items():
                    technical_data[timeframe] = self.calculate_technical_indicators(df)

                # Format analysis results
                analysis_result = {
                    'symbol': symbol,
                    'current_price': current_price,
                    'technical_indicators': technical_data.get('1m', {}).get('technical_indicators', {}),
                    'volume_analysis': {
                        'current_volume': current_volume,
                        'avg_volume': avg_volume,
                        'rel_volume': rel_volume
                    }
                }

                # Cache results
                self.analysis_cache[symbol] = (datetime.now(), analysis_result)
                return analysis_result

            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {str(e)}")
                return None

        except Exception as e:
            self.logger.error(f"Fatal error analyzing {symbol}: {str(e)}")
            return None

    def calculate_technical_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate technical indicators with error handling"""
        try:
            indicators = {}
            
            # Basic indicators
            if 'Close' in df.columns:
                indicators['sma_20'] = df['Close'].rolling(window=20).mean().iloc[-1]
                indicators['ema_9'] = df['Close'].ewm(span=9, adjust=False).mean().iloc[-1]
                
                # RSI
                delta = df['Close'].diff()
                gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
                rs = gain / loss
                indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1]
                
            # Volume-weighted indicators
            if all(col in df.columns for col in ['Close', 'Volume']):
                indicators['vwap'] = (df['Close'] * df['Volume']).sum() / df['Volume'].sum()
                
            return {
                'technical_indicators': indicators
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating technical indicators: {str(e)}")
            return {'technical_indicators': {}}

    def _passes_filters(self, price: float, volume: int, rel_volume: float) -> bool:
        """Trading filter validation"""
        try:
            filters = self.trading_filters
            return all([
                price >= filters['min_price'],
                price <= filters['max_price'],
                volume >= filters['min_volume'],
                rel_volume >= filters['min_rel_volume']
            ])
            
        except Exception as e:
            self.logger.error(f"Error in filter validation: {str(e)}")
            return False

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """Clear analysis cache"""
        try:
            if symbol:
                self.analysis_cache.pop(symbol, None)
            else:
                self.analysis_cache.clear()
                
            self.logger.info(f"Cleared analysis cache for {'all symbols' if symbol is None else symbol}")
        except Exception as e:
            self.logger.error(f"Error clearing cache: {str(e)}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get analysis cache statistics"""
        try:
            current_time = datetime.now()
            return {
                'cache_size': len(self.analysis_cache),
                'cached_symbols': list(self.analysis_cache.keys()),
                'cache_age': {
                    symbol: (current_time - timestamp).seconds
                    for symbol, (timestamp, _) in self.analysis_cache.items()
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {str(e)}")
            return {
                'cache_size': 0,
                'cached_symbols': [],
                'cache_age': {}
            }

    def analyze_support_resistance(self, df: pd.DataFrame, periods: int = 20) -> Dict[str, float]:
        """Calculate support and resistance levels"""
        try:
            if df.empty:
                return {'support': 0, 'resistance': 0, 'mid_point': 0}

            # Get recent highs and lows
            highs = df['High'].tail(periods)
            lows = df['Low'].tail(periods)
            
            # Calculate levels using price clustering
            resistance = self._calculate_resistance(highs)
            support = self._calculate_support(lows)
            mid_point = (support + resistance) / 2
            
            return {
                'support': support,
                'resistance': resistance,
                'mid_point': mid_point
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating support/resistance: {str(e)}")
            return {'support': 0, 'resistance': 0, 'mid_point': 0}

    def _calculate_support(self, prices: pd.Series) -> float:
        """Calculate support level using price clustering"""
        try:
            if prices.empty:
                return 0
            
            # Find price clusters
            clusters = pd.qcut(prices, q=4, duplicates='drop')
            
            # Get lowest cluster midpoint
            support = clusters.value_counts().index[0].mid
            
            return float(support)
            
        except Exception as e:
            self.logger.error(f"Error calculating support: {str(e)}")
            return float(prices.min()) if not prices.empty else 0

    def _calculate_resistance(self, prices: pd.Series) -> float:
        """Calculate resistance level using price clustering"""
        try:
            if prices.empty:
                return 0
            
            # Find price clusters
            clusters = pd.qcut(prices, q=4, duplicates='drop')
            
            # Get highest cluster midpoint
            resistance = clusters.value_counts().index[-1].mid
            
            return float(resistance)
            
        except Exception as e:
            self.logger.error(f"Error calculating resistance: {str(e)}")
            return float(prices.max()) if not prices.empty else 0
