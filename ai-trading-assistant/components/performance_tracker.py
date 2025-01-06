import os
import json
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List

class PerformanceTracker:
    def __init__(self, log_dir='performance_logs'):
        """Initialize Performance Tracker with enhanced logging"""
        self.log_dir = log_dir
        self.trades_file = os.path.join(log_dir, 'trades.csv')
        self.metrics_file = os.path.join(log_dir, 'metrics.json')
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Create log directory
        os.makedirs(log_dir, exist_ok=True)
        
        # Initialize log files
        self._init_log_files()

    def _init_log_files(self) -> None:
        """Initialize log files with proper structure"""
        try:
            # Initialize trades CSV if it doesn't exist
            if not os.path.exists(self.trades_file):
                columns = [
                    'timestamp', 'symbol', 'entry_price', 'exit_price',
                    'target_price', 'stop_price', 'position_size',
                    'confidence', 'type', 'simulated', 'status',
                    'profit_loss', 'profit_loss_percent', 'exit_time',
                    'reason', 'notes'
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
        """Log new trade with validation"""
        try:
            # Validate trade data
            required_fields = ['symbol', 'entry_price']
            if not all(field in trade_data for field in required_fields):
                raise ValueError("Missing required trade data fields")
            
            # Add timestamp if not provided
            if 'timestamp' not in trade_data:
                trade_data['timestamp'] = datetime.now().isoformat()
                
            # For paper trading, mark trade as simulated
            trade_data['simulated'] = trade_data.get('simulated', True)
            trade_data['type'] = trade_data.get('type', 'PAPER')
            trade_data['status'] = trade_data.get('status', 'OPEN')
            
            # Create trade row
            trade_row = {
                'timestamp': trade_data['timestamp'],
                'symbol': trade_data['symbol'],
                'entry_price': trade_data.get('entry_price'),
                'target_price': trade_data.get('target_price'),
                'stop_price': trade_data.get('stop_price'),
                'position_size': trade_data.get('size', 100),
                'confidence': trade_data.get('confidence'),
                'reason': trade_data.get('reason', ''),
                'type': trade_data['type'],
                'simulated': trade_data['simulated'],
                'status': trade_data['status'],
                'exit_price': None,
                'exit_time': None,
                'profit_loss': None,
                'profit_loss_percent': None,
                'notes': trade_data.get('notes', '')
            }
            
            # Log to CSV
            df = pd.read_csv(self.trades_file)
            df = pd.concat([df, pd.DataFrame([trade_row])], ignore_index=True)
            df.to_csv(self.trades_file, index=False)
            
            # Update metrics
            self._update_metrics()
            
            self.logger.info(f"Trade logged for {trade_data['symbol']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging trade: {str(e)}")
            return False

    def update_trade(self, symbol: str, updates: Dict[str, Any]) -> bool:
        """Update existing trade with new data"""
        try:
            df = pd.read_csv(self.trades_file)
            
            # Find the most recent open trade for this symbol
            mask = (df['symbol'] == symbol) & (df['status'] == 'OPEN')
            if not mask.any():
                self.logger.warning(f"No open trade found for {symbol}")
                return False
            
            # Get the index of the most recent open trade
            trade_idx = df[mask].index[-1]
            
            # Update the trade
            for key, value in updates.items():
                df.at[trade_idx, key] = value
                
            # If closing the trade, calculate P&L
            if updates.get('status') == 'CLOSED' and 'exit_price' in updates:
                entry_price = df.at[trade_idx, 'entry_price']
                exit_price = updates['exit_price']
                position_size = df.at[trade_idx, 'position_size']
                
                profit_loss = (exit_price - entry_price) * position_size
                profit_loss_percent = ((exit_price / entry_price) - 1) * 100
                
                df.at[trade_idx, 'profit_loss'] = profit_loss
                df.at[trade_idx, 'profit_loss_percent'] = profit_loss_percent
                df.at[trade_idx, 'exit_time'] = updates.get('exit_time', datetime.now().isoformat())
            
            # Save updates
            df.to_csv(self.trades_file, index=False)
            
            # Update metrics immediately
            self._update_metrics()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating trade: {str(e)}")
            return False

    def _update_metrics(self) -> None:
        """Update performance metrics"""
        try:
            df = pd.read_csv(self.trades_file)
            closed_trades = df[df['status'] == 'CLOSED'].copy()
            
            if len(closed_trades) == 0:
                metrics = {
                    'total_trades': len(df),
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
            else:
                # Calculate metrics for closed trades
                winners = closed_trades[closed_trades['profit_loss'] > 0]
                losers = closed_trades[closed_trades['profit_loss'] < 0]
                
                metrics = {
                    'total_trades': len(df),
                    'winning_trades': len(winners),
                    'losing_trades': len(losers),
                    'win_rate': (len(winners) / len(closed_trades) * 100) if len(closed_trades) > 0 else 0.0,
                    'avg_profit_loss': closed_trades['profit_loss'].mean() if not closed_trades.empty else 0.0,
                    'largest_win': winners['profit_loss'].max() if not winners.empty else 0.0,
                    'largest_loss': losers['profit_loss'].min() if not losers.empty else 0.0,
                    'average_win': winners['profit_loss'].mean() if not winners.empty else 0.0,
                    'average_loss': losers['profit_loss'].mean() if not losers.empty else 0.0,
                }
                
                # Calculate drawdown
                equity_curve = (1 + closed_trades['profit_loss_percent'] / 100).cumprod()
                rolling_max = equity_curve.expanding().max()
                drawdowns = (equity_curve - rolling_max) / rolling_max * 100
                metrics['max_drawdown'] = abs(drawdowns.min()) if not drawdowns.empty else 0.0
                
                # Calculate profit factor
                total_profit = winners['profit_loss'].sum() if not winners.empty else 0
                total_loss = abs(losers['profit_loss'].sum()) if not losers.empty else 0
                metrics['profit_factor'] = (
                    total_profit / total_loss if total_loss > 0 else 
                    float('inf') if total_profit > 0 else 0.0
                )
                
                metrics['last_updated'] = datetime.now().isoformat()

            # Save metrics
            with open(self.metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error updating metrics: {str(e)}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        try:
            # Force update metrics before returning
            self._update_metrics()
            
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error getting metrics: {str(e)}")
            return {}

    def get_trade_history(self, symbol: Optional[str] = None, days: Optional[int] = None) -> pd.DataFrame:
        """Get trade history with optional filtering"""
        try:
            df = pd.read_csv(self.trades_file)
            
            # Apply filters
            if symbol:
                df = df[df['symbol'] == symbol]
            
            if days:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                cutoff = datetime.now() - timedelta(days=days)
                df = df[df['timestamp'] >= cutoff]
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error getting trade history: {str(e)}")
            return pd.DataFrame()

    def get_open_positions(self) -> pd.DataFrame:
        """Get currently open positions"""
        try:
            df = pd.read_csv(self.trades_file)
            return df[df['status'] == 'OPEN'].copy()
        except Exception as e:
            self.logger.error(f"Error getting open positions: {str(e)}")
            return pd.DataFrame()

    def generate_report(self, days: Optional[int] = None) -> str:
        """Generate comprehensive trading performance report"""
        try:
            df = pd.read_csv(self.trades_file)
            
            # Filter by date if specified
            if days:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                cutoff = datetime.now() - timedelta(days=days)
                df = df[df['timestamp'] >= cutoff]
            
            # Load metrics
            metrics = self.get_metrics()
            
            # Generate report sections
            sections = []
            
            # Overall Performance
            sections.append("OVERALL PERFORMANCE")
            sections.append("-" * 20)
            sections.append(f"Total Trades: {metrics['total_trades']}")
            sections.append(f"Win Rate: {metrics['win_rate']:.2f}%")
            sections.append(f"Profit Factor: {metrics['profit_factor']:.2f}")
            sections.append(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
            
            # Trade Statistics
            sections.append("\nTRADE STATISTICS")
            sections.append("-" * 20)
            sections.append(f"Average Win: ${metrics['average_win']:.2f}")
            sections.append(f"Average Loss: ${metrics['average_loss']:.2f}")
            sections.append(f"Largest Win: ${metrics['largest_win']:.2f}")
            sections.append(f"Largest Loss: ${metrics['largest_loss']:.2f}")
            
            # Recent Activity
            sections.append("\nRECENT TRADES")
            sections.append("-" * 20)
            if not df.empty:
                recent = df.tail(5)[['timestamp', 'symbol', 'profit_loss', 'status']]
                sections.append(recent.to_string(index=False))
            
            # Active Positions
            open_positions = df[df['status'] == 'OPEN']
            if not open_positions.empty:
                sections.append("\nACTIVE POSITIONS")
                sections.append("-" * 20)
                positions = open_positions[['symbol', 'entry_price', 'target_price', 'stop_price']]
                sections.append(positions.to_string(index=False))
            
            return "\n".join(sections)
            
        except Exception as e:
            self.logger.error(f"Error generating report: {str(e)}")
            return "Unable to generate performance report"

    def export_data(self, format: str = 'csv') -> Optional[str]:
        """Export trading data to specified format"""
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
                
            self.logger.info(f"Data exported to {export_path}")
            return export_path
            
        except Exception as e:
            self.logger.error(f"Error exporting data: {str(e)}")
            return None

    def reset_statistics(self) -> bool:
        """Reset performance statistics"""
        try:
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
            
            # Clear trades file
            columns = [
                'timestamp', 'symbol', 'entry_price', 'exit_price',
                'target_price', 'stop_price', 'position_size',
                'confidence', 'type', 'simulated', 'status',
                'profit_loss', 'profit_loss_percent', 'exit_time',
                'reason', 'notes'
            ]
            pd.DataFrame(columns=columns).to_csv(self.trades_file, index=False)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error resetting statistics: {str(e)}")
            return False

    def calculate_daily_stats(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Calculate daily trading statistics"""
        try:
            df = pd.read_csv(self.trades_file)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter for specific date
            if date is None:
                date = datetime.now()
            
            daily_trades = df[df['timestamp'].dt.date == date.date()]
            
            if daily_trades.empty:
                return {
                    'date': date.strftime('%Y-%m-%d'),
                    'total_trades': 0,
                    'profit_loss': 0.0,
                    'win_rate': 0.0,
                    'active_positions': 0
                }
            
            closed_trades = daily_trades[daily_trades['status'] == 'CLOSED']
            winners = closed_trades[closed_trades['profit_loss'] > 0]
            
            stats = {
                'date': date.strftime('%Y-%m-%d'),
                'total_trades': len(daily_trades),
                'profit_loss': closed_trades['profit_loss'].sum() if not closed_trades.empty else 0.0,
                'win_rate': (len(winners) / len(closed_trades) * 100) if not closed_trades.empty else 0.0,
                'active_positions': len(daily_trades[daily_trades['status'] == 'OPEN'])
            }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error calculating daily stats: {str(e)}")
            return {}

    def validate_trade_data(self, trade_data: Dict[str, Any]) -> bool:
        """Validate trade data structure and values"""
        try:
            # Required fields
            required = ['symbol', 'entry_price', 'target_price', 'stop_price']
            if not all(field in trade_data for field in required):
                return False
                
            # Numeric validation
            numeric_fields = ['entry_price', 'target_price', 'stop_price', 'position_size']
            for field in numeric_fields:
                if field in trade_data:
                    value = trade_data[field]
                    if not isinstance(value, (int, float)) or value <= 0:
                        return False
            
            # Logic validation
            if trade_data['stop_price'] >= trade_data['entry_price']:
                return False
            if trade_data['target_price'] <= trade_data['entry_price']:
                return False
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating trade data: {str(e)}")
            return False

    def analyze_performance_by_setup(self) -> Dict[str, Any]:
        """Analyze performance metrics grouped by setup type"""
        try:
            df = pd.read_csv(self.trades_file)
            closed_trades = df[df['status'] == 'CLOSED'].copy()
            
            if closed_trades.empty:
                return {}
            
            # Group by reason/setup type
            grouped = closed_trades.groupby('reason').agg({
                'profit_loss': ['count', 'mean', 'sum'],
                'profit_loss_percent': 'mean'
            }).round(2)
            
            # Calculate win rate per setup
            def calculate_win_rate(group):
                winners = len(group[group['profit_loss'] > 0])
                return (winners / len(group) * 100) if len(group) > 0 else 0
                
            win_rates = closed_trades.groupby('reason').apply(calculate_win_rate)
            
            # Format results
            results = {}
            for setup in grouped.index:
                results[setup] = {
                    'total_trades': int(grouped.loc[setup, ('profit_loss', 'count')]),
                    'avg_profit_loss': float(grouped.loc[setup, ('profit_loss', 'mean')]),
                    'total_profit_loss': float(grouped.loc[setup, ('profit_loss', 'sum')]),
                    'avg_profit_loss_percent': float(grouped.loc[setup, ('profit_loss_percent', 'mean')]),
                    'win_rate': float(win_rates[setup])
                }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error analyzing performance by setup: {str(e)}")
            return {}
