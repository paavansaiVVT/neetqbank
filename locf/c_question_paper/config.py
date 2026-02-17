"""
Configuration module for Question Paper Extraction with Retry Logic
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractionConfig:
    """
    Configuration for question paper extraction with retry logic.
    
    Attributes:
        max_retries: Maximum number of retry attempts for missing questions (default: 3)
        enable_validation: Whether to validate extraction completeness (default: True)
        enable_merge: Whether to merge results from multiple attempts (default: True)
        temperature: LLM temperature for extraction (default: 0 for deterministic)
        timeout_seconds: HTTP timeout for PDF download (default: 30)
        network_retries: Number of retries for network failures (default: 5)
        min_success_rate: Minimum success rate to consider extraction acceptable (default: 0.95)
    """
    max_retries: int = 3
    enable_validation: bool = True
    enable_merge: bool = True
    temperature: float = 0.0
    timeout_seconds: int = 30
    network_retries: int = 5
    min_success_rate: float = 0.95
    
    def validate(self) -> None:
        """Validate configuration values."""
        if self.max_retries < 1 or self.max_retries > 10:
            raise ValueError(f"max_retries must be between 1 and 10, got {self.max_retries}")
        
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature must be between 0.0 and 2.0, got {self.temperature}")
        
        if self.timeout_seconds < 10 or self.timeout_seconds > 300:
            raise ValueError(f"timeout_seconds must be between 10 and 300, got {self.timeout_seconds}")
        
        if not 0.0 < self.min_success_rate <= 1.0:
            raise ValueError(f"min_success_rate must be between 0.0 and 1.0, got {self.min_success_rate}")
    
    def get_acceptable_missing_count(self, total_questions: int) -> int:
        """
        Calculate the maximum acceptable number of missing questions.
        
        Args:
            total_questions: Total expected number of questions
            
        Returns:
            Maximum number of questions that can be missing while still being acceptable
        """
        return int(total_questions * (1 - self.min_success_rate))
    
    def is_extraction_acceptable(self, expected: int, actual: int) -> bool:
        """
        Check if extraction result is acceptable based on min_success_rate.
        
        Args:
            expected: Expected number of questions
            actual: Actual number of questions extracted
            
        Returns:
            True if the extraction meets the minimum success rate
        """
        if expected <= 0:
            return actual > 0
        
        success_rate = actual / expected
        return success_rate >= self.min_success_rate


# Default configuration
DEFAULT_CONFIG = ExtractionConfig()

# Strict configuration (higher standards)
STRICT_CONFIG = ExtractionConfig(
    max_retries=5,
    min_success_rate=1.0,  # Must extract ALL questions
    enable_validation=True,
    enable_merge=True
)

# Fast configuration (fewer retries, lower standards)
FAST_CONFIG = ExtractionConfig(
    max_retries=2,
    min_success_rate=0.90,  # Accept 90% success
    enable_validation=True,
    enable_merge=True
)

# Development configuration (verbose, forgiving)
DEV_CONFIG = ExtractionConfig(
    max_retries=3,
    min_success_rate=0.85,
    enable_validation=True,
    enable_merge=True,
    timeout_seconds=60
)


def get_config(profile: str = "default") -> ExtractionConfig:
    """
    Get a predefined configuration profile.
    
    Args:
        profile: Configuration profile name ("default", "strict", "fast", "dev")
        
    Returns:
        ExtractionConfig instance
        
    Raises:
        ValueError: If profile name is invalid
    """
    profiles = {
        "default": DEFAULT_CONFIG,
        "strict": STRICT_CONFIG,
        "fast": FAST_CONFIG,
        "dev": DEV_CONFIG
    }
    
    if profile not in profiles:
        raise ValueError(f"Unknown config profile: {profile}. Available: {list(profiles.keys())}")
    
    return profiles[profile]


# Usage examples:
"""
# Use default config
config = DEFAULT_CONFIG

# Use strict config
config = STRICT_CONFIG

# Use custom config
config = ExtractionConfig(
    max_retries=4,
    min_success_rate=0.98,
    temperature=0.1
)
config.validate()

# Get config by profile name
config = get_config("strict")

# Check if extraction is acceptable
if config.is_extraction_acceptable(expected=40, actual=38):
    print("Extraction acceptable!")
else:
    print("Too many missing questions!")

# Calculate acceptable missing count
max_missing = config.get_acceptable_missing_count(total_questions=40)
print(f"Can accept up to {max_missing} missing questions")
"""

