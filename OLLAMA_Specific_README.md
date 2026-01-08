# TheNZT Open Source - LLM Provider Configuration Guide

This guide explains how to configure and switch between different LLM providers (Ollama, OpenAI, Azure) for the TheNZT AI agent system.

## Table of Contents
- [Overview](#overview)
- [Switching Between LLM Providers](#switching-between-llm-providers)
- [Provider Setup Guides](#provider-setup-guides)
  - [Ollama Setup](#ollama-setup)
  - [OpenAI Setup](#openai-setup)
  - [Azure OpenAI Setup](#azure-openai-setup)
- [Configuration Details](#configuration-details)
- [Rate Limits and Usage Monitoring](#rate-limits-and-usage-monitoring)
- [Security Best Practices](#security-best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

The system supports three LLM providers:
- **Ollama**: Open-source LLM platform with models like Minimax-M2, GPT-OSS, Kimi-K2
- **OpenAI**: Commercial API with GPT-4.1 models
- **Azure OpenAI**: Microsoft's Azure-hosted OpenAI service

The provider is selected via the `LLM_PROVIDER` environment variable in your `.env` file, and the system automatically loads the corresponding configuration.

---

## Files Modified or Created in this Branch

To enable support for multiple LLM providers (Ollama, OpenAI, Azure) and improve documentation, the following files were created or modified:

### Core Configuration Files (src/ai/llm/)

#### 1. **config.py** (Modified - Router File)
**Location:** `src/ai/llm/config.py`

This is the main router file that determines which provider configuration to load. It reads the `LLM_PROVIDER` environment variable and dynamically imports the appropriate configuration.

**Key Features:**
- Implements priority logic:
  1. `LLM_PROVIDER` env var (explicit choice)
  2. Presence of `OPENAI_API_KEY` → defaults to OpenAI
  3. Default → Ollama
- Dynamically imports provider-specific config using Python's `import` statement
- Prints console message indicating which configuration was loaded
- No changes needed in agent files - they all import from this single config.py

**Code Structure:**
```python
llm_provider = os.getenv("LLM_PROVIDER").lower()

if llm_provider == "openai":
    from .config_openai import *
elif llm_provider == "ollama":
    from .config_ollama import *
elif llm_provider == "azure":
    from .config_azure import *
```

#### 2. **config_ollama.py** (Created)
**Location:** `src/ai/llm/config_ollama.py`

Contains all agent-specific configurations for Ollama models.

**Models Used:**
- Primary: `openai/minimax-m2:cloud`, `openai/kimi-k2:1t`, `openai/gpt-oss:20b-cloud`
- Alternative: `openai/gpt-oss:120b`

**Features:**
- Optimized temperature settings per agent (0.0 for deterministic tasks, 0.6 for creative tasks)
- Token limits ranging from 128 to 25,000 depending on agent
- Streaming support for summarizer
- Alternative model fallback for resilience

#### 3. **config_openai.py** (Created)
**Location:** `src/ai/llm/config_openai.py`

Contains all agent-specific configurations for OpenAI models.

**Models Used:**
- Primary: `openai/gpt-4.1-mini`
- Alternative: `openai/gpt-4.1`

**Features:**
- Maintains identical class structure as Ollama config for consistency
- Same agent configuration classes
- Similar temperature and token settings adapted for OpenAI models
- Cost-effective with gpt-4.1-mini as primary model

#### 4. **config_azure.py** (Created)
**Location:** `src/ai/llm/config_azure.py`

Contains all agent-specific configurations for Azure OpenAI deployments.

**Models Used:**
- Primary: `azure/gpt-4.1-mini`
- Alternative: `azure/gpt-4.1`

**Features:**
- Compatible with Azure OpenAI service deployments
- Requires `AZURE_API_BASE` and `AZURE_API_KEY` in environment
- Model names prefixed with `azure/` for proper routing
- Identical class structure for seamless switching

#### 5. **model.py** (Modified)
**Location:** `src/ai/llm/model.py`

Updated to support dynamic provider selection and configuration loading.

#### 6. **config_old.py** (Created)
**Location:** `src/ai/llm/config_old.py`

Archived copy of the previous single-provider configuration.

### Agent Modifications (src/ai/agents/)

The following agents were updated to utilize the new multi-provider configuration system:

- **intent_detector.py** 
- **manager_agent.py**
- **planner_agent.py**
- **response_generator_agent.py**
- **summarizer.py**
- **task_validator.py**
- **utils.py**
- **validation_agent.py**
- **web_search_agent.py**

### Backend Utilities (src/backend/utils/)

Updated to make the pipeline Ollama and multi-LLM provider compatible:

- **agent_comm.py**
- **utils.py**


### Environment and Documentation Files

#### 5. **.env** (Modified)
**Location:** Project root `/.env`

Added LLM provider configuration variables:

```properties
# Provider Selection
LLM_PROVIDER="ollama"  # Options: "ollama", "openai", "azure"

# API Keys for each provider
OLLAMA_API_KEY="your-ollama-key"
OPENAI_API_KEY="your-openai-key"
AZURE_API_KEY="your-azure-key"
AZURE_API_BASE="https://your-resource.openai.azure.com/"
```

### Project Structure

```
TheNZT_Open_Source/
├── src/
│   ├── ai/
│   │   ├── llm/
│   │   │   ├── config.py              # Router (Modified)
│   │   │   ├── config_ollama.py       # Ollama config (Created)
│   │   │   ├── config_openai.py       # OpenAI config (Created)
│   │   │   ├── config_azure.py        # Azure config (Created)
│   │   │   ├── config_old.py          # Previous config (archived)
│   │   │   └── model.py               # Model utilities
│   │   ├── agents/                    # Agent implementations
│   │   │   ├── base_agent.py
│   │   │   ├── coding_agent.py
│   │   │   ├── data_comparison_agent.py
│   │   │   ├── db_search_agent.py
│   │   │   ├── executor_agent.py
│   │   │   ├── fast_agent.py
│   │   │   ├── finance_data_agent.py
│   │   │   ├── intent_detector.py
│   │   │   ├── manager_agent.py
│   │   │   ├── map_agent.py
│   │   │   ├── planner_agent.py
│   │   │   ├── rag_engine.py
│   │   │   ├── response_generator_agent.py
│   │   │   ├── sentiment_analysis_agent.py
│   │   │   ├── social_media_agent.py
│   │   │   ├── summarizer.py
│   │   │   ├── task_validator.py
│   │   │   ├── utils.py
│   │   │   ├── validation_agent.py
│   │   │   └── web_search_agent.py
│   │   ├── tools/                     # AI tools
│   │   │   ├── code_gen_tools.py
│   │   │   ├── finance_data_tools.py
│   │   │   ├── finance_scraper_utils.py
│   │   │   ├── financial_tools.py
│   │   │   ├── graph_gen_tool.py
│   │   │   ├── internal_db_tools.py
│   │   │   ├── map_tools.py
│   │   │   ├── social_media_tools.py
│   │   │   └── web_search_tools.py
│   │   └── stock_prediction/
│   ├── backend/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   └── utils/
│   └── frontend/
│       └── ...
├── .env                               # Environment config (Modified)
├── .env.example                       # Example environment file
└── ...
```

### How Agent Files Use Configurations

All agent files import configurations from the main `config.py`:

```python
# Example: src/ai/agents/planner_agent.py
from src.ai.llm.config import PlannerConfig

# Agent automatically uses the configuration from selected provider
model = PlannerConfig.MODEL
temperature = PlannerConfig.TEMPERATURE
```

**Key Benefit:** No changes needed in agent implementation files when switching providers. Just update `.env` and restart the application.

### What Changed vs. Original Implementation

**Before:**
- Single hardcoded configuration file
- Models were fixed to one provider
- Required code changes to switch providers

**After:**
- Three separate provider configurations
- Dynamic configuration loading via router
- Switch providers by changing one environment variable
- All agent logic remains unchanged
- Fallback mechanism for API failures using ALT_MODEL

---

## Switching Between LLM Providers

To switch between providers, modify the `LLM_PROVIDER` variable in your `.env` file:

### Step 1: Open your `.env` file

Located in the root directory of the project.

### Step 2: Update the LLM_PROVIDER variable

```properties
# For Ollama
LLM_PROVIDER="ollama"

# For OpenAI
# LLM_PROVIDER="openai"

# For Azure
# LLM_PROVIDER="azure"
```

**To switch providers:**
1. Comment out the current active provider by adding `#` at the start
2. Uncomment your desired provider by removing the `#`
3. Restart your application

**Example - Switching from Ollama to OpenAI:**

```properties
# Before
LLM_PROVIDER="ollama"
# LLM_PROVIDER="openai"

# After
# LLM_PROVIDER="ollama"
LLM_PROVIDER="openai"
```

### Step 3: Ensure API Keys are Configured

Make sure you have valid API keys for your chosen provider in the `.env` file:

```properties
OLLAMA_API_KEY="your-ollama-api-key-here"
OPENAI_API_KEY="your-openai-api-key-here"
AZURE_API_KEY="your-azure-api-key-here"
AZURE_API_BASE="your-azure-endpoint-here"
```

⚠️ **Important**: Never commit your `.env` file to version control. Keep your API keys secure.

---

## Provider Setup Guides

### Ollama Setup

#### Creating an Ollama Account

1. **Navigate to Ollama Sign In Page**
   
   Visit: [https://signin.ollama.com](https://signin.ollama.com/?client_id=client_01JX0QMHD43PFFCCNXH82A6K8B&redirect_uri=https%3A%2F%2Follama.com%2Fauth%2Fcallback&authorization_session_id=01KEEFM7SE8VX60ZD0WRTKCP4S)

2. **Sign Up or Log In**
   - Click "Sign Up" if you're a new user
   - Or log in with existing credentials
   - You can use Google, GitHub, or email authentication

3. **Complete Registration**
   - Follow the on-screen instructions
   - Verify your email if required

#### Getting Your Ollama API Key

1. **Access API Keys Settings**
   
   After logging in, navigate to: [https://ollama.com/settings/keys](https://ollama.com/settings/keys)

2. **Create New API Key**
   - Click "Create API Key" or similar button
   - Give your key a descriptive name (e.g., "TheNZT Production")
   - Copy the generated API key immediately (you won't see it again!)

3. **Add to .env File**
   
   ```properties
   OLLAMA_API_KEY="your-generated-api-key-here"
   ```

#### Ollama Model Configuration

The system uses these Ollama models:
- **Primary Models**: `openai/minimax-m2:cloud`, `openai/kimi-k2:1t`, `openai/gpt-oss:20b-cloud`
- **Alternative Models**: `openai/gpt-oss:120b`

These are configured in `src/ai/llm/config_ollama.py` and are automatically selected based on the task.

---

### OpenAI Setup

#### Getting Your OpenAI API Key

1. **Create OpenAI Account**
   
   Visit: [https://platform.openai.com/signup](https://platform.openai.com/signup)

2. **Navigate to API Keys**
   
   Go to: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)

3. **Create New Secret Key**
   - Click "Create new secret key"
   - Name your key (e.g., "TheNZT Production")
   - Copy the key immediately (shown only once)

4. **Add to .env File**
   
   ```properties
   OPENAI_API_KEY="sk-proj-your-api-key-here"
   ```

#### OpenAI Model Configuration

The system uses:
- **Primary Model**: `openai/gpt-4.1-mini`
- **Alternative Model**: `openai/gpt-4.1`

Configured in `src/ai/llm/config_openai.py`.

---

### Azure OpenAI Setup

#### Setting Up Azure OpenAI

1. **Azure Account Required**
   
   You need an active Azure subscription

2. **Create Azure OpenAI Resource**
   - Go to Azure Portal
   - Create a new "Azure OpenAI" resource
   - Note your endpoint URL and API key

3. **Add to .env File**
   
   ```properties
   AZURE_API_BASE="https://your-resource-name.openai.azure.com/"
   AZURE_API_KEY="your-azure-api-key-here"
   ```

#### Azure Model Configuration

The system uses:
- **Primary Model**: `azure/gpt-4.1-mini`
- **Alternative Model**: `azure/gpt-4.1`

Configured in `src/ai/llm/config_azure.py`.

---

## Configuration Details

### How Configuration Loading Works

The system uses a router pattern in `src/ai/llm/config.py`:

```python
# Priority order:
# 1. LLM_PROVIDER environment variable (explicit choice)
# 2. Presence of OPENAI_API_KEY → defaults to OpenAI
# 3. Default → Ollama
```

### Agent-Specific Configurations

Each agent type has specific model configurations:

| Agent | Purpose | Primary Model (Ollama) |
|-------|---------|------------------------|
| FastAgent | Quick responses | minimax-m2:cloud |
| IntentDetection | Query classification | gpt-oss:20b-cloud |
| Planner | Task planning | kimi-k2:1t |
| Executor | Task execution | kimi-k2:1t |
| Manager | Coordination | kimi-k2:1t |
| WebSearch | Web queries | gpt-oss:20b-cloud |
| FinanceData | Financial analysis | gpt-oss:20b-cloud |
| ReportGeneration | Report creation | kimi-k2:1t |
| Summarizer | Content summarization | kimi-k2:1t |

### Temperature and Token Settings

Temperature controls randomness (0.0 = deterministic, 1.0 = creative):
- **Deterministic tasks** (Planning, Finance): 0.0 - 0.1
- **Balanced tasks** (Execution, Search): 0.1 - 0.3
- **Creative tasks** (Management, Validation): 0.6 - 0.7

Token limits vary by agent (128 - 25,000 tokens).

---

## Rate Limits and Usage Monitoring

### OpenAI Rate Limits

OpenAI enforces both **RPM** (Requests Per Minute) and **TPM** (Tokens Per Minute) limits:

| Tier | RPM | TPM | Daily Limit |
|------|-----|-----|-------------|
| Free | 3 | 40,000 | $20 equivalent |
| Tier 1 | 500 | 200,000 | Based on usage |
| Tier 2+ | Higher | Higher | Based on usage |

**Monitoring Usage:**
1. Visit [OpenAI Usage Dashboard](https://platform.openai.com/usage)
2. View hourly, daily, and monthly breakdowns
3. Set up usage alerts in billing settings

### Ollama Rate Limits

Ollama has different rate limits based on your subscription:

**Monitoring Usage:**
1. Visit your Ollama dashboard at [https://ollama.com/dashboard](https://ollama.com/dashboard)
2. Check API usage metrics
3. Monitor request counts and token usage

### Azure OpenAI Rate Limits

Azure uses **Tokens Per Minute (TPM)** limits:
- Configured per deployment
- Default: 120K TPM for GPT-4
- Can be increased via quota requests

**Monitoring Usage:**
1. Azure Portal → Your OpenAI Resource
2. Navigate to "Metrics" blade
3. View token usage, request rates, and errors
4. Set up Azure Monitor alerts

### Best Practices for Rate Limit Management

1. **Implement Exponential Backoff**
   - Already built into the system
   - Automatic retry on rate limit errors

2. **Use Alternative Models**
   - System automatically falls back to ALT_MODEL on primary model failure
   - Distributes load across models

3. **Monitor Token Usage**
   - Review `CountUsageMetricsPricingConfig` logs
   - Track expensive operations

4. **Batch Requests**
   - Use agent consolidation where possible
   - Combine related queries

---

## Security Best Practices

### Protecting Your API Keys

1. **Never Commit .env Files**
   
   Ensure `.env` is in your `.gitignore`:
   ```
   # .gitignore
   .env
   .env.local
   .env.*.local
   ```

2. **Use Environment-Specific Keys**
   - Development keys for testing
   - Production keys for live deployment
   - Rotate keys regularly

3. **Restrict Key Permissions**
   - OpenAI: Limit key permissions to required scopes
   - Azure: Use managed identities when possible
   - Ollama: Create separate keys per environment

4. **Monitor Key Usage**
   - Set up alerts for unusual activity
   - Review usage logs regularly
   - Deactivate unused keys

### Key Rotation

Regularly rotate your API keys:
1. Generate new key in provider dashboard
2. Update `.env` file with new key
3. Restart application
4. Deactivate old key after verification

---

## Troubleshooting

### Common Issues

#### "Invalid API Key" Error

**Symptoms:**
```
Error: Authentication failed
```

**Solutions:**
1. Verify key is correctly copied (no extra spaces)
2. Check key hasn't expired or been revoked
3. Ensure correct provider is selected in `.env`
4. Restart application after updating `.env`

#### Rate Limit Exceeded

**Symptoms:**
```
Error: Rate limit exceeded
```

**Solutions:**
1. Check your usage dashboard
2. Wait for rate limit window to reset
3. Upgrade to higher tier if needed
4. Implement request throttling in your application

#### Wrong Model Configuration

**Symptoms:**
```
Error: Model not found
```

**Solutions:**
1. Verify model names in config files
2. Ensure models are available for your subscription
3. Check for typos in model strings
4. For Azure: Verify deployment names match config

#### Provider Not Loading

**Symptoms:**
```
Loading Ollama Configuration (Default)
```
When you expected OpenAI/Azure.

**Solutions:**
1. Check `LLM_PROVIDER` in `.env` is uncommented
2. Verify no extra quotes or spaces
3. Ensure `.env` file is in project root
4. Restart application completely

### Getting Help

If you encounter issues:
1. Check application logs for detailed error messages
2. Verify all environment variables are set correctly
3. Test API keys independently using curl/Postman
4. Review provider status pages for outages

---

## Additional Resources

### Documentation Links

- **Ollama**: [https://ollama.com/docs](https://ollama.com/docs)
- **OpenAI**: [https://platform.openai.com/docs](https://platform.openai.com/docs)
- **Azure OpenAI**: [https://learn.microsoft.com/azure/ai-services/openai/](https://learn.microsoft.com/azure/ai-services/openai/)

### API Status Pages

- **OpenAI Status**: [https://status.openai.com](https://status.openai.com)
- **Azure Status**: [https://status.azure.com](https://status.azure.com)

---

## Environment Variables Reference

Complete list of LLM-related environment variables:

```properties
# LLM Provider Selection (choose one)
LLM_PROVIDER="ollama"          # Options: "ollama", "openai", "azure"

# Ollama Configuration
OLLAMA_API_KEY="your-key"

# OpenAI Configuration
OPENAI_API_KEY="your-key"

# Azure OpenAI Configuration
AZURE_API_BASE="your-endpoint"
AZURE_API_KEY="your-key"

# Additional LLM APIs (optional)
GEMINI_API_KEY="your-key"
GROQ_API_KEY="your-key"
```
