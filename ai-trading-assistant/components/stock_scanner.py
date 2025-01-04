# components/stock_scanner.py
import subprocess
import logging

class StockScanner:
    def __init__(self):
        self.curl_command = """curl -s 'https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved?count=100&scrIds=DAY_GAINERS&formatted=true&start=0&fields=symbol,regularMarketPrice,regularMarketChangePercent,regularMarketVolume' -H 'User-Agent: Mozilla/5.0' | jq -r '.finance.result[0].quotes[].symbol' ; curl -s 'https://finance.yahoo.com/markets/stocks/trending/' -H 'User-Agent: Mozilla/5.0' | grep -oP '"symbol":"\K[A-Z]+(?=")' ; curl -s 'https://finance.yahoo.com/markets/stocks/most-active/?start=0&count=100' -H 'User-Agent: Mozilla/5.0' | grep -oP '"symbol":"\K[A-Z]+(?=")' ; curl -s 'https://finance.yahoo.com/markets/stocks/52-week-gainers/?start=0&count=50' -H 'User-Agent: Mozilla/5.0' | grep -oP '"symbol":"\K[A-Z]+(?=")'"""

    def get_symbols(self, max_symbols=100):
        """
        Get stock symbols from multiple sources
        
        Args:
            max_symbols (int): Maximum number of unique symbols to return
        
        Returns:
            list: Unique stock symbols
        """
        try:
            result = subprocess.run(
                self.curl_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30  # Prevent hanging
            )

            if result.returncode != 0:
                logging.error(f"Curl command failed: {result.stderr}")
                return []

            # Split output into lines, remove duplicates, and filter
            symbols = list(set(result.stdout.strip().split('\n')))
            
            # Validate symbols (basic check for uppercase letters)
            valid_symbols = [
                symbol.upper() 
                for symbol in symbols 
                if symbol.isalpha() and len(symbol) <= 5
            ]

            # Truncate to max_symbols
            return valid_symbols[:max_symbols]

        except subprocess.TimeoutExpired:
            logging.error("Symbol retrieval timed out")
            return []
        except Exception as e:
            logging.error(f"Failed to get symbols: {str(e)}")
            return []