# components/robinhood_authenticator.py
import os
import json
import getpass
import logging
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from pathlib import Path

class RobinhoodAuthenticator:
    def __init__(self, config_path='robinhood_config.json'):
        """
        Initialize Robinhood Authentication Manager
        
        Args:
            config_path (str): Path to store encrypted credentials
        """
        self.config_path = config_path
        self.key_path = 'robinhood.key'
        
        # Initialize logging
        self.logger = logging.getLogger(__name__)
        
        # Initialize encryption
        self._init_encryption()
        
        # Ensure secure file permissions
        self._set_secure_permissions()

    def _init_encryption(self) -> None:
        """Initialize encryption key and cipher suite"""
        try:
            if not os.path.exists(self.key_path):
                # Generate new key
                key = Fernet.generate_key()
                with open(self.key_path, 'wb') as key_file:
                    key_file.write(key)
                self.key = key
            else:
                # Load existing key
                with open(self.key_path, 'rb') as key_file:
                    self.key = key_file.read()
            
            # Initialize cipher suite
            self.cipher_suite = Fernet(self.key)
            
        except Exception as e:
            self.logger.error(f"Error initializing encryption: {str(e)}")
            self.key = None
            self.cipher_suite = None

    def _set_secure_permissions(self) -> None:
        """Set secure file permissions for credential and key files"""
        try:
            # Set permissions for key file
            if os.path.exists(self.key_path):
                os.chmod(self.key_path, 0o600)
            
            # Set permissions for config file
            if os.path.exists(self.config_path):
                os.chmod(self.config_path, 0o600)
                
        except Exception as e:
            self.logger.error(f"Error setting file permissions: {str(e)}")

    def encrypt_value(self, value: str) -> Optional[str]:
        """
        Encrypt a single value
        
        Args:
            value (str): Value to encrypt
            
        Returns:
            str: Encrypted value or None on failure
        """
        try:
            if not self.cipher_suite or value is None:
                return None
            return self.cipher_suite.encrypt(value.encode()).decode()
        except Exception as e:
            self.logger.error(f"Error encrypting value: {str(e)}")
            return None

    def decrypt_value(self, encrypted_value: str) -> Optional[str]:
        """
        Decrypt a single value
        
        Args:
            encrypted_value (str): Value to decrypt
            
        Returns:
            str: Decrypted value or None on failure
        """
        try:
            if not self.cipher_suite or encrypted_value is None:
                return None
            return self.cipher_suite.decrypt(encrypted_value.encode()).decode()
        except Exception as e:
            self.logger.error(f"Error decrypting value: {str(e)}")
            return None

    def encrypt_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Encrypt Robinhood credentials
        
        Args:
            credentials (dict): Credentials to encrypt
            
        Returns:
            dict: Encrypted credentials
        """
        encrypted_creds = {}
        try:
            for key, value in credentials.items():
                if isinstance(value, str):
                    encrypted_creds[key] = self.encrypt_value(value)
                else:
                    encrypted_creds[key] = value
            return encrypted_creds
        except Exception as e:
            self.logger.error(f"Error encrypting credentials: {str(e)}")
            return credentials

    def decrypt_credentials(self, encrypted_creds: Dict[str, Any]) -> Dict[str, Any]:
        """
        Decrypt Robinhood credentials
        
        Args:
            encrypted_creds (dict): Encrypted credentials
            
        Returns:
            dict: Decrypted credentials
        """
        decrypted_creds = {}
        try:
            for key, value in encrypted_creds.items():
                if isinstance(value, str):
                    decrypted_creds[key] = self.decrypt_value(value)
                else:
                    decrypted_creds[key] = value
            return decrypted_creds
        except Exception as e:
            self.logger.error(f"Error decrypting credentials: {str(e)}")
            return encrypted_creds

    def save_credentials(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save Robinhood credentials securely
        
        Args:
            credentials (dict, optional): Credentials to save
            
        Returns:
            bool: True if successful
        """
        try:
            # Get credentials if not provided
            if credentials is None:
                credentials = self._prompt_for_credentials()
            
            # Validate credentials
            if not self._validate_credentials(credentials):
                self.logger.error("Invalid credentials provided")
                return False
            
            # Create config structure
            config = {
                'credentials': self.encrypt_credentials(credentials),
                'settings': {
                    'max_retries': 3,
                    'timeout': 30,
                    'debug_mode': False
                }
            }
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path) if os.path.dirname(self.config_path) else '.', 
                       exist_ok=True)
            
            # Save config
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            # Set secure permissions
            self._set_secure_permissions()
            
            self.logger.info("Credentials saved successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving credentials: {str(e)}")
            return False

    def load_credentials(self) -> Optional[Dict[str, Any]]:
        """
        Load and decrypt saved credentials
        
        Returns:
            dict: Decrypted credentials or None if not found/error
        """
        try:
            if not os.path.exists(self.config_path):
                return None
            
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            encrypted_creds = config.get('credentials', {})
            if not encrypted_creds:
                return None
            
            decrypted_creds = self.decrypt_credentials(encrypted_creds)
            
            # Validate decrypted credentials
            if not self._validate_credentials(decrypted_creds):
                self.logger.warning("Loaded credentials are invalid")
                return None
                
            return decrypted_creds
            
        except Exception as e:
            self.logger.error(f"Error loading credentials: {str(e)}")
            return None

    def _prompt_for_credentials(self) -> Dict[str, str]:
        """
        Interactively prompt for Robinhood credentials
        
        Returns:
            dict: User-provided credentials
        """
        print("\nEnter your Robinhood credentials (these will be encrypted)")
        credentials = {
            'username': input("Robinhood Username: ").strip(),
            'password': getpass.getpass("Robinhood Password: ").strip(),
            'mfa_token': getpass.getpass("MFA Token (optional, press Enter to skip): ").strip() or None,
            'device_token': None  # Will be set during authentication
        }
        return credentials

    def _validate_credentials(self, credentials: Dict[str, Any]) -> bool:
        """
        Validate credential format
        
        Args:
            credentials (dict): Credentials to validate
            
        Returns:
            bool: True if valid
        """
        # Check for required fields
        required_fields = ['username', 'password']
        if not all(field in credentials for field in required_fields):
            return False
            
        # Check for non-empty required values
        if not all(credentials.get(field) for field in required_fields):
            return False
            
        return True

    def remove_credentials(self) -> bool:
        """
        Securely remove saved credentials and encryption key
        
        Returns:
            bool: True if successful
        """
        try:
            # Remove config file
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
                
            # Remove encryption key
            if os.path.exists(self.key_path):
                os.remove(self.key_path)
                
            self.logger.info("Credentials and encryption key removed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error removing credentials: {str(e)}")
            return False

    def update_settings(self, settings: Dict[str, Any]) -> bool:
        """
        Update authentication settings
        
        Args:
            settings (dict): New settings
            
        Returns:
            bool: True if successful
        """
        try:
            if not os.path.exists(self.config_path):
                return False
                
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                
            config['settings'].update(settings)
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
                
            self._set_secure_permissions()
            
            self.logger.info("Settings updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating settings: {str(e)}")
            return False

    def get_settings(self) -> Dict[str, Any]:
        """
        Get current authentication settings
        
        Returns:
            dict: Current settings
        """
        try:
            if not os.path.exists(self.config_path):
                return {}
                
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                
            return config.get('settings', {})
            
        except Exception as e:
            self.logger.error(f"Error getting settings: {str(e)}")
            return {}
