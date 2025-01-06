import pytz
import logging
import json
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
        self.logger = logging.getLogger(__name__)
        
        # Market hours configuration
        self.regular_market_hours = {
            'open': time(9, 30),   # 9:30 AM
            'close': time(16, 0),  # 4:00 PM
            'pre_market_open': time(4, 0),    # 4:00 AM
            'post_market_close': time(20, 0)  # 8:00 PM
        }
        
        # Initialize market calendar
        self.market_calendar = self._load_market_calendar()

    def _load_market_calendar(self) -> Dict[str, Any]:
        """Load market calendar with holidays and special dates"""
        try:
            if Path(self.config_path).exists():
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            
            # Default calendar if file doesn't exist
            calendar = {
                'holidays': self._generate_default_holidays(),
                'half_days': self._generate_half_days(),
                'special_events': [],
                'testing_mode': {
                    'enabled': False,
                    'override_market_hours': False,
                    'scan_interval': 60
                }
            }
            
            # Save default calendar
            self._save_market_calendar(calendar)
            return calendar
            
        except Exception as e:
            self.logger.error(f"Error loading market calendar: {str(e)}")
            return {
                'holidays': self._generate_default_holidays(),
                'half_days': [],
                'special_events': [],
                'testing_mode': {
                    'enabled': False,
                    'override_market_hours': False,
                    'scan_interval': 60
                }
            }

    def get_market_phase(self) -> str:
        """
        Get current market phase (pre-market, regular, post-market, closed)
        
        Returns:
            str: Current market phase
        """
        try:
            # Check testing mode first
            if self.market_calendar.get('testing_mode', {}).get('enabled', False):
                return 'regular'
            
            now = datetime.now(self.timezone)
            current_time = now.time()
            
            # First check if we're in overnight hours (8 PM - 4 AM)
            if current_time >= self.regular_market_hours['post_market_close'] or \
               current_time < self.regular_market_hours['pre_market_open']:
                return 'closed'

            # Then check if it's a weekend
            if now.weekday() >= 5:
                return 'closed'
            
            # Then check if it's a holiday
            if now.strftime("%Y-%m-%d") in self.market_calendar.get('holidays', []):
                return 'closed'
            
            # Pre-market (4:00 AM - 9:30 AM ET)
            if self.regular_market_hours['pre_market_open'] <= current_time < self.regular_market_hours['open']:
                return 'pre-market'
            
            # Regular hours (9:30 AM - 4:00 PM ET)
            elif self.regular_market_hours['open'] <= current_time < self.regular_market_hours['close']:
                return 'regular'
            
            # Post-market (4:00 PM - 8:00 PM ET)
            elif self.regular_market_hours['close'] <= current_time < self.regular_market_hours['post_market_close']:
                return 'post-market'
            
            return 'closed'
            
        except Exception as e:
            self.logger.error(f"Error getting market phase: {str(e)}")
            return 'closed'

    def is_market_open(self, include_extended: bool = False) -> bool:
        """Check if market is currently open"""
        market_phase = self.get_market_phase()
        
        if include_extended:
            return market_phase in ['pre-market', 'regular', 'post-market']
        
        return market_phase == 'regular'

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

    def _save_market_calendar(self, calendar: Dict[str, Any]) -> None:
        """Save market calendar to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(calendar, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving market calendar: {str(e)}")

    def get_market_status(self) -> Dict[str, Any]:
        """Get comprehensive market status"""
        try:
            now = datetime.now(self.timezone)
            market_phase = self.get_market_phase()
            
            status = {
                'timestamp': now.isoformat(),
                'market_phase': market_phase,
                'is_open': market_phase == 'regular',
                'is_extended_hours': market_phase in ['pre-market', 'post-market'],
                'current_time': now.strftime('%H:%M:%S'),
                'today_is_holiday': now.strftime("%Y-%m-%d") in self.market_calendar.get('holidays', []),
                'today_is_half_day': now.strftime("%Y-%m-%d") in self.market_calendar.get('half_days', []),
                'is_weekend': now.weekday() >= 5,
                'is_testing_mode': self.market_calendar.get('testing_mode', {}).get('enabled', False),
                'market_hours': {
                    'regular_open': self.regular_market_hours['open'].strftime('%H:%M'),
                    'regular_close': self.regular_market_hours['close'].strftime('%H:%M'),
                    'pre_market_open': self.regular_market_hours['pre_market_open'].strftime('%H:%M'),
                    'post_market_close': self.regular_market_hours['post_market_close'].strftime('%H:%M')
                }
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting market status: {str(e)}")
            return {
                'market_phase': 'closed',
                'is_open': False,
                'error': str(e)
            }

    def time_until_market_open(self) -> timedelta:
        """Calculate time until next market opening"""
        try:
            # Check testing mode first
            if self.market_calendar.get('testing_mode', {}).get('enabled', False):
                return timedelta(seconds=self.market_calendar['testing_mode'].get('scan_interval', 60))
            
            now = datetime.now(self.timezone)
            
            # If market is already open, return scan interval
            if self.get_market_phase() == 'regular':
                return timedelta(seconds=60)
            
            # Calculate next market open
            next_open = now.replace(
                hour=self.regular_market_hours['open'].hour,
                minute=self.regular_market_hours['open'].minute,
                second=0,
                microsecond=0
            )
            
            # If we're past today's opening, move to next day
            if now.time() >= self.regular_market_hours['open']:
                next_open += timedelta(days=1)
            
            # Skip weekends and holidays
            while (
                next_open.weekday() >= 5 or
                next_open.strftime("%Y-%m-%d") in self.market_calendar.get('holidays', [])
            ):
                next_open += timedelta(days=1)
            
            return next_open - now
            
        except Exception as e:
            self.logger.error(f"Error calculating time until market open: {str(e)}")
            return timedelta(minutes=1)  # Return short delay on error

    def set_testing_mode(self, enabled: bool = True, scan_interval: int = 60) -> bool:
        """Configure testing mode"""
        try:
            self.market_calendar['testing_mode'] = {
                'enabled': enabled,
                'override_market_hours': enabled,
                'scan_interval': scan_interval
            }
            self._save_market_calendar(self.market_calendar)
            return True
        except Exception as e:
            self.logger.error(f"Error setting testing mode: {str(e)}")
            return False
