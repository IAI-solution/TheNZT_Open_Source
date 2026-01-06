class FastAgentConfig:
    MODEL = "openai/minimax-m2:cloud"
    ALT_MODEL = "openai/gpt-oss:20b-cloud"
    TEMPERATURE = 0.15
    ALT_TEMPERATURE = 0.4
    MAX_TOKENS = 6000
    ALT_MAX_TOKENS = 6000


class IntentDetectionConfig:
    MODEL = "openai/gpt-oss:20b-cloud"
    ALT_MODEL = "openai/gpt-oss:120b"
    TEMPERATURE = 0.3
    ALT_TEMPERATURE = 0.4
    MAX_TOKENS = None
    ALT_MAX_TOKENS = None


class PlannerConfig:
    MODEL = "openai/kimi-k2:1t"
    ALT_MODEL = "openai/gpt-oss:20b-cloud"
    TEMPERATURE = 0.0
    ALT_TEMPERATURE = 0.0
    MAX_TOKENS = None
    ALT_MAX_TOKENS = None


class ExecutorConfig:
    # Gemini primary, Groq 32k as ALT for very long execution contexts
    # MODEL = "groq/openai/gpt-oss-120b" # "gemini/gemini-2.5-flash"
    MODEL = "openai/kimi-k2:1t"
    ALT_MODEL = "openai/gpt-oss:20b-cloud"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 25000


class ManagerConfig:
    MODEL = "openai/kimi-k2:1t"
    ALT_MODEL = "openai/gpt-oss:20b-cloud"
    TEMPERATURE = 0.6
    ALT_TEMPERATURE = 0.6
    ALT_TOP_P = 0.95
    ALT_TOP_K = 25
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class WebSearchConfig:
    MODEL = "openai/gpt-oss:20b-cloud"
    ALT_MODEL = "openai/gpt-oss:120b"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class FinanceDataConfig:
    MODEL = "openai/gpt-oss:20b-cloud"
    ALT_MODEL = "openai/gpt-oss:120b"
    TEMPERATURE = 0.0
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class ReportGenerationConfig:
    # MODEL = "gemini/gemini-2.5-pro"
    MODEL="openai/deepseek-v3.2:cloud"
    ALT_MODEL="openai/gpt-oss:20b-cloud"
    # ALT_MODEL = "groq/llama-3.3-70b-versatile"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.2
    MAX_TOKENS = 20000
    ALT_MAX_TOKENS = 25000


class TaskValidationConfig:
    # MODEL = "gemini/gemini-2.0-flash-lite"
    MODEL = "openai/kimi-k2:1t"
    ALT_MODEL = "openai/gpt-oss:20b-cloud"
    TEMPERATURE = 0.7
    ALT_TEMPERATURE = 0.7
    MAX_TOKENS = 1000
    ALT_MAX_TOKENS = 1000


class ValidationConfig:
    MODEL = "openai/kimi-k2:1t"
    ALT_MODEL = "openai/gpt-oss:20b-cloud"
    TEMPERATURE = 0.6
    ALT_TEMPERATURE = 0.6
    MAX_TOKENS = 2000
    ALT_MAX_TOKENS = 2000


class SummarizerConfig:
    MODEL = "openai/kimi-k2:1t"
    ALT_MODEL = "openai/gpt-oss:20b-cloud"
    TEMPERATURE = 0.3
    STREAM = True
    ALT_TEMPERATURE = 0.25


class CountUsageMetricsPricingConfig:
    MODEL = "openai/gpt-oss:20b-cloud"
    ALT_MODEL = "openai/gpt-oss:120b"


class GetRelatedQueriesConfig:
    MODEL = "openai/minimax-m2:cloud"
    ALT_MODEL = "openai/gpt-oss:20b-cloud"
    TEMPERATURE = 0.2
    ALT_TEMPERATURE = 0.4
    MAX_TOKENS = 800
    ALT_MAX_TOKENS = 800


class GenerateSessionTitleConfig:
    # MODEL = "gemini/gemini-2.0-flash-lite"
    # MODEL = "groq/llama-3.3-70b-versatile"
    MODEL = "openai/gpt-oss:20b-cloud"
    ALT_MODEL = "openai/gpt-oss:120b"
    TEMPERATURE = 0.4
    ALT_TEMPERATURE = 0.4
    MAX_TOKENS = 128
    ALT_MAX_TOKENS = 128


class StockPredictionConfig:
    # prefer Groq Qwen/Mixtral as ALT for long financial sequences; Gemini primary for deterministic behavior
    MODEL = "openai/kimi-k2:1t"
    ALT_MODEL = "openai/gpt-oss:20b-cloud"
    TEMPERATURE = 0.0
    ALT_TEMPERATURE = 0.0
    MAX_TOKENS = 1500
    ALT_MAX_TOKENS = 1500


class GraphGenerationConfig:
    # MODEL = "gemini/gemini-2.5-flash"
    MODEL = "openai/gpt-oss:20b-cloud"
    ALT_MODEL = "openai/gpt-oss:120b"
    # ALT_MODEL = "groq/llama-3.3-70b-versatile"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.2
    MAX_TOKENS = 2000
    ALT_MAX_TOKENS = 2000

# class FastAgentConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.5-flash"
#     TEMPERATURE = 0.15
#     ALT_TEMPERATURE = 0.4
#     MAX_TOKENS = 6000
#     ALT_MAX_TOKENS = 6000


# class IntentDetectionConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.3
#     ALT_TEMPERATURE = 0.4
#     MAX_TOKENS = None
#     ALT_MAX_TOKENS = None


# class PlannerConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.5-flash"
#     TEMPERATURE = 0.0
#     ALT_TEMPERATURE = 0.0
#     MAX_TOKENS = None
#     ALT_MAX_TOKENS = None


# class ExecutorConfig:
#     # Gemini primary, Groq 32k as ALT for very long execution contexts
#     # MODEL = "groq/openai/gpt-oss-120b" # "gemini/gemini-2.5-flash"
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 25000


# class ManagerConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.5-flash"
#     TEMPERATURE = 0.6
#     ALT_TEMPERATURE = 0.6
#     ALT_TOP_P = 0.95
#     ALT_TOP_K = 25
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class WebSearchConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class FinanceDataConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.5-flash-lite"
#     TEMPERATURE = 0.0
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class ReportGenerationConfig:
#     MODEL = "azure/gpt-4.1"
#     # MODEL = "gemini/gemini-2.5-pro"
#     ALT_MODEL="gemini/gemini-2.0-flash"
#     # ALT_MODEL = "groq/llama-3.3-70b-versatile"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.2
#     MAX_TOKENS = 20000
#     ALT_MAX_TOKENS = 25000


# class TaskValidationConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     # MODEL = "gemini/gemini-2.0-flash-lite"
#     ALT_MODEL = "gemini/gemini-2.5-pro"
#     TEMPERATURE = 0.7
#     ALT_TEMPERATURE = 0.7
#     MAX_TOKENS = 1000
#     ALT_MAX_TOKENS = 1000


# class ValidationConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.5-pro"
#     TEMPERATURE = 0.6
#     ALT_TEMPERATURE = 0.6
#     MAX_TOKENS = 2000
#     ALT_MAX_TOKENS = 2000


# class SummarizerConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.3
#     STREAM = True
#     ALT_TEMPERATURE = 0.25


# class CountUsageMetricsPricingConfig:
#     MODEL = "gemini/gemini-2.0-flash-lite"
#     ALT_MODEL = "gemini/gemini-2.5-flash"


# class GetRelatedQueriesConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "groq/llama-3.3-70b-versatile"
#     TEMPERATURE = 0.2
#     ALT_TEMPERATURE = 0.4
#     MAX_TOKENS = 800
#     ALT_MAX_TOKENS = 800


# class GenerateSessionTitleConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     # MODEL = "gemini/gemini-2.0-flash-lite"
#     # MODEL = "groq/llama-3.3-70b-versatile"
#     ALT_MODEL = "gemini/gemini-2.0-flash"
#     TEMPERATURE = 0.4
#     ALT_TEMPERATURE = 0.4
#     MAX_TOKENS = 128
#     ALT_MAX_TOKENS = 128


# class StockPredictionConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     # prefer Groq Qwen/Mixtral as ALT for long financial sequences; Gemini primary for deterministic behavior
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.0
#     ALT_TEMPERATURE = 0.0
#     MAX_TOKENS = 1500
#     ALT_MAX_TOKENS = 1500


# class GraphGenerationConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     # MODEL = "gemini/gemini-2.5-flash"
#     ALT_MODEL = "gemini/gemini-2.5-flash-lite"
#     # ALT_MODEL = "groq/llama-3.3-70b-versatile"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.2
#     MAX_TOKENS = 2000
#     ALT_MAX_TOKENS = 2000




# class FastAgentConfig:
#     MODEL = "gemini/gemini-2.5-flash"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.15
#     ALT_TEMPERATURE = 0.6
#     MAX_TOKENS = 6000
#     ALT_MAX_TOKENS = 6000


# class IntentDetectionConfig:
#     MODEL = "gemini/gemini-2.0-flash-lite"
#     ALT_MODEL = "gemini/gemini-2.5-flash"
#     TEMPERATURE = 0.4
#     ALT_TEMPERATURE = 0.4
#     MAX_TOKENS = None
#     ALT_MAX_TOKENS = None



# class PlannerConfig:
#     MODEL = "gemini/gemini-2.5-flash"
#     ALT_MODEL = "gemini/gemini-2.5-flash-lite"
#     TEMPERATURE = 0.0
#     ALT_TEMPERATURE = 0.0
#     MAX_TOKENS = None
#     ALT_MAX_TOKENS = None


# class ExecutorConfig:
#     MODEL = "gemini/gemini-2.5-flash"
#     ALT_MODEL = "gemini/gemini-2.5-flash-lite"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class ManagerConfig:
#     # MODEL = "gemini/gemini-2.5-pro"
#     # ALT_MODEL = "gemini/gemini-2.5-flash"
#     MODEL="gemini-2.5-flash"
#     ALT_MODEL = "gemini/gemini-2.5-flash-lite"
#     TEMPERATURE = 0.6
#     ALT_TOP_P = 0.95
#     ALT_TOP_K = 25
#     ALT_TEMPERATURE = 0.6
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class WebSearchConfig:
#     MODEL = "gemini/gemini-2.5-flash-lite"
#     ALT_MODEL = "gemini/gemini-2.5-flash"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class FinanceDataConfig:
#     # MODEL = "gemini/gemini-2.5-flash"
#     MODEL = "gemini/gemini-2.0-flash-lite"
#     ALT_MODEL = "gemini/gemini-2.0-flash"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class ReportGenerationConfig:
#     # MODEL = "gemini/gemini-2.5-flash-lite-preview"
#     MODEL = "gemini/gemini-2.5-pro"
#     ALT_MODEL = "gemini/gemini-2.5-flash"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 20000
#     ALT_MAX_TOKENS = 4000


# class TaskValidationConfig:
#     MODEL = "gemini/gemini-2.0-flash-lite"
#     ALT_MODEL = "gemini/gemini-2.5-flash"
#     TEMPERATURE = 0.7
#     ALT_TEMPERATURE = 0.7
#     MAX_TOKENS = 1000
#     ALT_MAX_TOKENS = 1000


# class ValidationConfig:
#     MODEL = "gemini/gemini-2.0-flash-lite"
#     ALT_MODEL = "gemini/gemini-2.5-flash"
#     TEMPERATURE = 0.6
#     ALT_TEMPERATURE = 0.6
#     MAX_TOKENS = 2000
#     ALT_MAX_TOKENS = 2000


# class SummarizerConfig:
#     MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.3
#     STREAM = True
    
    
# class CountUsageMetricsPricingConfig:
#     MODEL = "gemini/gemini-2.0-flash-lite"
    

# class GetRelatedQueriesConfig:
#     MODEL = "gemini/gemini-2.5-flash"
#     ALT_MODEL = "gemini/gemini-2.5-flash-lite"
#     TEMPERATURE = 0.2
#     ALT_TEMPERATURE = 0.6
    
# class GenerateSessionTitleConfig:
#     MODEL = "gemini/gemini-2.0-flash-lite"
#     ALT_MODEL = "gemini/gemini-2.5-flash"
#     TEMPERATURE = 0.4
#     ALT_TEMPERATURE = 0.4
    
    
# class StockPredictionConfig:
#     # MODEL = "gemini/gemini-2.5-pro"
#     MODEL = "gemini/gemini-2.5-flash-lite"
#     TEMPERATURE = 0.0
    
# class GraphGenerationConfig:
#     MODEL = "gemini/gemini-2.5-flash"
#     TEMPERATURE = 0.1
    