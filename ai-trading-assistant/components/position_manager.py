"""
Position Manager Module
----------------------
Handles all aspects of position management including:
- Position entry and exit execution
- Position sizing and risk calculations
- Stop loss management
- Portfolio metrics tracking
- Risk management enforcement

This module integrates with the account manager and performance tracker
to maintain a complete view of the trading system's positions and risk exposure.

Author: AI Trading Assistant
Version: 2.0
Last Updated: 2025-01-07
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import pandas as pd

class PositionManager:
    def __init__(self, performance_tracker, account_manager):
        self.performance_tracker = performance_tracker
        self.account_manager = account_manager
        self.logger = logging.getLogger(__name__)
        self.open_positions: Dict[str, Any] = {}

    def calculate_position_size(self, symbol: str, entry_price: float, stop_price: float) -> Dict[str, Any]:
        """Calculate appropriate position size based on risk parameters"""
        try:
            # Get account metrics
            account_value = self.account_manager.get_account_metrics()['current_balance']
            risk_per_trade = self.account_manager.config.get(
                'account_management.risk_management.position_sizing.risk_per_trade_percent', 1.0
            )
            
            # Calculate risk amounts
            max_risk_amount = (account_value * risk_per_trade) / 100
            risk_per_share = abs(entry_price - stop_price)
            
            if risk_per_share == 0:
                return {'error': 'Invalid risk per share'}
            
            # Calculate shares based on risk
            shares = int(max_risk_amount / risk_per_share)
            position_value = shares * entry_price
            
            # Apply position size limits
            max_position_pct = self.account_manager.config.get(
                'account_management.risk_management.position_sizing.max_position_percent', 20.0
            )
            max_position_value = (account_value * max_position_pct) / 100
            
            if position_value > max_position_value:
                shares = int(max_position_value / entry_price)
                position_value = shares * entry_price
            
            return {
                'shares': shares,
                'position_value': position_value,
                'risk_amount': shares * risk_per_share,
                'risk_percent': (shares * risk_per_share / account_value) * 100
            }
            
        except Exception as e:
            self.logger.error(f"Position sizing error for {symbol}: {str(e)}")
            return {'error': str(e)}

    async def handle_position_action(self, symbol: str, action: Dict[str, Any], 
                                   position: Dict[str, Any], current_data: Dict[str, Any]) -> None:
        """Handle position actions with validation"""
        try:
            # Validate inputs
            if not all(k in position for k in ['entry_price', 'size']):
                raise ValueError(f"Invalid position data for {symbol}")
            if not current_data.get('current_price'):
                raise ValueError(f"Missing current price for {symbol}")

            action_type = action.get('action', 'HOLD').upper()
            current_price = float(current_data['current_price'])
            
            self.logger.info(f"Handling action for {symbol}: {action_type}")
            self.logger.info(f"Action details: {action}")
            
            if action_type == 'EXIT':
                await self._handle_exit(symbol, current_price, position, action)
                
            elif action_type == 'PARTIAL_EXIT':
                await self._handle_partial_exit(symbol, current_price, position, action)
                
            elif action_type == 'ADJUST_STOPS':
                await self._handle_stop_adjustment(symbol, position, action)
                
            elif action_type == 'HOLD':
                self.logger.info(f"Maintaining position in {symbol}: {action.get('reason', 'No reason provided')}")
            
            else:
                self.logger.warning(f"Unknown action type: {action_type}")

            # Update position tracking
            if symbol in self.open_positions:
                self._update_position_metrics(symbol, current_price)

        except Exception as e:
            self.logger.error(f"Position action error for {symbol}: {str(e)}")

    async def _handle_exit(self, symbol: str, current_price: float, 
                         position: Dict[str, Any], action: Dict[str, Any]) -> None:
        """Handle position exit"""
        try:
            entry_price = float(position['entry_price'])
            position_size = float(position['size'])
            
            exit_data = {
                'status': 'CLOSED',
                'exit_price': current_price,
                'exit_time': datetime.now().isoformat(),
                'profit_loss': (current_price - entry_price) * position_size,
                'profit_loss_percent': ((current_price / entry_price) - 1) * 100,
                'notes': f"Exit reason: {action.get('reason', 'No reason provided')}"
            }
            
            if self.performance_tracker.update_trade(symbol, exit_data):
                self.logger.info(f"Closed position in {symbol} at ${current_price:.2f}")
                
                # Remove from open positions tracking
                if symbol in self.open_positions:
                    self._record_closed_position(symbol, exit_data)
            else:
                self.logger.error(f"Failed to close position in {symbol}")
                
        except Exception as e:
            self.logger.error(f"Exit handling error for {symbol}: {str(e)}")

    async def _handle_partial_exit(self, symbol: str, current_price: float, 
                                position: Dict[str, Any], action: Dict[str, Any]) -> None:
        """Handle partial position exit"""
        try:
            current_size = float(position['size'])
            exit_size = current_size / 2  # Exit half position
            remaining_size = current_size - exit_size
            
            entry_price = float(position['entry_price'])
            
            # Create exit trade record
            exit_trade = {
                'symbol': symbol,
                'entry_price': entry_price,
                'exit_price': current_price,
                'position_size': exit_size,
                'status': 'CLOSED',
                'exit_time': datetime.now().isoformat(),
                'profit_loss': (current_price - entry_price) * exit_size,
                'profit_loss_percent': ((current_price / entry_price) - 1) * 100,
                'notes': f"Partial exit. Reason: {action.get('reason', 'No reason provided')}"
            }
            
            if self.performance_tracker.log_trade(exit_trade):
                # Update remaining position
                update_data = {
                    'position_size': remaining_size,
                    'notes': f"Partial exit of {exit_size} shares at ${current_price:.2f}"
                }
                
                if self.performance_tracker.update_trade(symbol, update_data):
                    self.logger.info(f"Partial exit of {exit_size} shares in {symbol}")
                    
                    # Update position tracking
                    if symbol in self.open_positions:
                        self.open_positions[symbol]['shares'] = remaining_size
                        self._update_position_metrics(symbol, current_price)
                else:
                    self.logger.error(f"Failed to update remaining position in {symbol}")
            else:
                self.logger.error(f"Failed to log partial exit for {symbol}")
                
        except Exception as e:
            self.logger.error(f"Partial exit handling error for {symbol}: {str(e)}")

    async def _handle_stop_adjustment(self, symbol: str, position: Dict[str, Any], 
                                   action: Dict[str, Any]) -> None:
        """Handle stop loss adjustment"""
        try:
            if not action.get('params'):
                self.logger.error(f"Missing stop price parameters for {symbol}")
                return
                
            try:
                params_str = action['params']
                if '=' in params_str:
                    new_stop = float(params_str.split('=')[1].strip())
                else:
                    new_stop = float(params_str.strip())
                    
                # Validate new stop price
                entry_price = float(position['entry_price'])
                if new_stop >= entry_price:
                    self.logger.warning(f"Invalid stop price for {symbol}: above entry price")
                    return
                    
                # Check if new risk is acceptable
                position_size = float(position['size'])
                new_risk = (entry_price - new_stop) * position_size
                account_value = self.account_manager.get_account_metrics()['current_balance']
                max_risk_percent = self.account_manager.config.get(
                    'account_management.risk_management.position_sizing.risk_per_trade_percent', 1.0
                )
                
                if (new_risk / account_value) * 100 > max_risk_percent:
                    self.logger.warning(f"New stop would exceed risk limits for {symbol}")
                    return
                
                update_data = {
                    'stop_price': new_stop,
                    'notes': f"Stop adjusted to ${new_stop:.2f}. Reason: {action.get('reason', 'No reason provided')}"
                }
                
                if self.performance_tracker.update_trade(symbol, update_data):
                    self.logger.info(f"Adjusted stop to ${new_stop:.2f} for {symbol}")
                    
                    # Update position tracking
                    if symbol in self.open_positions:
                        self.open_positions[symbol]['stop_price'] = new_stop
                else:
                    self.logger.error(f"Failed to adjust stop for {symbol}")
                    
            except ValueError as e:
                self.logger.error(f"Invalid stop price format in params: {action.get('params')} - {e}")
                
        except Exception as e:
            self.logger.error(f"Stop adjustment error for {symbol}: {str(e)}")

    def _update_position_metrics(self, symbol: str, current_price: float) -> None:
        """Update metrics for an open position"""
        try:
            if symbol not in self.open_positions:
                return
                
            position = self.open_positions[symbol]
            entry_price = position['entry_price']
            shares = position['shares']
            
            # Update current values
            position['current_price'] = current_price
            position['current_value'] = current_price * shares
            position['unrealized_pl'] = (current_price - entry_price) * shares
            position['unrealized_pl_percent'] = ((current_price / entry_price) - 1) * 100
            
            # Update high/low prices
            position['high_price'] = max(position.get('high_price', current_price), current_price)
            position['low_price'] = min(position.get('low_price', current_price), current_price)
            
        except Exception as e:
            self.logger.error(f"Error updating position metrics for {symbol}: {str(e)}")

    def _record_closed_position(self, symbol: str, exit_data: Dict[str, Any]) -> None:
        """Record position closure details"""
        try:
            position = self.open_positions.pop(symbol)
            
            # Calculate final metrics
            position.update({
                'exit_price': exit_data['exit_price'],
                'exit_time': exit_data['exit_time'],
                'final_pl': exit_data['profit_loss'],
                'final_pl_percent': exit_data['profit_loss_percent'],
                'hold_time_hours': (
                    datetime.fromisoformat(exit_data['exit_time']) - 
                    datetime.fromisoformat(position['entry_time'])
                ).total_seconds() / 3600,
                'status': 'CLOSED'
            })
            
        except Exception as e:
            self.logger.error(f"Error recording closed position for {symbol}: {str(e)}")

    def get_portfolio_metrics(self) -> Dict[str, Any]:
        """Get current portfolio metrics"""
        try:
            metrics = {
                'open_positions_count': len(self.open_positions),
                'total_exposure': sum(pos['current_value'] for pos in self.open_positions.values()),
                'total_unrealized_pl': sum(pos['unrealized_pl'] for pos in self.open_positions.values()),
                'positions': {}
            }
            
            account_value = self.account_manager.get_account_metrics()['current_balance']
            
            # Calculate exposure and risk metrics
            if account_value > 0:
                metrics['total_exposure_percent'] = (metrics['total_exposure'] / account_value) * 100
                metrics['total_unrealized_pl_percent'] = (metrics['total_unrealized_pl'] / account_value) * 100
            
            # Add individual position details
            for symbol, position in self.open_positions.items():
                metrics['positions'][symbol] = {
                    'current_price': position['current_price'],
                    'entry_price': position['entry_price'],
                    'shares': position['shares'],
                    'current_value': position['current_value'],
                    'unrealized_pl': position['unrealized_pl'],
                    'unrealized_pl_percent': position['unrealized_pl_percent'],
                    'high_price': position.get('high_price'),
                    'low_price': position.get('low_price'),
                    'hold_time_hours': (
                        datetime.now() - 
                        datetime.fromisoformat(position['entry_time'])
                    ).total_seconds() / 3600
                }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Error getting portfolio metrics: {str(e)}")
            return {}
