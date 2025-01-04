# components/market_monitor.py
import pytz
from datetime import datetime, time, timedelta

class MarketMonitor:
    def __init__(self, timezone='US/Eastern'):
        """
        Initialize Market Monitor
        
        Args:
            timezone (str): Timezone for market hours
        """
        self.timezone = pytz.timezone(timezone)
        
        # Market hours configuration
        self.market_open_time = time(9, 30)  # 9:30 AM
        self.market_close_time = time(16, 0)  # 4:00 PM
        
        # Holidays and market closures (basic list, should be expanded)
        self.market_holidays = [
            # Major US market holidays
            "2024-01-01",  # New Year's Day
            "2024-01-15",  # Martin Luther King Jr. Day
            "2024-02-19",  # Presidents' Day
            "2024-05-27",  # Memorial Day
            "2024-07-04",  # Independence Day
            "2024-09-02",  # Labor Day
            "2024-11-28",  # Thanksgiving
            "2024-12-25",  # Christmas
        ]

    def is_market_open(self):
        """
        Check if current time is during US stock market trading hours
        
        Returns:
            bool: True if market is open, False otherwise
        """
        # Get current time in specified timezone
        now = datetime.now(self.timezone)
        
        # Check if current date is a market holiday
        if now.strftime("%Y-%m-%d") in self.market_holidays:
            return False
        
        # Check if it's a weekend
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check market hours
        current_time = now.time()
        return (
            self.market_open_time <= current_time < self.market_close_time
        )

    def time_until_market_open(self):
        """
        Calculate time until next market opening
        
        Returns:
            timedelta: Time until next market open
        """
        now = datetime.now(self.timezone)
        
        # If market is already open, return 0
        if self.is_market_open():
            return timedelta(0)
        
        # Calculate next market open time
        if now.time() < self.market_open_time:
            # Market opens later today
            market_open = now.replace(
                hour=self.market_open_time.hour, 
                minute=self.market_open_time.minute, 
                second=0, 
                microsecond=0
            )
        else:
            # Market opens next trading day
            market_open = now + timedelta(days=1)
            market_open = market_open.replace(
                hour=self.market_open_time.hour, 
                minute=self.market_open_time.minute, 
                second=0, 
                microsecond=0
            )
        
        # Skip weekends and holidays
        while (market_open.weekday() >= 5 or 
               market_open.strftime("%Y-%m-%d") in self.market_holidays):
            market_open += timedelta(days=1)
        
        return market_open - now

    def get_market_status(self):
        """
        Get comprehensive market status
        
        Returns:
            dict: Detailed market status information
        """
        now = datetime.now(self.timezone)
        
        return {
            'is_open': self.is_market_open(),
            'current_time': now,
            'time_until_open': self.time_until_market_open(),
            'today_is_holiday': now.strftime("%Y-%m-%d") in self.market_holidays,
            'is_weekend': now.weekday() >= 5
        }

    def add_market_holiday(self, date):
        """
        Add a custom market holiday
        
        Args:
            date (str): Date in YYYY-MM-DD format
        """
        if date not in self.market_holidays:
            self.market_holidays.append(date)

    def remove_market_holiday(self, date):
        """
        Remove a market holiday
        
        Args:
            date (str): Date in YYYY-MM-DD format
        """
        if date in self.market_holidays:
            self.market_holidays.remove(date)