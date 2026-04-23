"""Configuration management using Pydantic Settings"""

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings loaded from environment variables and config files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Qdrant settings
    qdrant_url: str = Field(default="", description="Qdrant cluster URL")
    qdrant_api_key: str = Field(default="", description="Qdrant API key")

    # HuggingFace settings
    hf_token: Optional[str] = Field(default=None, description="HuggingFace token")

    # Model settings
    base_model: str = Field(
        default="distilbert/distilbert-base-uncased",
        description="Base model for sparse encoder",
    )
    architecture: Literal["splade", "inference_free_splade"] = Field(
        default="inference_free_splade",
        description="Sparse encoder architecture",
    )
    pooling_strategy: Literal["max", "sum"] = Field(
        default="max",
        description="SPLADE pooling strategy",
    )

    # Training settings
    batch_size: int = Field(default=32, description="Training batch size")
    learning_rate: float = Field(default=2e-5, description="Learning rate")
    num_epochs: int = Field(default=3, description="Number of training epochs")
    warmup_ratio: float = Field(default=0.1, description="Warmup ratio")

    # Sparse regularization
    query_regularizer_weight: float = Field(
        default=5e-5,
        description="L1 regularization weight for query embeddings (higher = sparser)",
    )
    document_regularizer_weight: float = Field(
        default=3e-5,
        description="L1 regularization weight for document embeddings",
    )

    # ANCE settings
    ance_iterations: int = Field(default=3, description="Number of ANCE iterations")
    mining_top_k: int = Field(default=20, description="Top-K for hard negative mining")
    epochs_per_ance_iteration: int = Field(default=1, description="Epochs per ANCE iteration")

    # Checkpointing
    save_steps: int = Field(default=1000, description="Save checkpoint every N steps")
    save_total_limit: int = Field(default=3, description="Keep last N checkpoints")
    logging_steps: int = Field(default=100, description="Log every N steps")

    # Paths
    output_dir: Path = Field(default=Path("./outputs"), description="Output directory")
    checkpoint_dir: Path = Field(default=Path("./checkpoints"), description="Checkpoint directory")
    cache_dir: Path = Field(default=Path("./cache"), description="Cache directory")


class TrainingConfig:
    """Training configuration loaded from YAML file."""

    def __init__(
        self,
        run_name: str = "baseline",
        base_model: str = "distilbert/distilbert-base-uncased",
        architecture: str = "inference_free_splade",
        batch_size: int = 32,
        learning_rate: float = 2e-5,
        num_epochs: int = 3,
        query_regularizer_weight: float = 5e-5,
        document_regularizer_weight: float = 3e-5,
        ance_iterations: int = 3,
        mining_top_k: int = 20,
        **kwargs,
    ):
        self.run_name = run_name
        self.base_model = base_model
        self.architecture = architecture
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.num_epochs = num_epochs
        self.query_regularizer_weight = query_regularizer_weight
        self.document_regularizer_weight = document_regularizer_weight
        self.ance_iterations = ance_iterations
        self.mining_top_k = mining_top_k
        # Store any extra kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TrainingConfig":
        """Load config from YAML file."""
        with open(path) as f:
            config_dict = yaml.safe_load(f)
        return cls(**config_dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "run_name": self.run_name,
            "base_model": self.base_model,
            "architecture": self.architecture,
            "batch_size": self.batch_size,
            "learning_rate": self.learning_rate,
            "num_epochs": self.num_epochs,
            "query_regularizer_weight": self.query_regularizer_weight,
            "document_regularizer_weight": self.document_regularizer_weight,
            "ance_iterations": self.ance_iterations,
            "mining_top_k": self.mining_top_k,
        }


# Global settings instance
settings = Settings()


# ESCI label relevance scores
ESCI_SCORES = {
    "E": 1.0,  # Exact match
    "Exact": 1.0,
    "S": 0.7,  # Substitute
    "Substitute": 0.7,
    "C": 0.5,  # Complement
    "Complement": 0.5,
    "I": 0.0,  # Irrelevant
    "Irrelevant": 0.0,
}

# Labels considered as positive for training
POSITIVE_LABELS = {"E", "Exact", "S", "Substitute"}

# Labels considered as relevant for evaluation (used in recall)
RELEVANT_LABELS = {"E", "Exact", "S", "Substitute"}

# WANDS label relevance scores (numeric grades)
# 2 = Exact, 1 = Partial, 0 = Irrelevant
WANDS_SCORES = {
    2: 1.0,  # Exact match
    1: 0.5,  # Partial match
    0: 0.0,  # Irrelevant
}

# WANDS labels considered as relevant for evaluation
WANDS_RELEVANT_LABELS = {2, 1}  # Exact and Partial
