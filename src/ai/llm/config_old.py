class FastAgentConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.15
    ALT_TEMPERATURE = 0.6
    MAX_TOKENS = 6000
    ALT_MAX_TOKENS = 6000


# class FastAgentConfig:
#     # LLM_PROVIDER=huggingface
#     # MODEL = "mistralai/Mixtral-8x7B-Instruct-v0.1"
#     MODEL = "gemini/gemini-2.5-flash"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.15
#     ALT_TEMPERATURE = 0.6
#     MAX_TOKENS = 6000
#     ALT_MAX_TOKENS = 6000


class IntentDetectionConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.4
    ALT_TEMPERATURE = 0.4
    MAX_TOKENS = None
    ALT_MAX_TOKENS = None


class DBSearchConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class PlannerConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.0
    ALT_TEMPERATURE = 0.0
    MAX_TOKENS = None
    ALT_MAX_TOKENS = None


class ExecutorConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class ManagerConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "groq/qwen-qwq-32b"
    TEMPERATURE = 0.6
    ALT_TOP_P = 0.95
    ALT_TOP_K = 25
    ALT_TEMPERATURE = 0.6
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class WebSearchConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class SocialMediaConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class FinanceDataConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class CodingConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.2
    ALT_TEMPERATURE = 0.2
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class DataComparisonConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class SentimentAnalysisConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class ReportGenerationConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 20000
    ALT_MAX_TOKENS = 4000


class TaskValidationConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.7
    ALT_TEMPERATURE = 0.7
    MAX_TOKENS = 1000
    ALT_MAX_TOKENS = 1000


class ValidationConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.6
    ALT_TEMPERATURE = 0.6
    MAX_TOKENS = 2000
    ALT_MAX_TOKENS = 2000


class MapConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.2
    ALT_TEMPERATURE = 0.2
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class SummarizerConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.3
    STREAM = True


class DeepProcessQueryInitialConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.4
    STREAM = True


class DeepProcessQueryFinalConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.3


class DeepSeachQueryConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.6


class DeepRelevanceCheckConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.3


class DeepTopicStructureConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.4


class DeepTopicReportConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.4


class DeepFinalReportConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.3


class SummarizerConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.7
    STREAM = True
    
    
class CountUsageMetricsPricingConfig:
    MODEL = "gemini/gemini-2.5-pro"
    

class GetRelatedQueriesConfig:
    MODEL = "gemini/gemini-2.5-pro"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.2
    ALT_TEMPERATURE = 0.6
    
class GenerateSessionTitleConfig:
    MODEL = "gemini/gemini-2.5-pro"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.4
    ALT_TEMPERATURE = 0.4
    
    
class StockPredictionConfig:
    MODEL = "gemini/gemini-2.5-pro"
    TEMPERATURE = 0.0
    
class GraphGenerationConfig:
    MODEL = "gemini/gemini-2.5-pro"
    TEMPERATURE = 0.1
    
class WebSearchConfig:
    MODEL = "gemini/gemini-2.5-pro"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.0
    ALT_TEMPERATURE = 0.0
    


# Azure


# class IntentDetectionConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.4
#     ALT_TEMPERATURE = 0.4
#     MAX_TOKENS = None
#     ALT_MAX_TOKENS = None


# class DBSearchConfig:
#     MODEL = "azure/gpt-4o-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class PlannerConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.0
#     ALT_TEMPERATURE = 0.0
#     MAX_TOKENS = None
#     ALT_MAX_TOKENS = None


# class ExecutorConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class ManagerConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "groq/qwen-qwq-32b"
#     TEMPERATURE = 0.6
#     ALT_TOP_P = 0.95
#     ALT_TOP_K = 25
#     ALT_TEMPERATURE = 0.6
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class WebSearchConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class SocialMediaConfig:
#     MODEL = "azure/gpt-4o-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class FinanceDataConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class CodingConfig:
#     MODEL = "azure/gpt-4o-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.2
#     ALT_TEMPERATURE = 0.2
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class DataComparisonConfig:
#     MODEL = "azure/gpt-4o-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class SentimentAnalysisConfig:
#     MODEL = "azure/gpt-4o-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class ReportGenerationConfig:
#     MODEL = "azure/gpt-4.1"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.1
#     ALT_TEMPERATURE = 0.1
#     MAX_TOKENS = 20000
#     ALT_MAX_TOKENS = 4000


# class TaskValidationConfig:
#     MODEL = "azure/gpt-4o-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.7
#     ALT_TEMPERATURE = 0.7
#     MAX_TOKENS = 1000
#     ALT_MAX_TOKENS = 1000


# class ValidationConfig:
#     MODEL = "azure/gpt-4o-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.6
#     ALT_TEMPERATURE = 0.6
#     MAX_TOKENS = 2000
#     ALT_MAX_TOKENS = 2000


# class MapConfig:
#     MODEL = "azure/gpt-4o-mini"
#     ALT_MODEL = "gemini/gemini-2.0-flash-lite"
#     TEMPERATURE = 0.2
#     ALT_TEMPERATURE = 0.2
#     MAX_TOKENS = 4000
#     ALT_MAX_TOKENS = 4000


# class SummarizerConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     TEMPERATURE = 0.3
#     STREAM = True


# class DeepProcessQueryInitialConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     TEMPERATURE = 0.4
#     STREAM = True


# class DeepProcessQueryFinalConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     TEMPERATURE = 0.3


# class DeepSeachQueryConfig:
#     MODEL = "azure/gpt-4.1-nano"
#     TEMPERATURE = 0.6


# class DeepRelevanceCheckConfig:
#     MODEL = "azure/gpt-4o-mini"
#     TEMPERATURE = 0.3


# class DeepTopicStructureConfig:
#     MODEL = "azure/gpt-4o-mini"
#     TEMPERATURE = 0.4


# class DeepTopicReportConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     TEMPERATURE = 0.4


# class DeepFinalReportConfig:
#     MODEL = "azure/gpt-4o-mini"
#     TEMPERATURE = 0.3


# class SummarizerConfig:
#     MODEL = "azure/gpt-4.1-mini"
#     TEMPERATURE = 0.7
#     STREAM = True


