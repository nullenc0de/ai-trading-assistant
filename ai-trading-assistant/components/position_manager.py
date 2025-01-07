import logging
from typing import Dict, Any
from datetime import datetime
import pandas as pd

class PositionManager:
    def __init__(self, performance_tracker):
        self.performance_tracker = performance_tracker
        self.logger = logging.getLogger(__name__)

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
                    
                update_data = {
                    'stop_price': new_stop,
                    'notes': f"Stop adjusted to ${new_stop:.2f}. Reason: {action.get('reason', 'No reason provided')}"
                }
                
                if self.performance_tracker.update_trade(symbol, update_data):
                    self.logger.info(f"Adjusted stop to ${new_stop:.2f} for {symbol}")
                else:
                    self.logger.error(f"Failed to adjust stop for {symbol}")
                    
            except ValueError as e:
                self.logger.error(f"Invalid stop price format in params: {action.get('params')} - {e}")
                
        except Exception as e:
            self.logger.error(f"Stop adjustment error for {symbol}: {str(e)}")
