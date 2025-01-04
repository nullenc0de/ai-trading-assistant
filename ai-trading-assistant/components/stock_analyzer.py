# components/stock_analyzer.py
import yfinance as yf
import pandas as pd
import numpy as np
import logging

class StockAnalyzer:
    def __init__(self, config):
        """
        Initialize Stock Analyzer with configurable trading filters
        
        Args:
            config (ConfigManager): Configuration manager with trading parameters
        """
        self.trading_filters = {
            'min_price': config.get('min_price', 2.00),
            'max_price': config.get('max_price', 20.00),
            'min_volume': config.get('min_volume', 500000),
            'min_rel_volume': config.get('min_rel_volume', 5.0)
        }

    def calculate_technical_indicators(self, df):
        """
        Calculate various technical indicators
        
        Args:
            df (pd.DataFrame): Price and volume data
        
        Returns:
            pd.DataFrame: DataFrame with added technical indicators
        """
        try:
            # Ensure required columns exist
            required_columns = ['Close', 'High', 'Low', 'Volume']
            if not all(col in df.columns for col in required_columns):
                logging.error("Missing required columns for indicator calculation")
                return df

            # RSI Calculation
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))

            # VWAP
            df['VWAP'] = (df['Close'] * df['Volume']).cumsum() / df['Volume'].cumsum()

            # Moving averages
            df['SMA_20'] = df['Close'].rolling(window=20).mean()
            df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()

            # ATR for volatility
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            ranges = pd.concat([high_low, high_close, low_close], axis=1)
            df['ATR'] = ranges.max(axis=1).rolling(14).mean()

            return df
        except Exception as e:
            logging.error(f"Error calculating technical indicators: {str(e)}")
            return df

    def analyze_stock(self, symbol):
        """
        Comprehensive stock analysis
        
        Args:
            symbol (str): Stock ticker symbol
        
        Returns:
            dict or None: Analyzed stock data or None if analysis fails
        """
        try:
            # Fetch stock data
            stock = yf.Ticker(symbol)
            
            # Get historical data (1-day, 1-minute interval)
            hist = stock.history(period='1d', interval='1m')

            if hist.empty:
                logging.warning(f"No historical data for {symbol}")
                return None

            # Get current price and volume
            current_price = hist['Close'].iloc[-1]
            current_volume = hist['Volume'].sum()
            
            # Get additional stock info
            stock_info = stock.info

            # Calculate average volume
            avg_volume = stock_info.get('averageVolume', 0)
            rel_volume = current_volume / avg_volume if avg_volume > 0 else 0

            # Apply filters
            if not self._passes_filters(current_price, current_volume, rel_volume):
                return None

            # Calculate technical indicators
            tech_data = self.calculate_technical_indicators(hist)

            # Format data for trading analysis
            data = self._format_data_for_analysis(symbol, tech_data, stock_info)

            return data

        except Exception as e:
            logging.error(f"Error analyzing {symbol}: {str(e)}")
            return None

    def _passes_filters(self, price, volume, rel_volume):
        """
        Check if stock passes basic trading filters
        
        Args:
            price (float): Current stock price
            volume (int): Current trading volume
            rel_volume (float): Relative volume compared to average
        
        Returns:
            bool: True if stock passes filters, False otherwise
        """
        filters = self.trading_filters
        return all([
            price >= filters['min_price'],
            price <= filters['max_price'],
            volume >= filters['min_volume'],
            rel_volume >= filters['min_rel_volume']
        ])

    def _format_data_for_analysis(self, symbol, tech_data, stock_info):
        """
        Format stock data for LLM trading analysis
        
        Args:
            symbol (str): Stock ticker symbol
            tech_data (pd.DataFrame): Technical indicator data
            stock_info (dict): Additional stock information
        
        Returns:
            dict: Formatted stock data
        """
        # Get most recent 5 data points
        recent = tech_data.tail(5)

        return {
            'symbol': symbol,
            'current_price': tech_data['Close'].iloc[-1],
            'rsi': tech_data['RSI'].iloc[-1],
            'vwap': tech_data['VWAP'].iloc[-1],
            'sma20': tech_data['SMA_20'].iloc[-1],
            'ema9': tech_data['EMA_9'].iloc[-1],
            'atr': tech_data['ATR'].iloc[-1],
            'volume': stock_info.get('volume', 0),
            'avg_volume': stock_info.get('averageVolume', 0),
            'market_cap': stock_info.get('marketCap', 0),
            'beta': stock_info.get('beta', 0),
            'recent_price_action': recent[['Open', 'High', 'Low', 'Close', 'Volume']].to_dict('records')
        }