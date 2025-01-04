# AI-Powered Stock Trading Assistant

## 🚀 Overview

### Project Description
This is an advanced, AI-driven stock trading system designed to provide intelligent, data-driven trading insights using machine learning, technical analysis, and comprehensive market monitoring.

### Key Features
- 📊 Advanced Stock Scanning
- 🤖 AI-Powered Trading Setup Generation
- 📈 Technical Indicator Analysis
- 🔐 Secure Robinhood Integration
- 📝 Detailed Performance Tracking
- ⏰ Market Hours Intelligence
- 🛡️ Configurable Risk Management

## 🖥️ System Requirements

### Minimum Hardware Requirements
- Processor: Intel Core i5 or equivalent
- RAM: 8GB 
- Storage: 10GB free disk space
- Internet Connection: Stable broadband

### Recommended Hardware
- Processor: Intel Core i7 or AMD Ryzen 7
- RAM: 16GB
- GPU: CUDA-enabled (for faster ML inference)
- SSD Storage
- High-speed internet connection

### Software Prerequisites
- Python 3.9+
- pip (Python package manager)
- Ollama (Local Language Model)
- Operating Systems: 
  * Windows 10/11
  * macOS 10.15+
  * Linux (Ubuntu 20.04+ recommended)

## 🔧 Installation Guide

### 1. Prepare Your Environment

#### Windows
```powershell
# Open PowerShell as Administrator
# Enable Python virtual environments
Set-ExecutionPolicy RemoteSigned

# Create project directory
mkdir ai-trading-assistant
cd ai-trading-assistant

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate
```

#### macOS/Linux
```bash
# Create project directory
mkdir ai-trading-assistant
cd ai-trading-assistant

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install core dependencies
pip install -r components/requirements.txt

# Optional: Install development tools
pip install -r components/requirements.txt
```

### 3. Install Ollama
- Visit https://ollama.ai/
- Download and install Ollama for your operating system
- Pull Llama3 model:
```bash
ollama pull llama3
```

## 🔐 Robinhood Integration

### Authentication Process
1. First-time setup will prompt for Robinhood credentials
2. Credentials are encrypted using Fernet symmetric encryption
3. Stored securely with restricted file permissions

### Credential Management Commands
```python
# Interactive Credential Management
python -m components.robinhood_authenticator

# Options:
# 1. Save Credentials
# 2. Load Credentials
# 3. Remove Credentials
```

## 🚀 Running the Trading System

### Basic Execution
```bash
# Activate virtual environment first
python main.py
```

### Command-Line Options
```bash
# Future planned options
python main.py --config custom_config.json
python main.py --paper-trade
python main.py --backtest
```

## 📊 Configuration

### `config.json` Parameters
```json
{
    "trading_filters": {
        "min_price": 2.00,      // Minimum stock price
        "max_price": 20.00,     // Maximum stock price
        "min_volume": 500000,   // Minimum trading volume
        "min_relative_volume": 5.0  // Minimum relative volume
    },
    "system_settings": {
        "scan_interval": 60,    // Scan frequency (seconds)
        "max_symbols_to_analyze": 100  // Max symbols per scan
    },
    "risk_management": {
        "max_position_size": 1000,  // Max shares per trade
        "risk_per_trade": 0.02      // Maximum risk percentage
    }
}
```

## 📈 Performance Tracking

### Logging Details
- Stored in `performance_logs/trades.csv`
- Tracks:
  * Timestamp
  * Symbol
  * Entry Price
  * Confidence Level
  * Trading Setup Details

### Performance Report Metrics
- Total Trades
- Confidence Level Statistics
- Symbol Performance
- Potential Profit/Loss Analysis

## 🛡️ Risk Management

### Key Risk Mitigation Strategies
- Configurable position sizing
- Confidence-based trade selection
- Technical indicator analysis
- AI-powered setup validation

## 🔍 Technical Analysis Indicators

### Calculated Indicators
1. RSI (Relative Strength Index)
   - Momentum oscillator
   - Measures speed of price changes

2. VWAP (Volume Weighted Average Price)
   - Institutional trading reference
   - Shows average price weighted by volume

3. Moving Averages
   - SMA (Simple Moving Average)
   - EMA (Exponential Moving Average)

4. ATR (Average True Range)
   - Volatility indicator
   - Helps determine stop-loss levels

## 🤖 AI Trading Setup Generation

### Machine Learning Process
1. Collect stock data
2. Calculate technical indicators
3. Generate comprehensive prompt
4. Use Llama3 to analyze setup
5. Validate and format response

## 📋 Logging and Monitoring

### System Logs
- Location: `logs/trading_system.log`
- Captures:
  * System events
  * Errors
  * Trading decisions
  * Performance metrics

## ⚠️ Important Disclaimers

### Legal and Financial Warning
- THIS IS AN EXPERIMENTAL TRADING SYSTEM
- NO GUARANTEED PROFITS
- HIGH FINANCIAL RISK
- SIMULATED TRADING RECOMMENDED
- CONSULT FINANCIAL PROFESSIONALS

## 🔬 Troubleshooting

### Common Issues
1. Ollama not running
   - Ensure Ollama is installed and Llama3 is pulled
   - Check Ollama service status

2. Dependency Errors
   - Verify Python version
   - Recreate virtual environment
   - Reinstall dependencies

3. Market Data Issues
   - Check internet connectivity
   - Verify stock data source availability

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create feature branch
3. Implement changes
4. Write tests
5. Submit pull request

### Code Style
- Follow PEP 8 guidelines
- Use type hints
- Write comprehensive docstrings
- 100% test coverage for new features

## 📄 Licensing

### MIT License
- Commercial use allowed
- Modifications permitted
- Private and commercial use
- No liability
- Must include original license

## 📞 Support

### Community Support
- GitHub Issues
- Discussion Forums
- Email Support

### Professional Support
- Consulting available
- Custom feature development
- Enterprise integration

## 🔮 Future Roadmap

### Planned Features
- Multiple broker integrations
- Advanced machine learning models
- Real-time news sentiment analysis
- Backtesting framework
- Mobile app
- Cloud deployment options

## 🙏 Acknowledgments
- Ollama Team
- Robinhood
- Open-source community contributors

---

**Remember**: Investing involves risk. Always do your own research and never invest more than you can afford to lose.
