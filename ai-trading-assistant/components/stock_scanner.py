# components/stock_scanner.py
import subprocess
import logging
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta

class StockScanner:
    def __init__(self):
        """Initialize Stock Scanner with curl command approach"""
        self.curl_command = """curl -s 'https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?count=100&scrIds=DAY_GAINERS&formatted=true&start=0&fields=symbol,regularMarketPrice,regularMarketChangePercent,regularMarketVolume' -H 'User-Agent: Mozilla/5.0' | jq -r '.finance.result[0].quotes[].symbol' ; curl -s 'https://finance.yahoo.com/markets/stocks/trending/' -H 'User-Agent: Mozilla/5.0' | grep -oP '"symbol":"\K[A-Z]+(?=")' ; curl -s 'https://finance.yahoo.com/markets/stocks/most-active/?start=0&count=100' -H 'User-Agent: Mozilla/5.0' | grep -oP '"symbol":"\K[A-Z]+(?=")' ; curl -s 'https://finance.yahoo.com/markets/stocks/52-week-gainers/?start=0&count=50' -H 'User-Agent: Mozilla/5.0' | grep -oP '"symbol":"\K[A-Z]+(?=")'"""
        
        # Symbol cache with timestamp
        self._symbol_cache: Dict[str, Any] = {}
        self._last_cache_update = None
        self._cache_duration = timedelta(minutes=5)
        
        # Blacklisted symbols (e.g., known problems)
        self.blacklist: Set[str] = set()
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)

    async def get_symbols(self, max_symbols: int = 100) -> List[str]:
        """
        Get stock symbols from curl command with caching
        
        Args:
            max_symbols (int): Maximum number of symbols to return
            
        Returns:
            list: Filtered stock symbols
        """
        try:
            # Check cache first
            if self._check_cache():
                return list(self._symbol_cache['symbols'])[:max_symbols]
            
            result = subprocess.run(
                self.curl_command,
                shell=True,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                self.logger.error(f"Curl command failed: {result.stderr}")
                return []

            # Split output into lines and remove duplicates
            symbols = list(set(result.stdout.strip().split('\n')))
            
            # Filter and validate symbols
            filtered_symbols = self._filter_symbols(symbols)
            
            # Update cache
            self._update_cache(filtered_symbols)
            
            return filtered_symbols[:max_symbols]
            
        except Exception as e:
            self.logger.error(f"Failed to get symbols: {str(e)}")
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
        
        # Sort by symbol name
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
            invalid_patterns = ['_', '.', '-', '$']
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
            self.logger.info(f"Added {symbol} to blacklist")

    def remove_from_blacklist(self, symbol: str) -> None:
        """
        Remove symbol from blacklist
        
        Args:
            symbol (str): Symbol to remove from blacklist
        """
        self.blacklist.discard(symbol)
        self.logger.info(f"Removed {symbol} from blacklist")

    def clear_cache(self) -> None:
        """Clear symbol cache"""
        self._symbol_cache = {}
        self._last_cache_update = None
        self.logger.info("Symbol cache cleared")

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
