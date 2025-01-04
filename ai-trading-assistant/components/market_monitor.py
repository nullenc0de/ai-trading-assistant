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
        
        # Exchange status tracking
        self.exchange_status = {
            'NYSE': 'unknown',
            'NASDAQ': 'unknown',
            'last_update': None
        }

    def _load_market_calendar(self) -> Dict[str, List[str]]:
        """
        Load market calendar with holidays and special dates
        
        Returns:
            dict: Market calendar data
        """
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
        """
        Save market calendar to file
        
        Args:
            calendar (dict): Calendar data to save
        """
        try:
            with open(self.config_path, 'w') as f:
                json.dump(calendar, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving market calendar: {str(e)}")

    async def update_exchange_status(self) -> None:
        """Update real-time exchange status"""
        try:
            # Get current market hours status
            is_market_hours = self.is_market_open(include_extended=False)
            
            # Update exchange status based on market hours and any available API data
            self.exchange_status = {
                'NYSE': 'open' if is_market_hours else 'closed',
                'NASDAQ': 'open' if is_market_hours else 'closed',
                'last_update': datetime.now()
            }
            
            # Additional APIs could be integrated here for real-time status
            # For example:
            # async with aiohttp.ClientSession() as session:
            #     async with session.get(EXCHANGE_API_URL) as response:
            #         if response.status == 200:
            #             data = await response.json()
            #             self.exchange_status.update(data)
            
        except Exception as e:
            logging.error(f"Error updating exchange status: {str(e)}")

    def is_market_open(self, include_extended: bool = False) -> bool:
        """
        Check if market is currently open
        
        Args:
            include_extended (bool): Include extended hours trading
            
        Returns:
            bool: True if market is open
        """
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
            # Extended hours check
            return (
                self.regular_market_hours['pre_market_open'] <= current_time < 
                (time(13, 0) if is_half_day else self.regular_market_hours['post_market_close'])
            )
        else:
            # Regular hours check
            return (
                self.regular_market_hours['open'] <= current_time <
                (time(13, 0) if is_half_day else self.regular_market_hours['close'])
            )

    def time_until_market_open(self, include_extended: bool = False) -> timedelta:
        """
        Calculate time until next market opening
        
        Args:
            include_extended (bool): Include extended hours
            
        Returns:
            timedelta: Time until next market open
        """
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

    def get_market_status(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get comprehensive market status
        
        Args:
            use_cache (bool): Use cached status if available
            
        Returns:
            dict: Detailed market status information
        """
        now = datetime.now(self.timezone)
        
        # Check cache
        if use_cache and self._last_cache_update:
            cache_age = now - self._last_cache_update
            if cache_age < self._cache_duration:
                return self._status_cache
        
        # Build status report
        status = {
            'timestamp': now.isoformat(),
            'is_regular_hours_open': self.is_market_open(False),
            'is_extended_hours_open': self.is_market_open(True),
            'current_time': now.strftime('%H:%M:%S'),
            'time_until_open': self.time_until_market_open().seconds // 60,
            'time_until_extended_open': self.time_until_market_open(True).seconds // 60,
            'today_is_holiday': now.strftime("%Y-%m-%d") in self.market_calendar['holidays'],
            'today_is_half_day': now.strftime("%Y-%m-%d") in self.market_calendar['half_days'],
            'is_weekend': now.weekday() >= 5,
            'exchange_status': self.exchange_status,
            'market_hours': {
                'regular_open': self.regular_market_hours['open'].strftime('%H:%M'),
                'regular_close': self.regular_market_hours['close'].strftime('%H:%M'),
                'pre_market_open': self.regular_market_hours['pre_market_open'].strftime('%H:%M'),
                'post_market_close': self.regular_market_hours['post_market_close'].strftime('%H:%M')
            }
        }
        
        # Update cache
        self._status_cache = status
        self._last_cache_update = now
        
        return status

    def add_market_holiday(self, date: str) -> bool:
        """
        Add a custom market holiday
        
        Args:
            date (str): Date in YYYY-MM-DD format
            
        Returns:
            bool: True if successfully added
        """
        try:
            # Validate date format
            datetime.strptime(date, '%Y-%m-%d')
            
            if date not in self.market_calendar['holidays']:
                self.market_calendar['holidays'].append(date)
                self._save_market_calendar(self.market_calendar)
                logging.info(f"Added market holiday: {date}")
                return True
                
            return False
            
        except ValueError:
            logging.error(f"Invalid date format: {date}")
            return False
        except Exception as e:
            logging.error(f"Error adding market holiday: {str(e)}")
            return False

    def remove_market_holiday(self, date: str) -> bool:
        """
        Remove a market holiday
        
        Args:
            date (str): Date in YYYY-MM-DD format
            
        Returns:
            bool: True if successfully removed
        """
        try:
            if date in self.market_calendar['holidays']:
                self.market_calendar['holidays'].remove(date)
                self._save_market_calendar(self.market_calendar)
                logging.info(f"Removed market holiday: {date}")
                return True
                
            return False
            
        except Exception as e:
            logging.error(f"Error removing market holiday: {str(e)}")
            return False

    def add_half_day(self, date: str) -> bool:
        """
        Add a half trading day
        
        Args:
            date (str): Date in YYYY-MM-DD format
            
        Returns:
            bool: True if successfully added
        """
        try:
            # Validate date format
            datetime.strptime(date, '%Y-%m-%d')
            
            if date not in self.market_calendar['half_days']:
                self.market_calendar['half_days'].append(date)
                self._save_market_calendar(self.market_calendar)
                logging.info(f"Added half day: {date}")
                return True
                
            return False
            
        except ValueError:
            logging.error(f"Invalid date format: {date}")
            return False
        except Exception as e:
            logging.error(f"Error adding half day: {str(e)}")
            return False

    def add_market_event(self, date: str, description: str) -> bool:
        """
        Add a special market event
        
        Args:
            date (str): Date in YYYY-MM-DD format
            description (str): Event description
            
        Returns:
            bool: True if successfully added
        """
        try:
            event = {'date': date, 'description': description}
            self.market_calendar['special_events'].append(event)
            self._save_market_calendar(self.market_calendar)
            logging.info(f"Added market event: {date} - {description}")
            return True
            
        except Exception as e:
            logging.error(f"Error adding market event: {str(e)}")
            return False

    def get_upcoming_events(self, days: int = 30) -> List[Dict[str, str]]:
        """
        Get upcoming market events
        
        Args:
            days (int): Number of days to look ahead
            
        Returns:
            list: Upcoming market events
        """
        try:
            now = datetime.now()
            end_date = now + timedelta(days=days)
            
            events = []
            
            # Check holidays
            for holiday in self.market_calendar['holidays']:
                holiday_date = datetime.strptime(holiday, '%Y-%m-%d')
                if now <= holiday_date <= end_date:
                    events.append({
                        'date': holiday,
                        'type': 'holiday',
                        'description': 'Market Holiday'
                    })
            
            # Check half days
            for half_day in self.market_calendar['half_days']:
                half_day_date = datetime.strptime(half_day, '%Y-%m-%d')
                if now <= half_day_date <= end_date:
                    events.append({
                        'date': half_day,
                        'type': 'half_day',
                        'description': 'Market Half Day'
                    })
            
            # Check special events
            for event in self.market_calendar['special_events']:
                event_date = datetime.strptime(event['date'], '%Y-%m-%d')
                if now <= event_date <= end_date:
                    events.append({
                        'date': event['date'],
                        'type': 'special_event',
                        'description': event['description']
                    })
            
            # Sort by date
            return sorted(events, key=lambda x: x['date'])
            
        except Exception as e:
            logging.error(f"Error getting upcoming events: {str(e)}")
            return []
