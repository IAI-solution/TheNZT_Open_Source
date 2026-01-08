class FastAgentConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.15
    ALT_TEMPERATURE = 0.4
    MAX_TOKENS = 6000
    ALT_MAX_TOKENS = 6000


class IntentDetectionConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.3
    ALT_TEMPERATURE = 0.4
    MAX_TOKENS = None
    ALT_MAX_TOKENS = None


class PlannerConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.0
    ALT_TEMPERATURE = 0.0
    MAX_TOKENS = None
    ALT_MAX_TOKENS = None


class ExecutorConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 25000


class ManagerConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.6
    ALT_TEMPERATURE = 0.6
    ALT_TOP_P = 0.95
    ALT_TOP_K = 25
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class WebSearchConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class FinanceDataConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.0
    ALT_TEMPERATURE = 0.1
    MAX_TOKENS = 4000
    ALT_MAX_TOKENS = 4000


class ReportGenerationConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.2
    MAX_TOKENS = 20000
    ALT_MAX_TOKENS = 25000


class TaskValidationConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.7
    ALT_TEMPERATURE = 0.7
    MAX_TOKENS = 1000
    ALT_MAX_TOKENS = 1000


class ValidationConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.6
    ALT_TEMPERATURE = 0.6
    MAX_TOKENS = 2000
    ALT_MAX_TOKENS = 2000


class SummarizerConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.3
    STREAM = True
    ALT_TEMPERATURE = 0.25


class CountUsageMetricsPricingConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"


class GetRelatedQueriesConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.2
    ALT_TEMPERATURE = 0.4
    MAX_TOKENS = 800
    ALT_MAX_TOKENS = 800


class GenerateSessionTitleConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.4
    ALT_TEMPERATURE = 0.4
    MAX_TOKENS = 128
    ALT_MAX_TOKENS = 128


class StockPredictionConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.0
    ALT_TEMPERATURE = 0.0
    MAX_TOKENS = 1500
    ALT_MAX_TOKENS = 1500


class GraphGenerationConfig:
    MODEL = "azure/gpt-4.1-mini"
    ALT_MODEL = "azure/gpt-4.1"
    TEMPERATURE = 0.1
    ALT_TEMPERATURE = 0.2
    MAX_TOKENS = 2000
    ALT_MAX_TOKENS = 2000
