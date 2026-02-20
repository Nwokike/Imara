"""
LiteLLM Router Initialization for Project Imara.
Provides a centralized, resilient entry point for all LLM calls with 
multi-layer fallback logic and automatic rate-limit handling.
"""
import os
import yaml
import logging
from pathlib import Path
from litellm import Router

logger = logging.getLogger(__name__)

_router_instance = None

def get_llm_router():
    """
    Returns the global LiteLLM Router instance (Singleton).
    Initializes from litellm_config.yaml on first call.
    """
    global _router_instance
    if _router_instance is None:
        config_path = Path(__file__).resolve().parent.parent / 'litellm_config.yaml'
        
        if not config_path.exists():
            logger.error(f"LiteLLM config not found at {config_path}")
            raise FileNotFoundError(f"Missing litellm_config.yaml at {config_path}")

        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)

            model_list = config.get('model_list', [])
            router_settings = config.get('router_settings', {})

            # Enable Semantic Disk Caching (2026 Best Practice)
            # Saves tokens and RAM by persisting results locally
            import litellm
            cache_dir = Path(os.environ.get('TEMP', '/tmp')) / 'litellm_cache'
            cache_dir.mkdir(parents=True, exist_ok=True)
            
            litellm.cache = litellm.Cache(
                type="disk", 
                disk_cache_dir=str(cache_dir)
            )
            
            # Initialize Router
            _router_instance = Router(
                model_list=model_list,
                **router_settings
            )
            logger.info(f"LiteLLM Router initialized with Disk Cache at {cache_dir}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LiteLLM Router: {e}")
            raise e

    return _router_instance
