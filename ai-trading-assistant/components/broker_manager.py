from enum import Enum
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType

class BrokerType(Enum):
    ROBINHOOD = "robinhood"
    ALPACA = "alpaca"
    PAPER = "paper"

class BrokerManager:
    def __init__(self, config_manager, robinhood_client=None, alpaca_client=None):
        self.config = config_manager
        self.robinhood_client = robinhood_client
        self.alpaca_client = alpaca_client
        self.logger = logging.getLogger(__name__)
        self.broker_type = self._determine_broker_type()
        
        # Initialize account metrics
        self.metrics = {
            'starting_balance': self.config.get('account.starting_balance', 3000.00),
            'current_balance': 0.0,
            'buying_power': 0.0,
            'cash_reserve': 0.0,
            'total_positions_value': 0.0,
            'unrealized_pl': 0.0,
            'realized_pl': 0.0,
            'high_water_mark': 0.0,
            'last_updated': None
        }
        
        self._initialize_account()

    def _determine_broker_type(self) -> BrokerType:
        """Determine which broker to use based on available clients"""
        if self.alpaca_client:
            return BrokerType.ALPACA
        elif self.robinhood_client and self.robinhood_client.is_authenticated():
            return BrokerType.ROBINHOOD
        return BrokerType.PAPER

    def _initialize_account(self) -> None:
        """Initialize account metrics based on broker type"""
        try:
            if self.broker_type == BrokerType.ALPACA:
                account = self.alpaca_client.get_account()
                self.metrics['current_balance'] = float(account.equity)
                self.metrics['buying_power'] = float(account.buying_power)
                
            elif self.broker_type == BrokerType.ROBINHOOD:
                profile = self.robinhood_client.load_account_profile()
                self.metrics['current_balance'] = float(profile['equity'])
                self.metrics['buying_power'] = float(profile['buying_power'])
                
            else:  # Paper trading
                self.metrics['current_balance'] = self.metrics['starting_balance']
                self.metrics['buying_power'] = self.metrics['starting_balance']
            
            # Set initial values
            self.metrics['high_water_mark'] = self.metrics['current_balance']
            self.metrics['cash_reserve'] = self.metrics['current_balance'] * (
                self.config.get('account.risk_management.cash_reserve_percent', 10.0) / 100
            )
            self.metrics['last_updated'] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error initializing account: {str(e)}")

    def update_account_metrics(self, positions: Dict[str, Any]) -> None:
        """Update account metrics with current positions"""
        try:
            if self.broker_type == BrokerType.ALPACA:
                account = self.alpaca_client.get_account()
                positions = self.alpaca_client.get_all_positions()
                
                self.metrics['current_balance'] = float(account.equity)
                self.metrics['buying_power'] = float(account.buying_power)
                self.metrics['total_positions_value'] = sum(float(pos.market_value) for pos in positions)
                self.metrics['unrealized_pl'] = sum(float(pos.unrealized_pl) for pos in positions)
                
            elif self.broker_type == BrokerType.ROBINHOOD:
                profile = self.robinhood_client.load_account_profile()
                self.metrics['current_balance'] = float(profile['equity'])
                self.metrics['buying_power'] = float(profile['buying_power'])
                
            else:  # Paper trading
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

    def place_order(self, order_spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Place order through appropriate broker"""
        try:
            if self.broker_type == BrokerType.ALPACA:
                return self._place_alpaca_order(order_spec)
            elif self.broker_type == BrokerType.ROBINHOOD:
                return self._place_robinhood_order(order_spec)
            else:
                return self._simulate_order(order_spec)
                
        except Exception as e:
            self.logger.error(f"Error placing order: {str(e)}")
            return None

    def _place_alpaca_order(self, order_spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Place order through Alpaca"""
        try:
            side = OrderSide.BUY if order_spec['side'].lower() == 'buy' else OrderSide.SELL
            
            if order_spec.get('type', 'market').lower() == 'market':
                request = MarketOrderRequest(
                    symbol=order_spec['symbol'],
                    qty=float(order_spec['quantity']),
                    side=side,
                    time_in_force=TimeInForce.DAY
                )
            else:
                request = LimitOrderRequest(
                    symbol=order_spec['symbol'],
                    qty=float(order_spec['quantity']),
                    side=side,
                    limit_price=float(order_spec['limit_price']),
                    time_in_force=TimeInForce.DAY
                )
            
            # Place order
            order = self.alpaca_client.submit_order(request)
            
            return {
                'id': order.id,
                'status': order.status,
                'filled_qty': order.filled_qty,
                'filled_avg_price': order.filled_avg_price
            }
            
        except Exception as e:
            self.logger.error(f"Alpaca order error: {str(e)}")
            return None

    def _place_robinhood_order(self, order_spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Place order through Robinhood"""
        try:
            # Use existing Robinhood order placement logic
            return None  # Replace with actual implementation
        except Exception as e:
            self.logger.error(f"Robinhood order error: {str(e)}")
            return None

    def _simulate_order(self, order_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate order for paper trading"""
        return {
            'id': f"paper_{datetime.now().timestamp()}",
            'status': 'filled',
            'filled_qty': order_spec['quantity'],
            'filled_avg_price': order_spec.get('limit_price') or order_spec.get('price'),
            'timestamp': datetime.now().isoformat()
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions from broker"""
        try:
            if self.broker_type == BrokerType.ALPACA:
                positions = self.alpaca_client.get_all_positions()
                return [{
                    'symbol': pos.symbol,
                    'quantity': float(pos.qty),
                    'entry_price': float(pos.avg_entry_price),
                    'current_price': float(pos.current_price),
                    'market_value': float(pos.market_value),
                    'unrealized_pl': float(pos.unrealized_pl),
                    'unrealized_plpc': float(pos.unrealized_plpc)
                } for pos in positions]
                
            elif self.broker_type == BrokerType.ROBINHOOD:
                # Implement Robinhood position fetching
                return []
            
            else:  # Paper trading
                return []  # Implement paper trading position tracking
                
        except Exception as e:
            self.logger.error(f"Error getting positions: {str(e)}")
            return []

    def get_orders(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get orders from broker"""
        try:
            if self.broker_type == BrokerType.ALPACA:
                orders = self.alpaca_client.get_orders(status=status)
                return [{
                    'id': order.id,
                    'symbol': order.symbol,
                    'type': order.type.value,
                    'side': order.side.value,
                    'quantity': float(order.qty),
                    'filled_quantity': float(order.filled_qty),
                    'status': order.status,
                    'submitted_at': order.submitted_at,
                    'filled_at': order.filled_at
                } for order in orders]
                
            elif self.broker_type == BrokerType.ROBINHOOD:
                # Implement Robinhood order fetching
                return []
            
            else:  # Paper trading
                return []  # Implement paper trading order tracking
                
        except Exception as e:
            self.logger.error(f"Error getting orders: {str(e)}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order by ID"""
        try:
            if self.broker_type == BrokerType.ALPACA:
                self.alpaca_client.cancel_order_by_id(order_id)
                return True
                
            elif self.broker_type == BrokerType.ROBINHOOD:
                # Implement Robinhood order cancellation
                return False
            
            else:  # Paper trading
                return True  # Simulate successful cancellation
                
        except Exception as e:
            self.logger.error(f"Error cancelling order: {str(e)}")
            return False

    def get_account_metrics(self) -> Dict[str, Any]:
        """Get current account metrics"""
        return {
            'broker': self.broker_type.value,
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

    def check_trade_allowed(self, position_value: float, risk_amount: float) -> Dict[str, Any]:
        """Check if a trade is allowed based on account rules"""
        try:
            # Get account limits from config
            max_position_pct = self.config.get('account.risk_management.position_sizing.max_position_percent', 20.0)
            max_risk_pct = self.config.get('account.risk_management.max_account_risk', 50.0)
            max_daily_loss_pct = self.config.get('account.risk_management.limits.max_daily_loss_percent', 3.0)
            
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

    def calculate_position_size(self, entry_price: float, stop_price: float) -> Dict[str, Any]:
        """Calculate position size based on risk parameters"""
        try:
            # Get risk parameters
            risk_percent = self.config.get('account.risk_management.position_sizing.risk_per_trade_percent', 1.0)
            min_position_pct = self.config.get('account.risk_management.position_sizing.min_position_percent', 3.0)
            max_position_pct = self.config.get('account.risk_management.position_sizing.max_position_percent', 20.0)
            
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
            increment = self.config.get('account.risk_management.position_sizing.preferred_share_increment', 5)
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
