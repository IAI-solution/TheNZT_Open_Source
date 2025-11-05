class FastAgentConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.0-flash-lite"
    TEMPERATURE = 0.15
    ALT_TEMPERATURE = 0.6
    MAX_TOKENS = 6000
    ALT_MAX_TOKENS = 6000


class IntentDetectionConfig:
    MODEL = "gemini/gemini-2.0-flash-lite"
    ALT_MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.4
    ALT_TEMPERATURE = 0.4
    MAX_TOKENS = None
    ALT_MAX_TOKENS = None



class PlannerConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.5-flash-lite"
    TEMPERATURE = 0.0
    ALT_TEMPERATURE = 0.0
    MAX_TOKENS = None
    ALT_MAX_TOKENS = None


class ExecutorConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.5-flash-lite"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class ManagerConfig:
    MODEL = "gemini/gemini-2.5-pro"
    ALT_MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.6
    ALT_TOP_P = 0.95
    ALT_TOP_K = 25
    ALT_TEMPERATURE = 0.6
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class WebSearchConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.5-flash-lite"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class FinanceDataConfig:
    MODEL = "gemini/gemini-2.5-flash"
    # MODEL = "gemini/gemini-2.0-flash-lite"
    ALT_MODEL = "gemini/gemini-2.0-flash"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class ReportGenerationConfig:
    # MODEL = "gemini/gemini-2.5-flash-lite-preview"
    MODEL = "gemini/gemini-2.5-pro"
    ALT_MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 20000
    ALT_MAX_TOKENS = 4000


class TaskValidationConfig:
    MODEL = "gemini/gemini-2.0-flash-lite"
    ALT_MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.7
    ALT_TEMPERATURE = 0.7
    MAX_TOKENS = 1000
    ALT_MAX_TOKENS = 1000


class ValidationConfig:
    MODEL = "gemini/gemini-2.0-flash-lite"
    ALT_MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.6
    ALT_TEMPERATURE = 0.6
    MAX_TOKENS = 2000
    ALT_MAX_TOKENS = 2000


class SummarizerConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.3
    STREAM = True
    
    
class CountUsageMetricsPricingConfig:
    MODEL = "gemini/gemini-2.0-flash-lite"
    

class GetRelatedQueriesConfig:
    MODEL = "gemini/gemini-2.5-flash"
    ALT_MODEL = "gemini/gemini-2.5-flash-lite"
    TEMPERATURE = 0.2
    ALT_TEMPERATURE = 0.6
    
class GenerateSessionTitleConfig:
    MODEL = "gemini/gemini-2.0-flash-lite"
    ALT_MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.4
    ALT_TEMPERATURE = 0.4
    
    
class StockPredictionConfig:
    MODEL = "gemini/gemini-2.5-pro"
    TEMPERATURE = 0.0
    
class GraphGenerationConfig:
    MODEL = "gemini/gemini-2.5-flash"
    TEMPERATURE = 0.1
    