# components/stock_scanner.py
import subprocess
import logging
import aiohttp
import asyncio
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta

class StockScanner:
    def __init__(self):
        """Initialize Stock Scanner with enhanced filtering and data sources"""
        # Base API endpoints
        self.api_endpoints = {
            'yahoo_gainers': 'https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved',
            'yahoo_trending': 'https://finance.yahoo.com/markets/stocks/trending',
            'yahoo_active': 'https://finance.yahoo.com/markets/stocks/most-active',
            'yahoo_52week': 'https://finance.yahoo.com/markets/stocks/52-week-gainers'
        }
        
        # Headers for API requests
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Symbol cache with timestamp
        self._symbol_cache: Dict[str, Any] = {}
        self._last_cache_update = None
        self._cache_duration = timedelta(minutes=5)
        
        # Blacklisted symbols (e.g., known problems)
        self.blacklist: Set[str] = set()
        
        # Initialize logging
        logging.getLogger(__name__).setLevel(logging.INFO)

    async def get_symbols(self, max_symbols: int = 100) -> List[str]:
        """
        Get stock symbols from multiple sources with enhanced filtering
        
        Args:
            max_symbols (int): Maximum number of symbols to return
            
        Returns:
            list: Filtered stock symbols
        """
        try:
            # Check cache first
            if self._check_cache():
                return list(self._symbol_cache['symbols'])[:max_symbols]
            
            # Collect symbols from multiple sources
            symbols = set()
            
            # Gather tasks for parallel execution
            tasks = [
                self._fetch_gainers(),
                self._fetch_trending(),
                self._fetch_most_active(),
                self._fetch_52week_highs()
            ]
            
            # Execute tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    logging.error(f"Error fetching symbols: {str(result)}")
                    continue
                    
                if isinstance(result, list):
                    symbols.update(result)
            
            # Filter and validate symbols
            filtered_symbols = self._filter_symbols(list(symbols))
            
            # Update cache
            self._update_cache(filtered_symbols)
            
            return filtered_symbols[:max_symbols]
            
        except Exception as e:
            logging.error(f"Failed to get symbols: {str(e)}")
            return []

    async def _fetch_gainers(self) -> List[str]:
        """Fetch top gainers from Yahoo Finance"""
        try:
            params = {
                'count': 100,
                'scrIds': 'day_gainers',
                'formatted': 'true',
                'start': 0,
                'fields': 'symbol,regularMarketPrice,regularMarketChangePercent,regularMarketVolume'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.api_endpoints['yahoo_gainers'],
                    params=params,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return [
                            quote['symbol']
                            for quote in data.get('finance', {}).get('result', [{}])[0].get('quotes', [])
                        ]
            return []
            
        except Exception as e:
            logging.error(f"Error fetching gainers: {str(e)}")
            return []

    async def _fetch_trending(self) -> List[str]:
        """Fetch trending stocks from Yahoo Finance"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.api_endpoints['yahoo_trending'],
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        # Extract symbols from response using string manipulation
                        symbols = []
                        for line in text.split('\n'):
                            if '"symbol":"' in line:
                                symbol = line.split('"symbol":"')[1].split('"')[0]
                                if self._is_valid_symbol(symbol):
                                    symbols.append(symbol)
                        return symbols
            return []
            
        except Exception as e:
            logging.error(f"Error fetching trending stocks: {str(e)}")
            return []

    async def _fetch_most_active(self) -> List[str]:
        """Fetch most active stocks from Yahoo Finance"""
        try:
            params = {
                'start': 0,
                'count': 100
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.api_endpoints['yahoo_active'],
                    params=params,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        # Extract symbols from response
                        symbols = []
                        for line in text.split('\n'):
                            if '"symbol":"' in line:
                                symbol = line.split('"symbol":"')[1].split('"')[0]
                                if self._is_valid_symbol(symbol):
                                    symbols.append(symbol)
                        return symbols
            return []
            
        except Exception as e:
            logging.error(f"Error fetching most active stocks: {str(e)}")
            return []

    async def _fetch_52week_highs(self) -> List[str]:
        """Fetch stocks at 52-week highs"""
        try:
            params = {
                'start': 0,
                'count': 50
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.api_endpoints['yahoo_52week'],
                    params=params,
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        text = await response.text()
                        # Extract symbols from response
                        symbols = []
                        for line in text.split('\n'):
                            if '"symbol":"' in line:
                                symbol = line.split('"symbol":"')[1].split('"')[0]
                                if self._is_valid_symbol(symbol):
                                    symbols.append(symbol)
                        return symbols
            return []
            
        except Exception as e:
            logging.error(f"Error fetching 52-week highs: {str(e)}")
            return []

    def _filter_symbols(self, symbols: List[str]) -> List[str]:
        """
        Filter and validate stock symbols
        
        Args:
            symbols (list): Raw stock symbols
            
        Returns:
            list: Filtered and validated symbols
        """
        filtered = []
        
        for symbol in symbols:
            if self._is_valid_symbol(symbol) and symbol not in self.blacklist:
                filtered.append(symbol)
        
        # Sort by various criteria
        return sorted(list(set(filtered)))

    def _is_valid_symbol(self, symbol: str) -> bool:
        """
        Validate stock symbol
        
        Args:
            symbol (str): Stock symbol to validate
            
        Returns:
            bool: True if symbol is valid
        """
        try:
            # Basic validation rules
            if not symbol or not isinstance(symbol, str):
                return False
                
            # Length check (most symbols are 1-5 characters)
            if not 1 <= len(symbol) <= 5:
                return False
                
            # Should be uppercase letters
            if not symbol.isupper():
                return False
                
            # Check for common invalid patterns
            invalid_patterns = ['_', '.', '-', ']
            if any(pattern in symbol for pattern in invalid_patterns):
                return False
            
            return True
            
        except Exception:
            return False

    def _check_cache(self) -> bool:
        """
        Check if cache is valid
        
        Returns:
            bool: True if cache is valid
        """
        if not self._last_cache_update:
            return False
            
        cache_age = datetime.now() - self._last_cache_update
        return cache_age < self._cache_duration

    def _update_cache(self, symbols: List[str]) -> None:
        """
        Update symbol cache
        
        Args:
            symbols (list): Symbols to cache
        """
        self._symbol_cache = {
            'symbols': symbols,
            'timestamp': datetime.now()
        }
        self._last_cache_update = datetime.now()

    def add_to_blacklist(self, symbol: str) -> None:
        """
        Add symbol to blacklist
        
        Args:
            symbol (str): Symbol to blacklist
        """
        if self._is_valid_symbol(symbol):
            self.blacklist.add(symbol)
            logging.info(f"Added {symbol} to blacklist")

    def remove_from_blacklist(self, symbol: str) -> None:
        """
        Remove symbol from blacklist
        
        Args:
            symbol (str): Symbol to remove from blacklist
        """
        self.blacklist.discard(symbol)
        logging.info(f"Removed {symbol} from blacklist")

    def clear_cache(self) -> None:
        """Clear symbol cache"""
        self._symbol_cache = {}
        self._last_cache_update = None
        logging.info("Symbol cache cleared")

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get cache information
        
        Returns:
            dict: Cache statistics
        """
        return {
            'cache_size': len(self._symbol_cache.get('symbols', [])),
            'last_update': self._last_cache_update,
            'blacklist_size': len(self.blacklist),
            'blacklisted_symbols': list(self.blacklist)
        }
