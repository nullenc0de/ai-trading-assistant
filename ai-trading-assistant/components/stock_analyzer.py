"""
Stock Analyzer Module
-------------------
Handles stock data analysis, technical indicators, and trading filters
with improved error handling and Yahoo Finance API compatibility.

Author: AI Trading Assistant
Version: 2.2
Last Updated: 2025-01-09
"""

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
        """Analyze stock with improved error handling and correct API parameters"""
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
                    '1m': '1d',    # 1-minute data for the last day
                    '5m': '5d',    # 5-minute data for the last 5 days
                    '1d': '1mo'    # Daily data for the last month
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
                    },
                    'metadata': {
                        'timestamp': datetime.now().isoformat(),
                        'source': 'yfinance',
                        'timeframes_available': list(data.keys())
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
        """Calculate technical indicators with improved error handling"""
        try:
            indicators = {}
            
            if df.empty:
                return {'technical_indicators': {}}
            
            # Basic price indicators
            if 'Close' in df.columns:
                # Moving averages
                indicators['sma_20'] = df['Close'].rolling(window=20).mean().iloc[-1]
                indicators['sma_50'] = df['Close'].rolling(window=50).mean().iloc[-1]
                indicators['ema_9'] = df['Close'].ewm(span=9, adjust=False).mean().iloc[-1]
                indicators['ema_21'] = df['Close'].ewm(span=21, adjust=False).mean().iloc[-1]
                
                # RSI calculation
                delta = df['Close'].diff()
                gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
                rs = gain / loss
                indicators['rsi'] = 100 - (100 / (1 + rs)).iloc[-1]
                
                # Price momentum
                indicators['price_momentum'] = (
                    (df['Close'].iloc[-1] - df['Close'].iloc[-20]) / 
                    df['Close'].iloc[-20] * 100
                )
            
            # Volume-weighted indicators
            if all(col in df.columns for col in ['Close', 'Volume']):
                # VWAP calculation
                df['Cumulative_Volume'] = df['Volume'].cumsum()
                df['Volume_Price'] = df['Close'] * df['Volume']
                df['Cumulative_Volume_Price'] = df['Volume_Price'].cumsum()
                indicators['vwap'] = (
                    df['Cumulative_Volume_Price'].iloc[-1] / 
                    df['Cumulative_Volume'].iloc[-1]
                )
                
                # Volume momentum
                indicators['volume_momentum'] = (
                    df['Volume'].tail(5).mean() / 
                    df['Volume'].tail(20).mean()
                )
            
            # Volatility indicators
            if all(col in df.columns for col in ['High', 'Low', 'Close']):
                # ATR calculation
                high_low = df['High'] - df['Low']
                high_close = abs(df['High'] - df['Close'].shift())
                low_close = abs(df['Low'] - df['Close'].shift())
                ranges = pd.concat([high_low, high_close, low_close], axis=1)
                true_range = ranges.max(axis=1)
                indicators['atr'] = true_range.rolling(window=14).mean().iloc[-1]
                
                # Bollinger Bands
                std_dev = df['Close'].rolling(window=20).std()
                indicators['upper_band'] = indicators['sma_20'] + (std_dev.iloc[-1] * 2)
                indicators['lower_band'] = indicators['sma_20'] - (std_dev.iloc[-1] * 2)
            
            return {
                'technical_indicators': indicators,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating technical indicators: {str(e)}")
            return {'technical_indicators': {}}

    def _passes_filters(self, price: float, volume: int, rel_volume: float) -> bool:
        """Trading filter validation with logging"""
        try:
            filters = self.trading_filters
            checks = {
                'price_min': price >= filters['min_price'],
                'price_max': price <= filters['max_price'],
                'volume_min': volume >= filters['min_volume'],
                'rel_volume_min': rel_volume >= filters['min_rel_volume']
            }
            
            # Log failed checks
            failed_checks = {k: v for k, v in checks.items() if not v}
            if failed_checks:
                self.logger.debug(f"Failed filters: {failed_checks}")
            
            return all(checks.values())
            
        except Exception as e:
            self.logger.error(f"Error in filter validation: {str(e)}")
            return False

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """Clear analysis cache with logging"""
        try:
            if symbol:
                self.analysis_cache.pop(symbol, None)
                self.logger.info(f"Cleared cache for {symbol}")
            else:
                self.analysis_cache.clear()
                self.logger.info("Cleared entire analysis cache")
                
        except Exception as e:
            self.logger.error(f"Error clearing cache: {str(e)}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get analysis cache statistics"""
        try:
            current_time = datetime.now()
            stats = {
                'cache_size': len(self.analysis_cache),
                'cached_symbols': list(self.analysis_cache.keys()),
                'cache_age': {
                    symbol: (current_time - timestamp).seconds
                    for symbol, (timestamp, _) in self.analysis_cache.items()
                },
                'cache_hit_rate': self._calculate_cache_hit_rate()
            }
            return stats
        except Exception as e:
            self.logger.error(f"Error getting cache stats: {str(e)}")
            return {
                'cache_size': 0,
                'cached_symbols': [],
                'cache_age': {},
                'cache_hit_rate': 0.0
            }

    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate"""
        try:
            total_requests = self.metrics.get('total_requests', 0)
            cache_hits = self.metrics.get('cache_hits', 0)
            return (cache_hits / total_requests * 100) if total_requests > 0 else 0.0
        except Exception:
            return 0.0
