from django.apps import AppConfig


class TriageConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'triage'

    def ready(self):
        """Initialize the LiteLLM Router on startup."""
        try:
            from utils.llm_router import get_llm_router
            get_llm_router()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Critical: Failed to initialize LiteLLM Router: {e}")
