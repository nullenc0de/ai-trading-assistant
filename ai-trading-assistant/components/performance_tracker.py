# components/performance_tracker.py
import os
import json
from datetime import datetime
import pandas as pd
import logging

class PerformanceTracker:
    def __init__(self, log_dir='performance_logs'):
        """
        Initialize Performance Tracker
        
        Args:
            log_dir (str): Directory to store performance logs
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # Initialize log file
        self._init_log_file()

    def _init_log_file(self):
        """
        Initialize performance log file if it doesn't exist
        """
        log_file = os.path.join(self.log_dir, 'trades.csv')
        if not os.path.exists(log_file):
            # Create initial CSV with headers
            columns = [
                'timestamp', 'symbol', 'entry_price', 'confidence', 
                'setup_details', 'outcome', 'profit_loss'
            ]
            pd.DataFrame(columns=columns).to_csv(log_file, index=False)

    def log_trade(self, symbol, entry_price, confidence, setup_details, outcome=None, profit_loss=None):
        """
        Log a trading setup or trade
        
        Args:
            symbol (str): Stock symbol
            entry_price (float): Entry price
            confidence (float): Trading setup confidence
            setup_details (str): Details of the trading setup
            outcome (str, optional): Trade outcome
            profit_loss (float, optional): Profit or loss amount
        """
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'entry_price': entry_price,
                'confidence': confidence,
                'setup_details': setup_details,
                'outcome': outcome,
                'profit_loss': profit_loss
            }
            
            log_file = os.path.join(self.log_dir, 'trades.csv')
            
            # Append to CSV
            df = pd.read_csv(log_file)
            df = df.append(log_entry, ignore_index=True)
            df.to_csv(log_file, index=False)
            
            logging.info(f"Logged trade for {symbol}")
        
        except Exception as e:
            logging.error(f"Error logging trade: {str(e)}")

    def generate_report(self):
        """
        Generate comprehensive trading performance report
        
        Returns:
            str: Formatted performance report
        """
        try:
            log_file = os.path.join(self.log_dir, 'trades.csv')
            df = pd.read_csv(log_file)
            
            # Basic performance metrics
            report_sections = []
            
            # Total Trades
            total_trades = len(df)
            report_sections.append(f"Total Trades: {total_trades}")
            
            # Confidence Distribution
            confidence_stats = df['confidence'].describe()
            report_sections.append("\nConfidence Levels:")
            report_sections.append(f"Average Confidence: {confidence_stats['mean']:.2f}%")
            report_sections.append(f"Min Confidence: {confidence_stats['min']:.2f}%")
            report_sections.append(f"Max Confidence: {confidence_stats['max']:.2f}%")
            
            # Symbol Performance
            symbol_performance = df.groupby('symbol').agg({
                'confidence': 'mean',
                'entry_price': 'count'
            }).rename(columns={'entry_price': 'trade_count'})
            
            report_sections.append("\nTop Traded Symbols:")
            top_symbols = symbol_performance.sort_values('trade_count', ascending=False).head(5)
            report_sections.append(top_symbols.to_string())
            
            # Generate JSON report for detailed analysis
            json_report_path = os.path.join(self.log_dir, 'performance_report.json')
            with open(json_report_path, 'w') as f:
                json.dump({
                    'total_trades': total_trades,
                    'confidence_stats': confidence_stats.to_dict(),
                    'symbol_performance': symbol_performance.to_dict()
                }, f, indent=2)
            
            return "\n".join(report_sections)
        
        except Exception as e:
            logging.error(f"Error generating performance report: {str(e)}")
            return "Unable to generate performance report"