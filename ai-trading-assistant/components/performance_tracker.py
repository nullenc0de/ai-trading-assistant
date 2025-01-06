import os
import json
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List

class PerformanceTracker:
    def __init__(self, log_dir='performance_logs'):
        self.log_dir = log_dir
        self.trades_file = os.path.join(log_dir, 'trades.csv')
        self.metrics_file = os.path.join(log_dir, 'metrics.json')
        self.logger = logging.getLogger(__name__)
        os.makedirs(log_dir, exist_ok=True)
        self._init_log_files()

    def _init_log_files(self) -> None:
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
        try:
            if not all(field in trade_data for field in ['symbol', 'entry_price']):
                raise ValueError("Missing required trade data fields")
            
            trade_row = {
                'timestamp': trade_data.get('timestamp', datetime.now().isoformat()),
                'symbol': trade_data['symbol'],
                'entry_price': trade_data.get('entry_price'),
                'target_price': trade_data.get('target_price'),
                'stop_price': trade_data.get('stop_price'),
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
            
            df = pd.read_csv(self.trades_file)
            df = pd.concat([df, pd.DataFrame([trade_row])], ignore_index=True)
            df.to_csv(self.trades_file, index=False)
            
            self.logger.info(f"Trade logged for {trade_data['symbol']}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error logging trade: {str(e)}")
            return False

    def update_trade(self, symbol: str, updates: Dict[str, Any]) -> bool:
        try:
            df = pd.read_csv(self.trades_file)
            
            mask = (df['symbol'] == symbol) & (df['status'] == 'OPEN')
            if not mask.any():
                self.logger.warning(f"No open trade found for {symbol}")
                return False
            
            trade_idx = df[mask].index[-1]
            
            for key, value in updates.items():
                df.at[trade_idx, key] = value
                
            if updates.get('status') == 'CLOSED' and 'exit_price' in updates:
                entry_price = df.at[trade_idx, 'entry_price']
                exit_price = updates['exit_price']
                position_size = df.at[trade_idx, 'position_size']
                
                df.at[trade_idx, 'profit_loss'] = (exit_price - entry_price) * position_size
                df.at[trade_idx, 'profit_loss_percent'] = ((exit_price / entry_price) - 1) * 100
                df.at[trade_idx, 'exit_time'] = updates.get('exit_time', datetime.now().isoformat())
            
            df.to_csv(self.trades_file, index=False)
            self._update_metrics()
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating trade: {str(e)}")
            return False

    def _update_metrics(self) -> None:
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
                winners = closed_trades[closed_trades['profit_loss'] > 0]
                losers = closed_trades[closed_trades['profit_loss'] < 0]
                
                metrics = {
                    'total_trades': len(df),
                    'winning_trades': len(winners),
                    'losing_trades': len(losers),
                    'win_rate': (len(winners) / len(closed_trades) * 100) if len(closed_trades) > 0 else 0.0,
                    'avg_profit_loss': closed_trades['profit_loss'].mean(),
                    'largest_win': winners['profit_loss'].max() if not winners.empty else 0.0,
                    'largest_loss': losers['profit_loss'].min() if not losers.empty else 0.0,
                    'average_win': winners['profit_loss'].mean() if not winners.empty else 0.0,
                    'average_loss': losers['profit_loss'].mean() if not losers.empty else 0.0,
                }
                
                # Calculate drawdown
                equity_curve = closed_trades.sort_values('exit_time')
                equity_curve['cumulative_pl'] = equity_curve['profit_loss'].cumsum()
                equity_curve['running_max'] = equity_curve['cumulative_pl'].cummax()
                drawdown = (equity_curve['cumulative_pl'] - equity_curve['running_max']) / equity_curve['running_max'] * 100
                metrics['max_drawdown'] = abs(drawdown.min()) if not drawdown.empty else 0.0
                
                # Calculate profit factor
                total_profit = winners['profit_loss'].sum() if not winners.empty else 0
                total_loss = abs(losers['profit_loss'].sum()) if not losers.empty else 0
                metrics['profit_factor'] = (
                    total_profit / total_loss if total_loss > 0 else float('inf') if total_profit > 0 else 0.0
                )
                
            with open(self.metrics_file, 'w') as f:
                json.dump(metrics, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Error updating metrics: {str(e)}")

    def get_metrics(self) -> Dict[str, Any]:
        try:
            self._update_metrics()
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error getting metrics: {str(e)}")
            return {}

    def get_open_positions(self) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.trades_file)
            return df[df['status'] == 'OPEN'].copy()
        except Exception as e:
            self.logger.error(f"Error getting open positions: {str(e)}")
            return pd.DataFrame()

    def get_trade_history(self, symbol: Optional[str] = None, days: Optional[int] = None) -> pd.DataFrame:
        try:
            df = pd.read_csv(self.trades_file)
            
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

    def generate_report(self, days: Optional[int] = None) -> str:
        try:
            df = pd.read_csv(self.trades_file)
            
            if days:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                cutoff = datetime.now() - timedelta(days=days)
                df = df[df['timestamp'] >= cutoff]
            
            metrics = self.get_metrics()
            sections = []
            
            sections.append("OVERALL PERFORMANCE")
            sections.append("-" * 20)
            sections.append(f"Total Trades: {metrics['total_trades']}")
            sections.append(f"Win Rate: {metrics['win_rate']:.2f}%")
            sections.append(f"Profit Factor: {metrics['profit_factor']:.2f}")
            sections.append(f"Max Drawdown: {metrics['max_drawdown']:.2f}%")
            
            sections.append("\nTRADE STATISTICS")
            sections.append("-" * 20)
            sections.append(f"Average Win: ${metrics['average_win']:.2f}")
            sections.append(f"Average Loss: ${metrics['average_loss']:.2f}")
            sections.append(f"Largest Win: ${metrics['largest_win']:.2f}")
            sections.append(f"Largest Loss: ${metrics['largest_loss']:.2f}")
            
            if not df.empty:
                sections.append("\nRECENT TRADES")
                sections.append("-" * 20)
                recent = df.tail(5)[['timestamp', 'symbol', 'profit_loss', 'status']]
                sections.append(recent.to_string(index=False))
            
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
