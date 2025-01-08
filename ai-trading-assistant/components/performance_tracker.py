"""
performance_tracker.py
---------------------
Enhanced with immediate updates and proper synchronization
"""
import os
import json
import pandas as pd
import numpy as np
import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
from threading import Lock

class PerformanceTracker:
    def __init__(self, log_dir='performance_logs'):
        self.log_dir = log_dir
        self.trades_file = os.path.join(log_dir, 'trades.csv')
        self.metrics_file = os.path.join(log_dir, 'metrics.json')
        self.logger = logging.getLogger(__name__)
        self._lock = Lock()  # Add thread safety
        os.makedirs(log_dir, exist_ok=True)
        self._init_log_files()

    def _init_log_files(self) -> None:
        try:
            with self._lock:
                if not os.path.exists(self.trades_file):
                    columns = [
                        'timestamp', 'symbol', 'entry_price', 'exit_price',
                        'target_price', 'stop_price', 'position_size',
                        'confidence', 'type', 'simulated', 'status',
                        'profit_loss', 'profit_loss_percent', 'exit_time',
                        'reason', 'notes'
                    ]
                    pd.DataFrame(columns=columns).to_csv(self.trades_file, index=False)
                
                if not os.path.exists(self.metrics_file):
                    self._save_metrics(self._create_default_metrics())
                    
        except Exception as e:
            self.logger.error(f"Error initializing log files: {str(e)}")
            raise

    def _create_default_metrics(self) -> Dict[str, Any]:
        return {
            'total_trades': 0,
            'open_trades': 0,
            'closed_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_profit_loss': 0.0,
            'max_drawdown': 0.0,
            'profit_factor': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0,
            'open_positions_count': 0,
            'open_positions': [],
            'open_exposure': 0.0,
            'last_updated': datetime.now().isoformat()
        }

    def log_trade(self, trade_data: Dict[str, Any], force_update: bool = True) -> bool:
        try:
            with self._lock:
                df = pd.read_csv(self.trades_file)
                
                # Validate trade data
                if not self._validate_trade_data(trade_data):
                    return False
                
                # Add timestamp if not present
                if 'timestamp' not in trade_data:
                    trade_data['timestamp'] = datetime.now().isoformat()
                
                # Append new trade
                new_row_df = pd.DataFrame([trade_data])
                df = pd.concat([df, new_row_df], ignore_index=True, sort=False)
                df.to_csv(self.trades_file, index=False)
                
                if force_update:
                    self._update_metrics()
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error logging trade: {str(e)}")
            return False

    def update_trade(self, symbol: str, updates: Dict[str, Any], force_update: bool = True) -> bool:
        try:
            with self._lock:
                df = pd.read_csv(self.trades_file)
                
                # Find open trade for symbol
                mask = (df['symbol'] == symbol) & (df['status'] == 'OPEN')
                if not mask.any():
                    self.logger.warning(f"No open trade found for {symbol}")
                    return False
                
                trade_idx = df[mask].index[-1]
                
                # Update trade data
                for key, value in updates.items():
                    df.at[trade_idx, key] = value
                
                # Calculate P&L if closing position
                if updates.get('status') == 'CLOSED' and 'exit_price' in updates:
                    entry_price = float(df.at[trade_idx, 'entry_price'])
                    exit_price = float(updates['exit_price'])
                    position_size = float(df.at[trade_idx, 'position_size'])
                    
                    df.at[trade_idx, 'profit_loss'] = (exit_price - entry_price) * position_size
                    df.at[trade_idx, 'profit_loss_percent'] = ((exit_price / entry_price) - 1) * 100
                    df.at[trade_idx, 'exit_time'] = updates.get('exit_time', datetime.now().isoformat())
                
                df.to_csv(self.trades_file, index=False)
                
                if force_update:
                    self._update_metrics()
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating trade: {str(e)}")
            return False

    def _update_metrics(self) -> None:
        try:
            with self._lock:
                df = pd.read_csv(self.trades_file)
                
                metrics = {}
                
                # Basic counts
                metrics['total_trades'] = len(df)
                metrics['open_trades'] = len(df[df['status'] == 'OPEN'])
                metrics['closed_trades'] = len(df[df['status'] == 'CLOSED'])
                
                # Process closed trades
                closed_trades = df[df['status'] == 'CLOSED']
                if not closed_trades.empty:
                    winners = closed_trades[closed_trades['profit_loss'] > 0]
                    losers = closed_trades[closed_trades['profit_loss'] < 0]
                    
                    metrics.update({
                        'winning_trades': len(winners),
                        'losing_trades': len(losers),
                        'win_rate': (len(winners) / len(closed_trades) * 100),
                        'avg_profit_loss': closed_trades['profit_loss'].mean(),
                        'largest_win': winners['profit_loss'].max() if not winners.empty else 0.0,
                        'largest_loss': losers['profit_loss'].min() if not losers.empty else 0.0,
                        'average_win': winners['profit_loss'].mean() if not winners.empty else 0.0,
                        'average_loss': losers['profit_loss'].mean() if not losers.empty else 0.0,
                        'total_profit': winners['profit_loss'].sum() if not winners.empty else 0.0,
                        'total_loss': losers['profit_loss'].sum() if not losers.empty else 0.0
                    })
                    
                    # Calculate drawdown
                    cumulative_pl = closed_trades.sort_values('exit_time')['profit_loss'].cumsum()
                    running_max = cumulative_pl.cummax()
                    drawdown = (cumulative_pl - running_max)
                    metrics['max_drawdown'] = abs(drawdown.min()) if not drawdown.empty else 0.0
                    
                    # Profit factor
                    total_profit = metrics['total_profit']
                    total_loss = abs(metrics['total_loss'])
                    metrics['profit_factor'] = total_profit / total_loss if total_loss > 0 else float('inf')
                
                # Open positions
                open_trades = df[df['status'] == 'OPEN']
                if not open_trades.empty:
                    metrics.update({
                        'open_positions_count': len(open_trades),
                        'open_positions': open_trades['symbol'].tolist(),
                        'open_exposure': open_trades['position_size'].sum(),
                        'avg_position_size': open_trades['position_size'].mean(),
                        'max_position_size': open_trades['position_size'].max(),
                        'min_position_size': open_trades['position_size'].min()
                    })
                else:
                    metrics.update({
                        'open_positions_count': 0,
                        'open_positions': [],
                        'open_exposure': 0.0,
                        'avg_position_size': 0.0,
                        'max_position_size': 0.0,
                        'min_position_size': 0.0
                    })
                
                metrics['last_updated'] = datetime.now().isoformat()
                self._save_metrics(metrics)
                
        except Exception as e:
            self.logger.error(f"Error updating metrics: {str(e)}")

    def _save_metrics(self, metrics: Dict[str, Any]) -> None:
        try:
            with self._lock:
                with open(self.metrics_file, 'w') as f:
                    json.dump(metrics, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving metrics: {str(e)}")

    def get_metrics(self) -> Dict[str, Any]:
        try:
            with self._lock:
                with open(self.metrics_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error getting metrics: {str(e)}")
            return self._create_default_metrics()

    def _validate_trade_data(self, trade_data: Dict[str, Any]) -> bool:
        required_fields = ['symbol', 'entry_price', 'position_size']
        return all(field in trade_data for field in required_fields)

"""
position_manager.py updates
-------------------------
Enhanced with immediate performance tracking updates
"""

class PositionManager:
    async def _handle_exit(self, symbol: str, current_price: float, 
                          position_data: Dict[str, Any], action: Dict[str, Any]) -> None:
        try:
            entry_price = float(position_data['entry_price'])
            position_size = float(position_data['size'])
            
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
            
            # Force immediate update of both trade and metrics
            if self.performance_tracker.update_trade(symbol, exit_data, force_update=True):
                self.logger.info(
                    f"Closed position in {symbol} at ${current_price:.2f} "
                    f"(P&L: ${profit_loss:.2f}, {profit_loss_percent:.2f}%)"
                )
                
                if symbol in self.open_positions:
                    self._record_closed_position(symbol, exit_data)
            else:
                self.logger.error(f"Failed to close position in {symbol}")
                
        except Exception as e:
            self.logger.error(f"Exit handling error for {symbol}: {str(e)}")
