# components/market_monitor.py
import pytz
import logging
import json
import aiohttp
import asyncio
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

class MarketMonitor:
    def __init__(self, timezone='US/Eastern', config_path: Optional[str] = None):
        """
        Initialize Market Monitor with enhanced features
        
        Args:
            timezone (str): Timezone for market hours
            config_path (str, optional): Path to market calendar config
        """
        self.timezone = pytz.timezone(timezone)
        self.config_path = config_path or 'market_calendar.json'
        
        # Market hours configuration
        self.regular_market_hours = {
            'open': time(9, 30),   # 9:30 AM
            'close': time(16, 0),  # 4:00 PM
            'pre_market_open': time(4, 0),    # 4:00 AM
            'post_market_close': time(20, 0)  # 8:00 PM
        }
        
        # Initialize market calendar
        self.market_calendar = self._load_market_calendar()
        
        # Market status cache
        self._status_cache = {}
        self._cache_duration = timedelta(minutes=5)
        self._last_cache_update = None

    def _load_market_calendar(self) -> Dict[str, List[str]]:
        """Load market calendar with holidays and special dates"""
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            
            # Default calendar if file doesn't exist
            calendar = {
                'holidays': self._generate_default_holidays(),
                'half_days': self._generate_half_days(),
                'special_events': []
            }
            
            # Save default calendar
            self._save_market_calendar(calendar)
            return calendar
            
        except Exception as e:
            logging.error(f"Error loading market calendar: {str(e)}")
            return {
                'holidays': self._generate_default_holidays(),
                'half_days': [],
                'special_events': []
            }

    def _generate_default_holidays(self) -> List[str]:
        """Generate default market holidays for current year"""
        current_year = datetime.now().year
        return [
            f"{current_year}-01-01",  # New Year's Day
            f"{current_year}-01-15",  # Martin Luther King Jr. Day
            f"{current_year}-02-19",  # Presidents' Day
            f"{current_year}-05-27",  # Memorial Day
            f"{current_year}-07-04",  # Independence Day
            f"{current_year}-09-02",  # Labor Day
            f"{current_year}-11-28",  # Thanksgiving
            f"{current_year}-12-25",  # Christmas
        ]

    def _generate_half_days(self) -> List[str]:
        """Generate typical half-day dates"""
        current_year = datetime.now().year
        return [
            f"{current_year}-11-29",  # Day after Thanksgiving
            f"{current_year}-12-24",  # Christmas Eve
        ]

    def _save_market_calendar(self, calendar: Dict[str, List[str]]) -> None:
        """Save market calendar to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(calendar, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving market calendar: {str(e)}")

    def is_market_open(self, include_extended: bool = False) -> bool:
        """Check if market is currently open"""
        try:
            # Get current time in market timezone
            now = datetime.now(self.timezone)
            current_time = now.time()
            
            # Check if it's a holiday
            if now.strftime("%Y-%m-%d") in self.market_calendar['holidays']:
                return False
            
            # Check if it's a weekend
            if now.weekday() >= 5:
                return False
            
            # Check if it's a half day
            is_half_day = now.strftime("%Y-%m-%d") in self.market_calendar['half_days']
            
            if include_extended:
                return (
                    self.regular_market_hours['pre_market_open'] <= current_time < 
                    (time(13, 0) if is_half_day else self.regular_market_hours['post_market_close'])
                )
            else:
                return (
                    self.regular_market_hours['open'] <= current_time <
                    (time(13, 0) if is_half_day else self.regular_market_hours['close'])
                )
        except Exception as e:
            logging.error(f"Error checking market status: {str(e)}")
            return False

    def get_market_status(self) -> Dict[str, Any]:
        """Get comprehensive market status"""
        try:
            now = datetime.now(self.timezone)
            
            status = {
                'timestamp': now.isoformat(),
                'is_open': self.is_market_open(False),
                'is_extended_hours_open': self.is_market_open(True),
                'current_time': now.strftime('%H:%M:%S'),
                'today_is_holiday': now.strftime("%Y-%m-%d") in self.market_calendar['holidays'],
                'today_is_half_day': now.strftime("%Y-%m-%d") in self.market_calendar['half_days'],
                'is_weekend': now.weekday() >= 5,
                'market_hours': {
                    'regular_open': self.regular_market_hours['open'].strftime('%H:%M'),
                    'regular_close': self.regular_market_hours['close'].strftime('%H:%M'),
                    'pre_market_open': self.regular_market_hours['pre_market_open'].strftime('%H:%M'),
                    'post_market_close': self.regular_market_hours['post_market_close'].strftime('%H:%M')
                }
            }
            
            return status
            
        except Exception as e:
            logging.error(f"Error getting market status: {str(e)}")
            return {
                'is_open': False,
                'error': str(e)
            }
            
    def time_until_market_open(self, include_extended: bool = False) -> timedelta:
        """Calculate time until next market opening"""
        try:
            now = datetime.now(self.timezone)
            
            # If market is already open, return 0
            if self.is_market_open(include_extended):
                return timedelta(0)
            
            # Get target opening time
            target_time = (
                self.regular_market_hours['pre_market_open']
                if include_extended
                else self.regular_market_hours['open']
            )
            
            # Calculate next market open
            next_open = now.replace(
                hour=target_time.hour,
                minute=target_time.minute,
                second=0,
                microsecond=0
            )
            
            # If we're past today's opening, move to next day
            if now.time() >= target_time:
                next_open += timedelta(days=1)
            
            # Skip weekends and holidays
            while (
                next_open.weekday() >= 5 or
                next_open.strftime("%Y-%m-%d") in self.market_calendar['holidays']
            ):
                next_open += timedelta(days=1)
            
            return next_open - now
        except Exception as e:
            logging.error(f"Error calculating time until market open: {str(e)}")
            return timedelta(minutes=1)  # Return short delay on error
