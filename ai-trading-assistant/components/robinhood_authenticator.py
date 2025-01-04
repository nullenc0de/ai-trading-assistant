# components/robinhood_authenticator.py
import os
import json
import getpass
import logging
from cryptography.fernet import Fernet
from typing import Optional, Dict

class RobinhoodAuthenticator:
    def __init__(self, config_path='robinhood_config.json'):
        """
        Initialize Robinhood Authentication Manager
        
        Args:
            config_path (str): Path to store encrypted credentials
        """
        self.config_path = config_path
        self.encryption_key_path = 'robinhood_key.key'
        
        # Ensure secure file permissions
        self._set_secure_file_permissions()

    def _set_secure_file_permissions(self):
        """
        Set secure file permissions for credential storage
        """
        try:
            # Unix/Linux file permission setting
            if os.name != 'nt':
                os.chmod(self.config_path, 0o600)  # Read/write for owner only
                os.chmod(self.encryption_key_path, 0o600)
        except Exception as e:
            logging.warning(f"Could not set secure file permissions: {e}")

    def _generate_key(self) -> bytes:
        """
        Generate a new encryption key
        
        Returns:
            bytes: Encryption key
        """
        key = Fernet.generate_key()
        with open(self.encryption_key_path, 'wb') as key_file:
            key_file.write(key)
        return key

    def _load_key(self) -> bytes:
        """
        Load existing encryption key or generate a new one
        
        Returns:
            bytes: Encryption key
        """
        try:
            with open(self.encryption_key_path, 'rb') as key_file:
                return key_file.read()
        except FileNotFoundError:
            return self._generate_key()

    def encrypt_credentials(self, credentials: Dict[str, str]) -> Dict[str, str]:
        """
        Encrypt Robinhood credentials
        
        Args:
            credentials (dict): User credentials
        
        Returns:
            dict: Encrypted credentials
        """
        key = self._load_key()
        f = Fernet(key)
        
        encrypted_credentials = {}
        for k, v in credentials.items():
            encrypted_credentials[k] = f.encrypt(v.encode()).decode()
        
        return encrypted_credentials

    def decrypt_credentials(self, encrypted_credentials: Dict[str, str]) -> Dict[str, str]:
        """
        Decrypt Robinhood credentials
        
        Args:
            encrypted_credentials (dict): Encrypted credentials
        
        Returns:
            dict: Decrypted credentials
        """
        key = self._load_key()
        f = Fernet(key)
        
        decrypted_credentials = {}
        for k, v in encrypted_credentials.items():
            decrypted_credentials[k] = f.decrypt(v.encode()).decode()
        
        return decrypted_credentials

    def save_credentials(self, credentials: Optional[Dict[str, str]] = None) -> bool:
        """
        Save Robinhood credentials securely
        
        Args:
            credentials (dict, optional): User credentials
        
        Returns:
            bool: True if credentials saved successfully
        """
        try:
            # If no credentials provided, prompt user
            if credentials is None:
                credentials = self._prompt_for_credentials()
            
            # Validate credentials
            if not self._validate_credentials(credentials):
                print("Invalid credentials. Please try again.")
                return False
            
            # Encrypt credentials
            encrypted_credentials = self.encrypt_credentials(credentials)
            
            # Save encrypted credentials
            with open(self.config_path, 'w') as config_file:
                json.dump(encrypted_credentials, config_file)
            
            print("Credentials saved securely.")
            return True
        
        except Exception as e:
            logging.error(f"Error saving credentials: {e}")
            return False

    def _prompt_for_credentials(self) -> Dict[str, str]:
        """
        Interactively prompt for Robinhood credentials
        
        Returns:
            dict: User-provided credentials
        """
        print("Enter your Robinhood credentials (these will be encrypted)")
        credentials = {
            'username': input("Robinhood Username: "),
            'password': getpass.getpass("Robinhood Password: "),
            # Optional: MFA token or additional authentication
            'mfa_token': getpass.getpass("MFA Token (optional): ") or None
        }
        return credentials

    def _validate_credentials(self, credentials: Dict[str, str]) -> bool:
        """
        Basic credential validation
        
        Args:
            credentials (dict): Credentials to validate
        
        Returns:
            bool: True if credentials appear valid
        """
        # Basic validation checks
        return all([
            credentials.get('username'),
            credentials.get('password')
        ])

    def load_credentials(self) -> Optional[Dict[str, str]]:
        """
        Load and decrypt saved credentials
        
        Returns:
            dict or None: Decrypted credentials or None if not found
        """
        try:
            with open(self.config_path, 'r') as config_file:
                encrypted_credentials = json.load(config_file)
            
            return self.decrypt_credentials(encrypted_credentials)
        
        except FileNotFoundError:
            print("No saved credentials found.")
            return None
        except Exception as e:
            logging.error(f"Error loading credentials: {e}")
            return None

    def remove_credentials(self) -> bool:
        """
        Securely remove saved credentials
        
        Returns:
            bool: True if credentials removed successfully
        """
        try:
            # Remove config file
            if os.path.exists(self.config_path):
                os.remove(self.config_path)
            
            # Remove encryption key
            if os.path.exists(self.encryption_key_path):
                os.remove(self.encryption_key_path)
            
            print("Credentials removed securely.")
            return True
        
        except Exception as e:
            logging.error(f"Error removing credentials: {e}")
            return False

# Example usage guidance
def main():
    auth = RobinhoodAuthenticator()
    
    while True:
        print("\nRobinhood Credential Management")
        print("1. Save Credentials")
        print("2. Load Credentials")
        print("3. Remove Credentials")
        print("4. Exit")
        
        choice = input("Enter your choice (1-4): ")
        
        if choice == '1':
            auth.save_credentials()
        elif choice == '2':
            credentials = auth.load_credentials()
            if credentials:
                print("Credentials loaded successfully.")
        elif choice == '3':
            auth.remove_credentials()
        elif choice == '4':
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == '__main__':
    main()