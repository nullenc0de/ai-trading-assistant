# AI Trading Assistant

An intelligent trading system that combines technical analysis, machine learning, and risk management to identify and execute trading opportunities in the stock market.

## Overview

AI Trading Assistant is a sophisticated trading platform that utilizes artificial intelligence to analyze market data, identify potential trading setups, and manage positions with strict risk management rules. The system is designed to operate in paper trading mode or live trading through either Alpaca or Robinhood integration.

### Key Features

- Real-time market data analysis
- AI-powered trading setup detection
- Automated position management
- Comprehensive risk management
- Performance tracking and analysis
- Pre-market and post-market analysis
- Paper trading support
- Multi-broker support (Alpaca and Robinhood)

## Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager
- Git

### Dependencies

- pandas
- numpy
- yfinance
- ollama
- colorama
- tabulate
- pytz
- cryptography
- alpaca-py

### Step-by-Step Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ai-trading-assistant.git
cd ai-trading-assistant
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

## Usage

### Starting the System

```bash
python main.py
```

### Configuration

The system can be configured through several JSON files:

- `config.json`: Main system configuration
- `market_calendar.json`: Market hours and holidays
- `alpaca_config.json`: Alpaca API credentials (if using Alpaca)
- `robinhood_config.json`: Robinhood credentials (if using Robinhood)

### Operation Modes

1. **Paper Trading Mode**
   - Default mode for testing strategies
   - No real money involved
   - Full functionality for analysis and tracking

2. **Live Trading Mode - Alpaca**
   - Real money trading through Alpaca
   - Requires API key and secret
   - Supports both paper and live Alpaca accounts
   - Enhanced risk management controls

3. **Live Trading Mode - Robinhood** - Not fully vetted
   - Real money trading through Robinhood
   - Requires API credentials
   - Enhanced risk management controls

### Broker Setup

#### Alpaca Configuration
1. Create an account at https://alpaca.markets/
2. Obtain API credentials from your dashboard
3. Configure using one of these methods:
   - Environment variables:
     ```bash
     export ALPACA_API_KEY_ID='your_key'
     export ALPACA_API_SECRET_KEY='your_secret'
     ```
   - Interactive setup through the application
   - Manual configuration in alpaca_config.json

#### Robinhood Configuration
- Configure through interactive setup when running the application
- Requires 2FA verification if enabled

### Monitoring and Logging

- All activities are logged in `logs/trading_system.log`
- Debug information in `logs/trading_system_debug.log`
- Performance metrics stored in `logs/performance/`

## System Architecture

### Components

1. **Market Monitor**
   - Tracks market hours and conditions
   - Manages trading sessions

2. **Stock Scanner**
   - Identifies potential trading candidates
   - Filters based on volume and price criteria

3. **Stock Analyzer**
   - Performs technical analysis
   - Calculates key indicators

4. **Trading Analyst**
   - AI-powered setup detection
   - Position analysis and management

5. **Broker Manager**
   - Manages broker connections (Alpaca/Robinhood)
   - Executes trading decisions
   - Manages stop losses and exits

6. **Performance Tracker**
   - Records all trading activity
   - Generates performance metrics

[Rest of README remains unchanged with Contributing, Commercial Use, Disclaimer, etc. sections]
