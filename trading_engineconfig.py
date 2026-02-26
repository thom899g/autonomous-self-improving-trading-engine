"""
Configuration management for the trading engine.
Uses Firebase as the primary state store with fallback to local cache.
"""
import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, db

# Load environment variables
load_dotenv()

@dataclass
class ExchangeConfig:
    """Configuration for cryptocurrency exchange connections"""
    name: str = "binance"
    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    rate_limit: int = 1200  # requests per minute
    timeout: int = 30000  # milliseconds
    
    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.getenv(f"{self.name.upper()}_API_KEY", "")
        if not self.api_secret:
            self.api_secret = os.getenv(f"{self.name.upper()}_API_SECRET", "")

@dataclass
class FirebaseConfig:
    """Firebase configuration with fallback handling"""
    project_id: str = field(default_factory=lambda: os.getenv("FIREBASE_PROJECT_ID", ""))
    credentials_path: str = field(default_factory=lambda: os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""))
    database_url: str = field(default_factory=lambda: os.getenv("FIREBASE_DATABASE_URL", ""))
    
    def __post_init__(self):
        if not self.project_id:
            raise ValueError("Firebase project ID must be provided via FIREBASE_PROJECT_ID env var")
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            logging.warning("Firebase credentials not found. Running in local-only mode.")

@dataclass
class TradingConfig:
    """Core trading engine configuration"""
    initial_capital: float = 10000.0
    max_position_size: float = 0.1  # 10% of capital per trade
    max_daily_loss: float = 0.02  # 2% daily loss limit
    symbols: list = field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])
    timeframe: str = "1h"
    backtest_days: int = 30
    live_trading: bool = False
    
    def validate(self) -> bool:
        """Validate configuration values"""
        if self.initial_capital <= 0:
            raise ValueError("Initial capital must be positive")
        if not 0 < self.max_position_size <= 1:
            raise ValueError("Max position size must be between 0 and 1")
        return True

class ConfigManager:
    """Manages configuration with Firebase sync and local cache"""
    
    def __init__(self, firebase_config: FirebaseConfig):
        self.firebase_config = firebase_config
        self.local_config: Dict[str, Any] = {}
        self.firestore_client: Optional[firestore.Client] = None
        self._init_firebase()
        
    def _init_firebase(self) -> None:
        """Initialize Firebase connection with error handling"""
        try:
            if self.firebase_config.credentials_path and os.path.exists