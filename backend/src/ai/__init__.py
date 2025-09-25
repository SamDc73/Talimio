"""AI module initialization and configuration."""

import litellm


# Configure LiteLLM at module initialization
litellm.enable_json_schema_validation = True
litellm.drop_params = True
litellm.suppress_debug_info = True  # Reduce verbose logging
