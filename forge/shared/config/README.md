# PyScrAI Forge Shared Configuration

This directory contains configuration settings and prompts **shared by all PyScrAI applications** (Launcher, Sandbox, Engine).

## Directory Structure

```
forge/shared/config/
├── prompts/           # Jinja2 templates for LLM prompts
│   ├── templates/     # .j2 template files
│   ├── manager.py     # Prompt rendering logic
│   └── __init__.py
└── settings/          # YAML configuration files
    ├── defaults.yaml  # System defaults
    ├── project.yaml   # Project-specific overrides
    └── user.yaml      # User-specific overrides
```

## Configuration Hierarchy (4-Tier)

Configuration values are resolved in this order (highest priority first):

1. **Environment Variables** (`PYSCRAI_*`, `os.environ`): Ephemeral overrides (e.g., API keys)
2. **Project Configuration** (`project.yaml`): Persistent, project-specific settings
3. **User Configuration** (`user.yaml`): User-level preferences across projects
4. **System Defaults** (`defaults.yaml`): Baseline fallback values

## Configuration Categories

### 1. LLM (Language Model) Settings
- **Provider selection**: `default_provider`, `secondary_provider`, `semantic_provider`
- **API keys**: `openrouter_api_key`, `cherry_api_key`, `lm_proxy_api_key`
- **Model selection**: `openrouter_model`, etc.
- **Rate limiting**: `rate_limit_max_concurrent`, `rate_limit_min_delay`, `rate_limit_max_retries`, `rate_limit_retry_delay`
- **Task-specific parameters**: `*_max_tokens`, `*_temperature` for extraction, profiling, synthesis, etc.

### 2. Vector Database (Qdrant)
- **Connection**: `url`, `api_key`, `embedding_dimension`
- **Collections**: `entities_collection`, `relationships_collection`
- **Similarity/deduplication**: `similarity_search_limit`, `similarity_search_threshold`, `deduplication_threshold`, `deduplication_limit`

### 3. Database (DuckDB)
- **Path**: `db_path`
- **Timeout**: `connection_timeout`
- **WAL mode**: `wal_mode`

### 4. Embedding Models
- **Device**: `device` (e.g., `cuda`, `cpu`)
- **Models**: `general_model`, `long_context_model`
- **Batching**: `batch_size`, `long_context_threshold`

### 5. UI Settings
- **Web mode**: `flet_web_mode`, `flet_port`, `flet_web_renderer`
- **Theme**: `theme_mode`, `primary_color`
- **Log**: `logs_feed_enabled`, `auto_refresh_interval`

### 6. Processing/Workflow
- **Delays**: `semantic_profiler_delay`, `graph_analysis_delay`
- **Automation**: `auto_deduplication`, `auto_relationship_inference`, `parallel_processing`

## How Precedence Works

When the system loads a configuration value, it checks in this order:
1. **Environment variable** (e.g., `OPENROUTER_API_KEY`)
2. **Project config** (e.g., `project.yaml` or project database)
3. **User config** (e.g., `user.yaml`)
4. **System default** (e.g., `defaults.yaml`)

The first value found is used. This allows for flexible overrides at any level.

## Editing Your Settings

- **User-level**: Copy `user.yaml` template, uncomment and edit your preferences.
- **Project-level**: Copy `project.yaml` template, edit for project-specific needs.
- **Environment**: Set environment variables in your shell or `.env` file for temporary overrides.

## Validation & Migration

- **Validation**: Critical settings (API keys, rate limits, model parameters) are validated using Pydantic. Invalid critical values will block startup and prompt correction.
- **Migration**: Legacy projects are automatically upgraded to the new config system. A migration notice appears in the Log.

## Example: Overriding the LLM Model

- To use a different model for a project, add to `project.yaml`:
  ```yaml
  llm:
    openrouter_model: "anthropic/claude-3-haiku-20240307"
  ```
- To override for all projects, add to `user.yaml`.
- To override just for a session, set the environment variable:
  ```sh
  export OPENROUTER_MODEL="anthropic/claude-3-haiku-20240307"
  ```

## Troubleshooting

- If a setting is not taking effect, check for higher-precedence overrides (env > project > user > system).
- For validation errors, see the Log for details and correction prompts.
- For advanced usage, see the comments in each YAML file for available options.

---

For more details, see the code in `forge/core/configuration.py` and the templates in `forge/config/settings/`.
