# components/output_formatter.py
import colorama
from tabulate import tabulate

class OutputFormatter:
    def __init__(self):
        """
        Initialize Output Formatter with color support
        """
        colorama.init(autoreset=True)

    def format_trading_setup(self, setup):
        """
        Format trading setup with color and tabulation
        
        Args:
            setup (str): Raw trading setup string
        
        Returns:
            str: Formatted trading setup
        """
        try:
            # Parse setup lines
            lines = setup.split("\n")
            
            # Extract key information
            symbol = lines[0].split(": ")[1]
            entry_price = lines[1].split(": ")[1]
            target_price = lines[2].split(": ")[1]
            stop_price = lines[3].split(": ")[1]
            position_size = lines[4].split(": ")[1]
            reason = lines[5].split(": ")[1]
            confidence = lines[6].split(": ")[1]
            risk_reward = lines[7].split(": ")[1]
            
            # Prepare table data
            table_data = [
                ["Symbol", symbol],
                ["Entry Price", f"{colorama.Fore.CYAN}{entry_price}{colorama.Fore.RESET}"],
                ["Target Price", f"{colorama.Fore.GREEN}{target_price}{colorama.Fore.RESET}"],
                ["Stop Loss", f"{colorama.Fore.RED}{stop_price}{colorama.Fore.RESET}"],
                ["Position Size", position_size],
                ["Confidence", f"{self._get_confidence_color(confidence)}{confidence}{colorama.Fore.RESET}"],
                ["Risk/Reward", risk_reward]
            ]
            
            # Create formatted output
            formatted_output = (
                f"\n{colorama.Fore.MAGENTA}🚀 TRADING SETUP DETECTED {colorama.Fore.RESET}\n"
                f"{tabulate(table_data, headers=['Detail', 'Value'], tablefmt='fancy_grid')}\n\n"
                f"{colorama.Fore.YELLOW}📝 Reason:{colorama.Fore.RESET} {reason}"
            )
            
            return formatted_output
        
        except Exception as e:
            # Fallback to simple formatting
            return f"Trading Setup (Error parsing): {setup}"

    def _get_confidence_color(self, confidence):
        """
        Get color based on confidence level
        
        Args:
            confidence (str): Confidence percentage
        
        Returns:
            str: Color code
        """
        try:
            conf_value = float(confidence.rstrip('%'))
            if conf_value > 80:
                return colorama.Fore.GREEN
            elif conf_value > 60:
                return colorama.Fore.YELLOW
            else:
                return colorama.Fore.RED
        except:
            return colorama.Fore.WHITE

    def print_system_message(self, message, message_type='info'):
        """
        Print system messages with appropriate coloring
        
        Args:
            message (str): Message to print
            message_type (str): Type of message (info, warning, error)
        """
        if message_type == 'info':
            print(f"{colorama.Fore.CYAN}ℹ️ {message}{colorama.Fore.RESET}")
        elif message_type == 'warning':
            print(f"{colorama.Fore.YELLOW}⚠️ {message}{colorama.Fore.RESET}")
        elif message_type == 'error':
            print(f"{colorama.Fore.RED}❌ {message}{colorama.Fore.RESET}")
        else:
            print(message)

    def print_trade_alert(self, symbol, action, details):
        """
        Print trade alerts with detailed formatting
        
        Args:
            symbol (str): Stock symbol
            action (str): Trade action (BUY/SELL)
            details (dict): Trade details
        """
        if action.upper() == 'BUY':
            color = colorama.Fore.GREEN
            icon = '📈'
        else:
            color = colorama.Fore.RED
            icon = '📉'
        
        print(
            f"{color}{icon} {action.upper()} ALERT: {symbol} {colorama.Fore.RESET}\n"
            f"Details: {details}"
        )