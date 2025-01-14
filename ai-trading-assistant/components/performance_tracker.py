import os
import json
import pandas as pd
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from threading import Lock

class PerformanceTracker:
    def __init__(self, log_dir='performance_logs'):
        """Initialize Performance Tracker with enhanced metrics tracking"""
        self.log_dir = log_dir
        self.trades_file = os.path.join(log_dir, 'trades.csv')
        self.metrics_file = os.path.join(log_dir, 'metrics.json')
        self.logger = logging.getLogger(__name__)
        self._lock = Lock()  # Add thread safety
        os.makedirs(log_dir, exist_ok=True)
        
        self.logger.info("Initializing performance log files...")
        self._init_log_files()
        self.logger.info("Performance tracker initialized.")

    def _init_log_files(self) -> None:
        """Initialize log files with proper structure"""
        try:
            with self._lock:
                self.logger.debug("Checking trades.csv")
                # Initialize trades.csv if it doesn't exist
                if not os.path.exists(self.trades_file):
                    columns = [
                        'timestamp', 'symbol', 'entry_price', 'exit_price',
                        'target_price', 'stop_price', 'position_size',
                        'confidence', 'type', 'simulated', 'status',
                        'profit_loss', 'profit_loss_percent', 'exit_time',
                        'reason', 'notes'
                    ]
                    self.logger.debug("Writing trades.csv")
                    pd.DataFrame(columns=columns).to_csv(self.trades_file, index=False)
                    self.logger.debug("trades.csv initialized")
self.logger.debug("Checking metrics.json")  
                # Initialize metrics.json with default structure if it doesn't exist
                # or if it's invalid
                try:
                    if os.path.exists(self.metrics_file):
                        with open(self.metrics_file, 'r') as f:
                            self.logger.debug("metrics.json loaded successfully")
                            json.load(f)  # Test if valid JSON
                    else:
                        self.logger.debug("Saving default metrics")
                        self._save_metrics(self._create_default_metrics())
                except json.JSONDecodeError:
                    self.logger.warning("Invalid metrics.json found. Reinitializing with defaults.")
                    self._save_metrics(self._create_default_metrics())
                    
        except Exception as e:
            self.logger.error(f"Error initializing log files: {str(e)}")
            self._ensure_valid_metrics_file()

    def _create_default_metrics(self) -> Dict[str, Any]:
        """Create default metrics dictionary"""
        return {
            'total_trades': 0,
            'open_trades': 0,
            'closed_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'avg_profit_loss': 0.0,
            'largest_win': 0.0,
            'largest_loss': 0.0,
            'average_win': 0.0,
            'average_loss': 0.0,
            'total_profit': 0.0,
            'total_loss': 0.0,
            'max_drawdown': 0.0,
            'profit_factor': 0.0,
            'open_positions_count': 0,
            'open_positions': [],
            'open_exposure': 0.0,
            'last_updated': datetime.now().isoformat()
        }

    def _save_metrics(self, metrics: Dict[str, Any]) -> None:
        """Save metrics to file with thread safety"""
        try:
            with self._lock:
                with open(self.metrics_file, 'w') as f:
                    json.dump(metrics, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving metrics: {str(e)}")

    def _ensure_valid_metrics_file(self) -> None:
        """Ensure metrics file exists and contains valid JSON"""
        try:
            default_metrics = self._create_default_metrics()
            with open(self.metrics_file, 'w') as f:
                json.dump(default_metrics, f, indent=4)
        except Exception as e:
            self.logger.error(f"Critical error ensuring valid metrics file: {str(e)}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        try:
            with self._lock:
                with open(self.metrics_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error getting metrics: {str(e)}")
            return self._create_default_metrics()

    def get_open_positions(self) -> pd.DataFrame:
        """Get all open positions with thread safety"""
        try:
            with self._lock:
                df = pd.read_csv(self.trades_file)
                return df[df['status'] == 'OPEN'].copy()
        except Exception as e:
            self.logger.error(f"Error getting open positions: {str(e)}")
            return pd.DataFrame()

    def log_trade(self, trade_data: Dict[str, Any], force_update: bool = True) -> bool:
        """Log a new trade with validation"""
        try:
            with self._lock:
                df = pd.read_csv(self.trades_file)
                
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
        """Update existing trade with validation"""
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
                
                df.to_csv(self.trades_file, index=False)
                
                if force_update:
                    self._update_metrics()
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error updating trade: {str(e)}")
            return False

    def _update_metrics(self) -> None:
        """Update performance metrics"""
        try:
            with self._lock:
                df = pd.read_csv(self.trades_file)
                metrics = self._calculate_metrics(df)
                self._save_metrics(metrics)
        except Exception as e:
            self.logger.error(f"Error updating metrics: {str(e)}")

    def _calculate_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate performance metrics from trade data"""
        metrics = self._create_default_metrics()
        try:
            if df.empty:
                return metrics

            closed_trades = df[df['status'] == 'CLOSED']
            open_trades = df[df['status'] == 'OPEN']

            if not closed_trades.empty:
                winners = closed_trades[closed_trades['profit_loss'] > 0]
                losers = closed_trades[closed_trades['profit_loss'] < 0]

                metrics.update({
                    'total_trades': len(closed_trades),
                    'winning_trades': len(winners),
                    'losing_trades': len(losers),
                    'win_rate': (len(winners) / len(closed_trades) * 100) if len(closed_trades) > 0 else 0.0,
                    'total_profit': winners['profit_loss'].sum() if not winners.empty else 0.0,
                    'total_loss': abs(losers['profit_loss'].sum()) if not losers.empty else 0.0,
                    'largest_win': winners['profit_loss'].max() if not winners.empty else 0.0,
                    'largest_loss': losers['profit_loss'].min() if not losers.empty else 0.0,
                    'average_win': winners['profit_loss'].mean() if not winners.empty else 0.0,
                    'average_loss': losers['profit_loss'].mean() if not losers.empty else 0.0
                })

            metrics['open_trades'] = len(open_trades)
            metrics['last_updated'] = datetime.now().isoformat()

            return metrics

        except Exception as e:
            self.logger.error(f"Error calculating metrics: {str(e)}")
            return metrics
