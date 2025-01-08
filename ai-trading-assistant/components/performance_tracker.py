# In performance_tracker.py
def _init_log_files(self) -> None:
    """Initialize log files with proper structure"""
    try:
        with self._lock:
            # Initialize trades.csv if it doesn't exist
            if not os.path.exists(self.trades_file):
                columns = [
                    'timestamp', 'symbol', 'entry_price', 'exit_price',
                    'target_price', 'stop_price', 'position_size',
                    'confidence', 'type', 'simulated', 'status',
                    'profit_loss', 'profit_loss_percent', 'exit_time',
                    'reason', 'notes'
                ]
                pd.DataFrame(columns=columns).to_csv(self.trades_file, index=False)
            
            # Initialize metrics.json with default structure if it doesn't exist
            # or if it's invalid
            try:
                if os.path.exists(self.metrics_file):
                    with open(self.metrics_file, 'r') as f:
                        json.load(f)  # Test if valid JSON
                else:
                    self._save_metrics(self._create_default_metrics())
            except json.JSONDecodeError:
                self.logger.warning("Invalid metrics.json found. Reinitializing with defaults.")
                self._save_metrics(self._create_default_metrics())
                
    except Exception as e:
        self.logger.error(f"Error initializing log files: {str(e)}")
        self._ensure_valid_metrics_file()

def _ensure_valid_metrics_file(self) -> None:
    """Ensure metrics file exists and contains valid JSON"""
    try:
        default_metrics = self._create_default_metrics()
        with open(self.metrics_file, 'w') as f:
            json.dump(default_metrics, f, indent=4)
    except Exception as e:
        self.logger.error(f"Critical error ensuring valid metrics file: {str(e)}")

# In stock_analyzer.py
def analyze_stock(self, symbol: str) -> Optional[Dict[str, Any]]:
    """Analyze stock with improved error handling"""
    try:
        # Validate symbol first
        if not isinstance(symbol, str) or not symbol.strip():
            self.logger.warning(f"Invalid symbol provided: {symbol}")
            return None

        # Check cache first
        if symbol in self.analysis_cache:
            cache_time, cache_data = self.analysis_cache[symbol]
            if datetime.now() - cache_time < self.cache_duration:
                return cache_data

        # Fetch stock data with error handling
        try:
            stock = yf.Ticker(symbol)
            
            # Get historical data with proper error handling
            data = {}
            intervals = {
                '1m': '1d',
                '5m': '5d',
                'daily': '1mo'
            }
            
            for interval, period in intervals.items():
                try:
                    df = stock.history(period=period, interval=interval)
                    if not df.empty:
                        data[interval] = df
                except Exception as e:
                    self.logger.warning(f"Could not fetch {interval} data for {symbol}: {str(e)}")
                    continue
            
            # If we couldn't get any data, return None
            if not data:
                self.logger.warning(f"No data available for {symbol}")
                return None

            # Continue with analysis only if we have minimum required data
            if '1m' not in data:
                self.logger.warning(f"Insufficient historical data for {symbol}")
                return None

            # Get current trading data
            current_price = data['1m']['Close'].iloc[-1]
            current_volume = data['1m']['Volume'].sum()
            
            # Get stock info with error handling
            try:
                stock_info = stock.info
            except Exception as e:
                self.logger.warning(f"Could not fetch info for {symbol}: {str(e)}")
                stock_info = {}

            # Calculate necessary metrics
            avg_volume = stock_info.get('averageVolume', 0)
            rel_volume = current_volume / avg_volume if avg_volume > 0 else 0

            if not self._passes_filters(current_price, current_volume, rel_volume):
                return None

            # Calculate technical indicators for available timeframes
            technical_data = {
                timeframe: self.calculate_technical_indicators(df)
                for timeframe, df in data.items()
            }

            # Format analysis results
            analysis_result = {
                'symbol': symbol,
                'current_price': current_price,
                'technical_indicators': technical_data.get('1m', {}).get('technical_indicators', {}),
                'volume_analysis': {
                    'current_volume': current_volume,
                    'avg_volume': avg_volume,
                    'rel_volume': rel_volume
                }
            }

            # Cache results
            self.analysis_cache[symbol] = (datetime.now(), analysis_result)
            return analysis_result

        except Exception as e:
            self.logger.error(f"Error analyzing {symbol}: {str(e)}")
            return None

    except Exception as e:
        self.logger.error(f"Fatal error analyzing {symbol}: {str(e)}")
        return None

# In main.py - Update the symbol analysis function
async def analyze_symbol(self, symbol: str):
    """Analyze symbol with improved error handling"""
    try:
        if not symbol or not isinstance(symbol, str):
            return

        self.metrics['trades_analyzed'] += 1
        
        stock_data = self.analyzer.analyze_stock(symbol)
        if not stock_data:
            return

        # Validate required data
        if 'current_price' not in stock_data:
            self.logger.warning(f"Missing required price data for {symbol}")
            return

        technical_data = stock_data.get('technical_indicators', {})
        logging.info(f"Technical data for {symbol}:")
        logging.info(f"  Price: ${stock_data.get('current_price', 0):.2f}")
        logging.info(f"  RSI: {technical_data.get('rsi', 'N/A')}")
        logging.info(f"  VWAP: ${technical_data.get('vwap', 'N/A')}")
        
        # Check for open positions
        try:
            open_positions = self.performance_tracker.get_open_positions()
            if not open_positions.empty and symbol in open_positions['symbol'].values:
                position = open_positions[open_positions['symbol'] == symbol].iloc[0]
                
                position_data = {
                    'entry_price': position['entry_price'],
                    'current_price': stock_data['current_price'],
                    'target_price': position['target_price'],
                    'stop_price': position['stop_price'],
                    'size': position['position_size']
                }
                
                await self.trading_analyst.analyze_position(
                    stock_data=stock_data,
                    position_data=position_data
                )
                return
        except Exception as e:
            self.logger.error(f"Error checking positions for {symbol}: {str(e)}")
            return

        # Only analyze for new setups during regular market hours unless in testing mode
        market_phase = self.market_monitor.get_market_phase()
        if market_phase != 'regular' and not self.config_manager.get('market.testing_mode.enabled', False):
            return

        trading_setup = await self.trading_analyst.analyze_setup(stock_data)
        
        if trading_setup and 'NO SETUP' not in trading_setup:
            self.metrics['setups_detected'] += 1
            setup_details = self._parse_trading_setup(trading_setup)
            
            if setup_details and 'symbol' in setup_details:
                try:
                    trade_data = {
                        'symbol': setup_details['symbol'],
                        'entry_price': setup_details.get('entry', setup_details.get('entry_price')),
                        'target_price': setup_details.get('target', setup_details.get('target_price')),
                        'stop_price': setup_details.get('stop', setup_details.get('stop_price')),
                        'size': setup_details.get('size', 100),
                        'confidence': setup_details.get('confidence'),
                        'reason': setup_details.get('reason', ''),
                        'type': 'PAPER',
                        'status': 'OPEN',
                        'notes': 'Auto-generated by AI analysis'
                    }
                    
                    if self.performance_tracker.log_trade(trade_data):
                        self.metrics['trades_executed'] += 1
                        await self._execute_trade(symbol, setup_details)
                except Exception as e:
                    self.logger.error(f"Error executing trade for {symbol}: {str(e)}")
                    
    except Exception as e:
        self.logger.error(f"Symbol analysis error: {str(e)}")
