"""
Position Manager Module
---------------------
Handles position management, risk management, and trade execution.
Includes automatic stop loss enforcement and position sizing.

Author: AI Trading Assistant
Version: 2.1
Last Updated: 2025-01-07
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import pandas as pd

class PositionManager:
    def __init__(self, performance_tracker, account_manager):
        self.performance_tracker = performance_tracker
        self.account_manager = account_manager
        self.logger = logging.getLogger(__name__)
        self.open_positions: Dict[str, Any] = {}

    async def handle_position_action(self, symbol: str, action: Dict[str, Any], 
                                   position: Dict[str, Any], current_data: Dict[str, Any]) -> None:
        """Handle position actions with strict stop loss enforcement"""
        try:
            # Validate inputs
            if not all(k in position for k in ['entry_price', 'size', 'stop_price']):
                raise ValueError(f"Invalid position data for {symbol}")
            if not current_data.get('current_price'):
                raise ValueError(f"Missing current price for {symbol}")

            current_price = float(current_data['current_price'])
            stop_price = float(position['stop_price'])
            entry_price = float(position['entry_price'])
            
            # First check if stop loss is hit - this overrides any LLM decision
            if current_price <= stop_price:
                self.logger.info(f"Stop loss triggered for {symbol} at ${current_price:.2f}")
                await self._handle_exit(symbol, current_price, position, {
                    'action': 'EXIT',
                    'reason': f"Stop loss triggered at ${current_price:.2f}"
                })
                return

            # Check for large adverse moves (2% below entry)
            adverse_move = (entry_price - current_price) / entry_price
            if adverse_move > 0.02:  # 2% loss
                self.logger.info(f"Large adverse move detected for {symbol}: {adverse_move:.2%}")
                await self._handle_exit(symbol, current_price, position, {
                    'action': 'EXIT',
                    'reason': f"Large adverse move of {adverse_move:.2%}"
                })
                return

            # Handle normal position management
            action_type = action.get('action', 'HOLD').upper()
            self.logger.info(f"Handling action for {symbol}: {action_type}")
            
            if action_type == 'EXIT':
                await self._handle_exit(symbol, current_price, position, action)
            elif action_type == 'PARTIAL_EXIT':
                await self._handle_partial_exit(symbol, current_price, position, action)
            elif action_type == 'ADJUST_STOPS':
                await self._handle_stop_adjustment(symbol, position, action)
            elif action_type == 'HOLD':
                # Update position tracking even on hold
                self._update_position_metrics(symbol, current_price)
                self.logger.info(f"Maintaining position in {symbol}: {action.get('reason', 'No reason provided')}")

        except Exception as e:
            self.logger.error(f"Position action error for {symbol}: {str(e)}")

    async def _handle_exit(self, symbol: str, current_price: float, 
                         position: Dict[str, Any], action: Dict[str, Any]) -> None:
        """Handle position exit with P&L calculation"""
        try:
            entry_price = float(position['entry_price'])
            position_size = float(position['size'])
            
            # Calculate P&L
            profit_loss = (current_price - entry_price) * position_size
            profit_loss_percent = ((current_price / entry_price) - 1) * 100
            
            exit_data = {
                'status': 'CLOSED',
                'exit_price': current_price,
                'exit_time': datetime.now().isoformat(),
                'profit_loss': profit_loss,
                'profit_loss_percent': profit_loss_percent,
                'notes': f"Exit reason: {action.get('reason', 'No reason provided')}"
            }
            
            if self.performance_tracker.update_trade(symbol, exit_data):
                self.logger.info(
                    f"Closed position in {symbol} at ${current_price:.2f} "
                    f"(P&L: ${profit_loss:.2f}, {profit_loss_percent:.2f}%)"
                )
                
                # Remove from open positions tracking
                if symbol in self.open_positions:
                    self._record_closed_position(symbol, exit_data)
            else:
                self.logger.error(f"Failed to close position in {symbol}")
                
        except Exception as e:
            self.logger.error(f"Exit handling error for {symbol}: {str(e)}")

    def _update_position_metrics(self, symbol: str, current_price: float) -> None:
        """Update metrics for an open position and check risk limits"""
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
            
            # Check risk thresholds
            self._check_risk_thresholds(symbol, position)
            
        except Exception as e:
            self.logger.error(f"Error updating position metrics for {symbol}: {str(e)}")

    def _check_risk_thresholds(self, symbol: str, position: Dict[str, Any]) -> None:
        """Check if position has breached any risk thresholds"""
        try:
            unrealized_pl_percent = position['unrealized_pl_percent']
            
            # Check maximum adverse excursion
            max_adverse_excursion = self.account_manager.config.get(
                'trading.rules.exit.max_adverse_excursion', 0.02
            )
            
            if unrealized_pl_percent < -max_adverse_excursion * 100:
                self.logger.warning(
                    f"{symbol} has exceeded maximum adverse excursion: {unrealized_pl_percent:.2f}%"
                )
                # This could trigger an automatic exit if desired
            
            # Check time-based exit if enabled
            if self.account_manager.config.get('trading.rules.exit.time_based_exit', False):
                max_hold_hours = self.account_manager.config.get(
                    'trading.rules.exit.max_hold_time_hours', 48
                )
                
                hold_time = (
                    datetime.now() - 
                    datetime.fromisoformat(position['entry_time'])
                ).total_seconds() / 3600
                
                if hold_time > max_hold_hours:
                    self.logger.warning(
                        f"{symbol} has exceeded maximum hold time: {hold_time:.1f} hours"
                    )
                    # This could trigger an automatic exit if desired
            
        except Exception as e:
            self.logger.error(f"Error checking risk thresholds for {symbol}: {str(e)}")

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
        """Handle stop loss adjustment with validation"""
        try:
            if not action.get('params'):
                self.logger.error(f"Missing stop price parameters for {symbol}")
                return
                
            entry_price = float(position['entry_price'])
            current_price = float(position['current_price'])
            
            try:
                # Parse new stop price
                params_str = action['params']
                if '=' in params_str:
                    new_stop = float(params_str.split('=')[1].strip())
                else:
                    new_stop = float(params_str.strip())
                
                # Validate new stop price
                if new_stop >= current_price:
                    self.logger.warning(f"Invalid stop price for {symbol}: above current price")
                    return
                    
                # Check if new risk is acceptable
                position_size = float(position['size'])
                new_risk = (current_price - new_stop) * position_size
                account_value = self.account_manager.get_account_metrics()['current_balance']
                max_risk_percent = self.account_manager.config.get(
                    'account.risk_management.position_sizing.risk_per_trade_percent', 1.0
                )
                
                if (new_risk / account_value) * 100 > max_risk_percent:
                    self.logger.warning(f"New stop would exceed risk limits for {symbol}")
                    return
                
                # Update stop price
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
