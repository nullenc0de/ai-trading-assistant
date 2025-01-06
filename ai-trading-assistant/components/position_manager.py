import logging
from typing import Dict, Any
from datetime import datetime
import pandas as pd

class PositionManager:
    def __init__(self, performance_tracker):
        self.performance_tracker = performance_tracker
        self.logger = logging.getLogger(__name__)

    async def handle_position_action(self, symbol: str, action: Dict[str, Any], position: Dict[str, Any], current_data: Dict[str, Any]):
        try:
            action_type = action.get('action', 'HOLD').upper()
            current_price = current_data['current_price']
            
            self.logger.info(f"Handling action for {symbol}: {action_type}")
            self.logger.info(f"Action details: {action}")
            
            if action_type == 'EXIT':
                exit_data = {
                    'status': 'CLOSED',
                    'exit_price': current_price,
                    'exit_time': datetime.now().isoformat(),
                    'profit_loss': (current_price - position['entry_price']) * float(position['size']),
                    'profit_loss_percent': ((current_price / position['entry_price']) - 1) * 100,
                    'notes': f"Exit reason: {action.get('reason', 'No reason provided')}"
                }
                self.performance_tracker.update_trade(symbol, exit_data)
                self.logger.info(f"Closed position in {symbol} at ${current_price:.2f}")

            elif action_type == 'PARTIAL_EXIT':
                current_size = float(position['size'])
                exit_size = current_size // 2  # Exit half position
                remaining_size = current_size - exit_size
                
                # Calculate P&L for exited portion
                exit_pl = (current_price - position['entry_price']) * exit_size
                
                # Create exit trade record
                exit_trade = {
                    'symbol': symbol,
                    'entry_price': position['entry_price'],
                    'exit_price': current_price,
                    'position_size': exit_size,
                    'status': 'CLOSED',
                    'exit_time': datetime.now().isoformat(),
                    'profit_loss': exit_pl,
                    'profit_loss_percent': ((current_price / position['entry_price']) - 1) * 100,
                    'notes': f"Partial exit. Reason: {action.get('reason', 'No reason provided')}"
                }
                self.performance_tracker.log_trade(exit_trade)

                # Update remaining position
                update_data = {
                    'position_size': remaining_size,
                    'notes': f"Partial exit of {exit_size} shares at ${current_price:.2f}"
                }
                self.performance_tracker.update_trade(symbol, update_data)
                self.logger.info(f"Partial exit of {exit_size} shares in {symbol}")

            elif action_type == 'ADJUST_STOPS':
                if action.get('params'):
                    try:
                        # Extract new stop price from params
                        params_str = action['params']
                        if '=' in params_str:
                            new_stop = float(params_str.split('=')[1].strip())
                        else:
                            new_stop = float(params_str.strip())
                            
                        update_data = {
                            'stop_price': new_stop,
                            'notes': f"Stop adjusted to ${new_stop:.2f}. Reason: {action.get('reason', 'No reason provided')}"
                        }
                        self.performance_tracker.update_trade(symbol, update_data)
                        self.logger.info(f"Adjusted stop to ${new_stop:.2f} for {symbol}")
                    except ValueError as e:
                        self.logger.error(f"Invalid stop price format in params: {action.get('params')} - {e}")

            elif action_type == 'HOLD':
                self.logger.info(f"Maintaining position in {symbol}: {action.get('reason', 'No reason provided')}")

            self.performance_tracker._update_metrics()

        except Exception as e:
            self.logger.error(f"Position action error: {str(e)}")
            return None
