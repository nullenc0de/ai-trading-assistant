import os
import json
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List

class PerformanceTracker:
    def __init__(self, log_dir='performance_logs'):
        """Initialize Performance Tracker with trade logging and metrics"""
        self.log_dir = log_dir
        self.trades_file = os.path.join(log_dir, 'trades.csv')
        self.metrics_file = os.path.join(log_dir, 'metrics.json')
        self.logger = logging.getLogger(__name__)
        os.makedirs(log_dir, exist_ok=True)
        self._init_log_files()

    def _init_log_files(self) -> None:
        """Initialize log files with proper structure"""
        try:
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
                initial_metrics = {
                    'total_trades': 0,
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
                    'last_updated': datetime.now().isoformat()
                }
                with open(self.metrics_file, 'w') as f:
                    json.dump(initial_metrics, f, indent=2)
                    
        except Exception as e:
            self.logger.error(f"Error initializing log files: {str(e)}")
            raise

    def log_trade(self, trade_data: Dict[str, Any]) -> bool:
        """Log a new trade with validation"""
        try:
            symbol = trade_data.get('symbol')
            if not symbol:
                self.logger.error("Missing symbol in trade data")
                return False

            # Validate required fields
            required_fields = ['entry_price', 'target_price', 'stop_price']
            if not all(trade_data.get(field) is not None for field in required_fields):
                self.logger.error(f"Missing required trade data fields for {symbol}")
                return False

            # Check for existing open position
            df = pd.read_csv(self.trades_file)
            if not df.empty:
                open_position = df[(df['symbol'] == symbol) & (df['status'] == 'OPEN')]
                if not open_position.empty:
                    self.logger.warning(f"Open position already exists for {symbol}")
                    return False

            trade_row = {
                'timestamp': trade_data.get('timestamp', datetime.now().isoformat()),
                'symbol': symbol,
                'entry_price': trade_data['entry_price'],
                'target_price': trade_data['target_price'],
                'stop_price': trade_data['stop_price'],
                'position_size': trade_data.get('size', 100),
                'confidence': trade_data.get('confidence'),
                'reason': trade_data.get('reason', ''),
                'type': trade_data.get('type', 'PAPER'),
                'simulated': True,
                'status': 'OPEN',
                'exit_price': None,
                'exit_time': None,
                'profit_loss': None,
                'profit_loss_percent': None,
                'notes': trade_data.get('notes', '')
            }
            
            # Use more robust DataFrame concatenation
            new_row_df = pd.DataFrame([trade_row])
            df = pd.concat([df, new_row_df], ignore_index=True, sort=False)
            df.to_csv(self.trades_file, index=False)
            
            self.logger.info(f"Trade logged for {symbol}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging trade: {str(e)}")
            return False

    def update_trade(self, symbol: str, updates: Dict[str, Any]) -> bool:
        """Update existing trade with validation"""
        try:
            df = pd.read_csv(self.trades_file)
            
            # Find the most recent open trade for the symbol
            mask = (df['symbol'] == symbol) & (df['status'] == 'OPEN')
            if not mask.any():
                self.logger.warning(f"No open trade found for {symbol}")
                return False
            
            trade_idx = df[mask].index[-1]
            
            # Validate exit price when closing position
            if updates.get('status') == 'CLOSED':
                if 'exit_price' not in updates:
                    self.logger.error(f"Missing exit price for {symbol} position closure")
                    return False
                
                entry_price = df.at[trade_idx, 'entry_price']
                exit_price = updates['exit_price']
                position_size = df.at[trade_idx, 'position_size']
                
                if pd.isna(entry_price):
                    self.logger.error(f"Invalid entry price for {symbol}")
                    return False
                
                # Calculate P&L
                df.at[trade_idx, 'profit_loss'] = (exit_price - entry_price) * position_size
                df.at[trade_idx, 'profit_loss_percent'] = ((exit_price / entry_price) - 1) * 100
                df.at[trade_idx, 'exit_time'] = updates.get('exit_time', datetime.now().isoformat())
            
            # Update trade data
            for key, value in updates.items():
                df.at[trade_idx, key] = value
            
            df.to_csv(self.trades_file, index=False)
            self._update_metrics()
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating trade: {str(e)}")
            return False

    def get_open_positions(self) -> pd.DataFrame:
        """Get all open positions"""
        try:
            df = pd.read_csv(self.trades_file)
            return df[df['status'] == 'OPEN'].copy()
        except Exception as e:
            self.logger.error(f"Error getting open positions: {str(e)}")
            return pd.DataFrame()

    def _update_metrics(self) -> None:
        """Update performance metrics"""
        try:
            df = pd.read_csv(self.trades_file)
            closed_trades = df[df['status'] == 'CLOSED'].copy()
            
            if len(closed_trades) == 0:
                return
                
            winners = closed_trades[closed_trades['profit_loss'] > 0]
            losers = closed_trades[closed_trades['profit_loss'] < 0]
            
            metrics = {
                'total_trades': len(closed_trades),
                'winning_trades': len(winners),
                'losing_trades': len(losers),
                'win_rate': (len(winners) / len(closed_trades) * 100) if len(closed_trades) > 0 else 0.0,
                'avg_profit_loss': closed_trades['profit_loss'].mean(),
                'largest_win': winners['profit_loss'].max() if not winners.empty else 0.0,
                'largest_loss': losers['profit_loss'].min() if not losers.empty else 0.0,
                'average_win': winners['profit_loss'].mean() if not winners.empty else 0.0,
                'average_loss': losers['profit_loss'].mean() if not losers.empty else 0.0,
                'last_updated': datetime.now().isoformat()
            }
            
            # Calculate drawdown
            if not closed_trades.empty:
                equity_curve = closed_trades.sort_values('exit_time')
                equity_curve['cumulative_pl'] = equity_curve['profit_loss'].cumsum()
                equity_curve['running_max'] = equity_curve['cumulative_pl'].cummax()
                drawdown = (equity_curve['cumulative_pl'] - equity_curve['running_max'])
                metrics['max_drawdown'] = abs(drawdown.min()) if not drawdown.empty else 0.0
            
            # Calculate profit factor
            total_profit = winners['profit_loss'].sum() if not winners.empty else 0
            total_loss = abs(losers['profit_loss'].sum()) if not losers.empty else 0
            metrics['profit_factor'] = total_profit / total_loss if total_loss > 0 else float('inf') if total_profit > 0 else 0.0
            
            with open(self.metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error updating metrics: {str(e)}")
