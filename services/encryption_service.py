from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


class EncryptionService:
    """Service for encrypting/decrypting sensitive data like addresses and phone numbers."""
    
    _instance = None
    
    def __init__(self, key=None):
        """Initialize with encryption key."""
        if key is None:
            key = current_app.config.get('ENCRYPTION_KEY')
        
        if not key:
            raise ValueError("ENCRYPTION_KEY not configured")
        
        # Handle both string and bytes
        if isinstance(key, str):
            key = key.encode()
        
        self.cipher = Fernet(key)
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance for the current app context."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def encrypt(self, plaintext):
        """Encrypt plaintext string, returns base64-encoded ciphertext."""
        if not plaintext:
            return None
        
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')
        
        return self.cipher.encrypt(plaintext).decode('utf-8')
    
    def decrypt(self, ciphertext):
        """Decrypt ciphertext, returns plaintext string."""
        if not ciphertext:
            return None
        
        if ciphertext == '[PURGED]':
            return None
        
        try:
            if isinstance(ciphertext, str):
                ciphertext = ciphertext.encode('utf-8')
            
            return self.cipher.decrypt(ciphertext).decode('utf-8')
        except InvalidToken:
            # Log this - could indicate tampering or key rotation issue
            current_app.logger.error("Failed to decrypt data - invalid token")
            return None
    
    @staticmethod
    def generate_key():
        """Generate a new Fernet key (for setup)."""
        return Fernet.generate_key().decode('utf-8')


def get_encryption_service():
    """Helper function to get encryption service instance."""
    return EncryptionService.get_instance()
