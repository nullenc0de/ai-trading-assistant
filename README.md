# AI Trading Assistant

An intelligent trading system that combines technical analysis, machine learning, and risk management to identify and execute trading opportunities in the stock market.

## Overview

AI Trading Assistant is a sophisticated trading platform that utilizes artificial intelligence to analyze market data, identify potential trading setups, and manage positions with strict risk management rules. The system is designed to operate in both paper trading and live trading modes through Robinhood integration.

### Key Features

- Real-time market data analysis
- AI-powered trading setup detection
- Automated position management
- Comprehensive risk management
- Performance tracking and analysis
- Pre-market and post-market analysis
- Paper trading support
- Robinhood integration (optional)

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

4. Configure the system:
```bash
cp config/config.json.example config/config.json
# Edit config.json with your preferred settings
```

## Usage

### Starting the System

```bash
python main.py
```

### Configuration

The system can be configured through several JSON files in the `config` directory:

- `config.json`: Main system configuration
- `money_management.json`: Risk and position sizing settings

### Operation Modes

1. **Paper Trading Mode**
   - Default mode for testing strategies
   - No real money involved
   - Full functionality for analysis and tracking

2. **Live Trading Mode (Requires Robinhood)**
   - Real money trading through Robinhood
   - Requires API credentials
   - Enhanced risk management controls

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

5. **Position Manager**
   - Executes trading decisions
   - Manages stop losses and exits

6. **Performance Tracker**
   - Records all trading activity
   - Generates performance metrics

## Contributing

We welcome contributions to improve the AI Trading Assistant. Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 style guide
- Add unit tests for new features
- Update documentation as needed
- Maintain type hints and docstrings

## License

This project is licensed under the Commercial License - see the [LICENSE](LICENSE) file for details.

### Commercial Use

This software is protected by copyright and cannot be used for commercial purposes without explicit permission.

### Permitted Use

- Personal use
- Educational purposes
- Non-commercial research

### Prohibited Use

- Commercial deployment
- Integration into commercial products
- Resale or redistribution

## Disclaimer

This software is for educational and research purposes only. It is not intended to provide financial advice. Trading stocks carries significant risks, and past performance is not indicative of future results. Users of this software assume all risks associated with its use.

## Support

For support, bug reports, or feature requests, please:

1. Check the [Issues](https://github.com/yourusername/ai-trading-assistant/issues) page
2. Create a new issue if needed
3. Join our community Discord [link]

## Acknowledgments

- Thanks to all contributors
- Special thanks to the open-source community
- Powered by [Ollama](https://github.com/ollama/ollama) for AI capabilities
