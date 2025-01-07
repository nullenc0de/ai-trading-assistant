import logging
from typing import Dict, Any, Optional
from datetime import datetime

class AccountManager:
    def __init__(self, config_manager, robinhood_client=None):
        self.config = config_manager
        self.robinhood_client = robinhood_client
        self.logger = logging.getLogger(__name__)
        
        # Initialize account metrics
        self.metrics = {
            'starting_balance': self.config.get('account_management.performance_tracking.starting_balance', 3000.00),
            'current_balance': 0.0,
            'buying_power': 0.0,
            'cash_reserve': 0.0,
            'total_positions_value': 0.0,
            'unrealized_pl': 0.0,
            'realized_pl': 0.0,
            'high_water_mark': 0.0,
            'last_updated': None
        }
        
        # Initialize account from config
        self._initialize_account()

    def _initialize_account(self) -> None:
        """Initialize account metrics"""
        try:
            if self.robinhood_client and self.robinhood_client.is_authenticated():
                # Get real account data
                profile = self.robinhood_client.load_account_profile()
                self.metrics['current_balance'] = float(profile['equity'])
                self.metrics['buying_power'] = float(profile['buying_power'])
            else:
                # Initialize paper trading account
                self.metrics['current_balance'] = self.metrics['starting_balance']
                self.metrics['buying_power'] = self.metrics['starting_balance']
            
            # Set initial values
            self.metrics['high_water_mark'] = self.metrics['current_balance']
            self.metrics['cash_reserve'] = self.metrics['current_balance'] * (
                self.config.get('account_management.risk_management.cash_reserve_percent', 10.0) / 100
            )
            self.metrics['last_updated'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error initializing account: {str(e)}")

    def update_account_metrics(self, positions: Dict[str, Any]) -> None:
        """Update account metrics with current positions"""
        try:
            if self.robinhood_client and self.robinhood_client.is_authenticated():
                profile = self.robinhood_client.load_account_profile()
                self.metrics['current_balance'] = float(profile['equity'])
                self.metrics['buying_power'] = float(profile['buying_power'])
            else:
                # Calculate for paper trading
                positions_value = sum(pos['current_value'] for pos in positions.values())
                unrealized_pl = sum(pos['unrealized_pl'] for pos in positions.values())
                realized_pl = sum(pos.get('realized_pl', 0) for pos in positions.values())
                
                self.metrics['total_positions_value'] = positions_value
                self.metrics['unrealized_pl'] = unrealized_pl
                self.metrics['realized_pl'] = realized_pl
                self.metrics['current_balance'] = (
                    self.metrics['starting_balance'] + 
                    self.metrics['unrealized_pl'] + 
                    self.metrics['realized_pl']
                )
                
                # Update buying power
                total_allocated = positions_value + self.metrics['cash_reserve']
                self.metrics['buying_power'] = max(0, self.metrics['current_balance'] - total_allocated)
            
            # Update high water mark
            if self.metrics['current_balance'] > self.metrics['high_water_mark']:
                self.metrics['high_water_mark'] = self.metrics['current_balance']
            
            self.metrics['last_updated'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error updating account metrics: {str(e)}")

    def check_trade_allowed(self, position_value: float, risk_amount: float) -> Dict[str, Any]:
        """Check if a trade is allowed based on account rules"""
        try:
            # Get account limits
            max_position_pct = self.config.get('account_management.risk_management.position_sizing.max_position_percent', 20.0)
            max_risk_pct = self.config.get('account_management.risk_management.max_account_risk', 50.0)
            max_daily_loss_pct = self.config.get('account_management.risk_management.limits.max_daily_loss_percent', 3.0)
            
            # Calculate current metrics
            position_percent = (position_value / self.metrics['current_balance']) * 100
            day_pl_percent = (self.metrics['unrealized_pl'] / self.metrics['starting_balance']) * 100
            
            # Check various limits
            checks = {
                'has_buying_power': position_value <= self.metrics['buying_power'],
                'within_position_limit': position_percent <= max_position_pct,
                'within_risk_limit': risk_amount <= (self.metrics['current_balance'] * max_risk_pct / 100),
                'within_daily_loss': day_pl_percent >= -max_daily_loss_pct,
                'has_cash_reserve': (self.metrics['buying_power'] - position_value) >= self.metrics['cash_reserve']
            }
            
            allowed = all(checks.values())
            
            return {
                'allowed': allowed,
                'checks': checks,
                'metrics': {
                    'position_percent': position_percent,
                    'risk_percent': (risk_amount / self.metrics['current_balance']) * 100,
                    'day_pl_percent': day_pl_percent
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error checking trade allowance: {str(e)}")
            return {'allowed': False, 'error': str(e)}

    def get_account_metrics(self) -> Dict[str, Any]:
        """Get current account metrics"""
        return {
            'current_balance': self.metrics['current_balance'],
            'buying_power': self.metrics['buying_power'],
            'cash_reserve': self.metrics['cash_reserve'],
            'total_positions_value': self.metrics['total_positions_value'],
            'unrealized_pl': self.metrics['unrealized_pl'],
            'realized_pl': self.metrics['realized_pl'],
            'total_pl': self.metrics['unrealized_pl'] + self.metrics['realized_pl'],
            'total_pl_percent': ((self.metrics['unrealized_pl'] + self.metrics['realized_pl']) / 
                               self.metrics['starting_balance'] * 100),
            'high_water_mark': self.metrics['high_water_mark'],
            'drawdown': (self.metrics['high_water_mark'] - self.metrics['current_balance']) / 
                       self.metrics['high_water_mark'] * 100 if self.metrics['high_water_mark'] > 0 else 0,
            'last_updated': self.metrics['last_updated']
        }

    def calculate_position_size(self, entry_price: float, stop_price: float) -> Dict[str, Any]:
        """Calculate position size based on risk parameters and current account value"""
        try:
            # Get risk parameters
            risk_percent = self.config.get('account_management.risk_management.position_sizing.risk_per_trade_percent', 1.0)
            min_position_pct = self.config.get('account_management.risk_management.position_sizing.min_position_percent', 3.0)
            max_position_pct = self.config.get('account_management.risk_management.position_sizing.max_position_percent', 20.0)
            
            # Calculate risk amounts
            max_risk_amount = (self.metrics['current_balance'] * risk_percent) / 100
            risk_per_share = abs(entry_price - stop_price)
            
            if risk_per_share == 0:
                return {'error': 'Invalid risk per share'}
            
            # Calculate position size
            shares = int(max_risk_amount / risk_per_share)
            position_value = shares * entry_price
            
            # Apply percentage-based limits
            min_position = (self.metrics['current_balance'] * min_position_pct) / 100
            max_position = min(
                (self.metrics['current_balance'] * max_position_pct) / 100,
                self.metrics['buying_power']
            )
            
            # Adjust shares based on limits
            if position_value < min_position:
                shares = int(min_position / entry_price)
            elif position_value > max_position:
                shares = int(max_position / entry_price)
            
            # Round to preferred increment
            increment = self.config.get('account_management.risk_management.position_sizing.preferred_share_increment', 5)
            shares = round(shares / increment) * increment
            
            # Calculate final values
            final_position_value = shares * entry_price
            final_risk_amount = shares * risk_per_share
            
            return {
                'shares': shares,
                'position_value': final_position_value,
                'risk_amount': final_risk_amount,
                'risk_percent': (final_risk_amount / self.metrics['current_balance']) * 100,
                'position_percent': (final_position_value / self.metrics['current_balance']) * 100
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating position size: {str(e)}")
            return {'error': str(e)}
