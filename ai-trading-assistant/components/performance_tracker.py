# components/performance_tracker.py
import os
import json
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

class PerformanceTracker:
    def __init__(self, log_dir='performance_logs'):
        """
        Initialize Performance Tracker with enhanced analytics
        
        Args:
            log_dir (str): Directory to store performance logs
        """
        self.log_dir = log_dir
        self.trades_file = os.path.join(log_dir, 'trades.csv')
        self.metrics_file = os.path.join(log_dir, 'metrics.json')
        
        # Create log directory
        os.makedirs(log_dir, exist_ok=True)
        
        # Initialize log files
        self._init_log_files()
        
        # Performance metrics cache
        self._metrics_cache = {}
        self._last_cache_update = None
        self._cache_duration = timedelta(minutes=5)

    def _init_log_files(self) -> None:
        """Initialize log files with proper structure"""
        try:
            # Initialize trades CSV if it doesn't exist
            if not os.path.exists(self.trades_file):
                columns = [
                    'timestamp', 'symbol', 'entry_price', 'exit_price',
                    'position_size', 'profit_loss', 'profit_loss_percent',
                    'trade_duration', 'setup_type', 'confidence',
                    'initial_stop', 'target', 'actual_risk_reward',
                    'market_conditions', 'notes'
                ]
                pd.DataFrame(columns=columns).to_csv(self.trades_file, index=False)
            
            # Initialize metrics JSON if it doesn't exist
            if not os.path.exists(self.metrics_file):
                initial_metrics = {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'win_rate': 0.0,
                    'avg_profit_loss': 0.0,
                    'max_drawdown': 0.0,
                    'sharpe_ratio': 0.0,
                    'profit_factor': 0.0,
                    'largest_win': 0.0,
                    'largest_loss': 0.0,
                    'average_win': 0.0,
                    'average_loss': 0.0,
                    'risk_reward_ratio': 0.0,
                    'last_updated': datetime.now().isoformat()
                }
                with open(self.metrics_file, 'w') as f:
                    json.dump(initial_metrics, f, indent=2)
                    
        except Exception as e:
            logging.error(f"Error initializing log files: {str(e)}")
            raise

    def log_trade(self, trade_data: Dict[str, Any]) -> bool:
        """
        Log trade with enhanced data validation
        
        Args:
            trade_data (dict): Complete trade information
            
        Returns:
            bool: True if successfully logged
        """
        try:
            # Validate required fields
            required_fields = ['symbol', 'entry_price', 'position_size']
            if not all(field in trade_data for field in required_fields):
                raise ValueError("Missing required trade data fields")
            
            # Add timestamp if not provided
            if 'timestamp' not in trade_data:
                trade_data['timestamp'] = datetime.now().isoformat()
            
            # Calculate additional metrics if exit price is provided
            if 'exit_price' in trade_data:
                trade_data['profit_loss'] = (
                    (trade_data['exit_price'] - trade_data['entry_price']) *
                    trade_data['position_size']
                )
                trade_data['profit_loss_percent'] = (
                    (trade_data['exit_price'] / trade_data['entry_price'] - 1) * 100
                )
            
            # Append to CSV
            df = pd.read_csv(self.trades_file)
            df = pd.concat([df, pd.DataFrame([trade_data])], ignore_index=True)
            df.to_csv(self.trades_file, index=False)
            
            # Update metrics
            self._update_metrics()
            
            logging.info(f"Trade logged for {trade_data['symbol']}")
            return True
            
        except Exception as e:
            logging.error(f"Error logging trade: {str(e)}")
            return False

    def _update_metrics(self) -> None:
        """Update performance metrics based on trade history"""
        try:
            df = pd.read_csv(self.trades_file)
            
            # Filter completed trades
            completed_trades = df.dropna(subset=['exit_price'])
            
            if len(completed_trades) == 0:
                return
            
            # Calculate basic metrics
            metrics = {
                'total_trades': len(completed_trades),
                'winning_trades': len(completed_trades[completed_trades['profit_loss'] > 0]),
                'losing_trades': len(completed_trades[completed_trades['profit_loss'] < 0])
            }
            
            # Win rate
            metrics['win_rate'] = (
                metrics['winning_trades'] / metrics['total_trades'] * 100
                if metrics['total_trades'] > 0 else 0
            )
            
            # Profit metrics
            profits = completed_trades['profit_loss']
            metrics.update({
                'total_profit_loss': profits.sum(),
                'avg_profit_loss': profits.mean(),
                'largest_win': profits.max(),
                'largest_loss': profits.min(),
                'average_win': profits[profits > 0].mean() if len(profits[profits > 0]) > 0 else 0,
                'average_loss': profits[profits < 0].mean() if len(profits[profits < 0]) > 0 else 0
            })
            
            # Risk metrics
            metrics['profit_factor'] = (
                abs(profits[profits > 0].sum() / profits[profits < 0].sum())
                if len(profits[profits < 0]) > 0 and profits[profits < 0].sum() != 0
                else 0
            )
            
            # Calculate drawdown
            cumulative_returns = (1 + completed_trades['profit_loss_percent'] / 100).cumprod()
            rolling_max = cumulative_returns.expanding().max()
            drawdowns = (cumulative_returns - rolling_max) / rolling_max * 100
            metrics['max_drawdown'] = abs(drawdowns.min())
            
            # Risk-adjusted returns
            returns = completed_trades['profit_loss_percent'] / 100
            if len(returns) > 1:
                avg_return = returns.mean()
                std_return = returns.std()
                risk_free_rate = 0.02  # Assumed 2% risk-free rate
                metrics['sharpe_ratio'] = (
                    (avg_return - risk_free_rate) / std_return * np.sqrt(252)
                    if std_return > 0 else 0
                )
            
            # Add timestamp
            metrics['last_updated'] = datetime.now().isoformat()
            
            # Save metrics
            with open(self.metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
            
            # Update cache
            self._metrics_cache = metrics
            self._last_cache_update = datetime.now()
            
        except Exception as e:
            logging.error(f"Error updating metrics: {str(e)}")

    def get_metrics(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get current performance metrics
        
        Args:
            use_cache (bool): Use cached metrics if available
            
        Returns:
            dict: Current performance metrics
        """
        try:
            # Check cache
            if use_cache and self._last_cache_update:
                cache_age = datetime.now() - self._last_cache_update
                if cache_age < self._cache_duration:
                    return self._metrics_cache
            
            # Load latest metrics
            with open(self.metrics_file, 'r') as f:
                metrics = json.load(f)
            
            # Update cache
            self._metrics_cache = metrics
            self._last_cache_update = datetime.now()
            
            return metrics
            
        except Exception as e:
            logging.error(f"Error getting metrics: {str(e)}")
            return {}

    def generate_report(self, days: Optional[int] = None) -> str:
        """
        Generate comprehensive trading performance report
        
        Args:
            days (int, optional): Number of days to include in report
            
        Returns:
            str: Formatted performance report
        """
        try:
            # Load trade data
            df = pd.read_csv(self.trades_file)
            
            # Filter by date if specified
            if days:
                cutoff_date = datetime.now() - timedelta(days=days)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df[df['timestamp'] >= cutoff_date]
            
            # Get current metrics
            metrics = self.get_metrics(use_cache=False)
            
            # Generate report sections
            sections = []
            
            # Overall Performance
            sections.append("OVERALL PERFORMANCE")
            sections.append("-" * 20)
            sections.append(f"Total Trades: {metrics['total_trades']}")
            sections.append(f"Win Rate: {metrics['win_rate']:.2f}%")
            sections.append(f"Profit Factor: {metrics['profit_factor']:.2f}")
            sections.append(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
            sections.append(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
            
            # Trade Statistics
            sections.append("\nTRADE STATISTICS")
            sections.append("-" * 20)
            sections.append(f"Average Win: ${metrics['average_win']:.2f}")
            sections.append(f"Average Loss: ${metrics['average_loss']:.2f}")
            sections.append(f"Largest Win: ${metrics['largest_win']:.2f}")
            sections.append(f"Largest Loss: ${metrics['largest_loss']:.2f}")
            
            # Symbol Performance
            if not df.empty:
                sections.append("\nSYMBOL PERFORMANCE")
                sections.append("-" * 20)
                symbol_stats = df.groupby('symbol').agg({
                    'profit_loss': ['count', 'sum', 'mean'],
                    'profit_loss_percent': 'mean'
                }).round(2)
                sections.append(symbol_stats.to_string())
            
            # Recent Trades
            sections.append("\nRECENT TRADES")
            sections.append("-" * 20)
            if not df.empty:
                recent_trades = df.tail(5)[
                    ['timestamp', 'symbol', 'profit_loss', 'profit_loss_percent']
                ].round(2)
                sections.append(recent_trades.to_string())
            
            return "\n".join(sections)
            
        except Exception as e:
            logging.error(f"Error generating report: {str(e)}")
            return "Unable to generate performance report"

    def analyze_trade_patterns(self) -> Dict[str, Any]:
        """
        Analyze trading patterns and provide insights
        
        Returns:
            dict: Trading pattern analysis
        """
        try:
            df = pd.read_csv(self.trades_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            patterns = {
                'best_performing_symbols': [],
                'best_times': [],
                'setup_performance': {},
                'consecutive_trades': {
                    'wins': 0,
                    'losses': 0
                }
            }
            
            if not df.empty:
                # Best performing symbols
                symbol_performance = df.groupby('symbol').agg({
                    'profit_loss': 'sum',
                    'profit_loss_percent': 'mean'
                }).sort_values('profit_loss', ascending=False)
                patterns['best_performing_symbols'] = symbol_performance.head(5).to_dict()
                
                # Best trading times
                df['hour'] = df['timestamp'].dt.hour
                hourly_performance = df.groupby('hour')['profit_loss'].mean()
                patterns['best_times'] = hourly_performance.nlargest(3).to_dict()
                
                # Setup type performance
                if 'setup_type' in df.columns:
                    setup_stats = df.groupby('setup_type').agg({
                        'profit_loss': ['count', 'mean', 'sum'],
                        'profit_loss_percent': 'mean'
                    })
                    patterns['setup_performance'] = setup_stats.to_dict()
                
                # Consecutive trade analysis
                df['is_win'] = df['profit_loss'] > 0
                patterns['consecutive_trades'] = {
                    'wins': self._find_longest_streak(df['is_win'], True),
                    'losses': self._find_longest_streak(df['is_win'], False)
                }
            
            return patterns
            
        except Exception as e:
            logging.error(f"Error analyzing trade patterns: {str(e)}")
            return {}

    def _find_longest_streak(self, series: pd.Series, value: bool) -> int:
        """
        Find longest streak of consecutive values
        
        Args:
            series (pd.Series): Series of boolean values
            value (bool): Value to find streak for
            
        Returns:
            int: Length of longest streak
        """
        max_streak = current_streak = 0
        for val in series:
            if val == value:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        return max_streak

    def export_data(self, format: str = 'csv') -> Optional[str]:
        """
        Export trading data to specified format
        
        Args:
            format (str): Export format ('csv' or 'json')
            
        Returns:
            str: Path to exported file
        """
        try:
            export_dir = os.path.join(self.log_dir, 'exports')
            os.makedirs(export_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            if format.lower() == 'csv':
                export_path = os.path.join(export_dir, f'trading_data_{timestamp}.csv')
                df = pd.read_csv(self.trades_file)
                df.to_csv(export_path, index=False)
                
            elif format.lower() == 'json':
                export_path = os.path.join(export_dir, f'trading_data_{timestamp}.json')
                df = pd.read_csv(self.trades_file)
                df.to_json(export_path, orient='records', indent=2)
                
            else:
                raise ValueError(f"Unsupported export format: {format}")
                
            logging.info(f"Data exported to {export_path}")
            return export_path
            
        except Exception as e:
            logging.error(f"Error exporting data: {str(e)}")
            return None
