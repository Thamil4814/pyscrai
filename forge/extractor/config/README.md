# Launcher Configuration

This directory contains **Flet UI-specific** configuration settings.

## Purpose

Settings in this directory are **only** used by the Launcher application and should contain:
- Window size and position preferences
- Theme and color preferences
- Last opened page/view
- UI layout preferences
- Launcher-specific feature flags

## What Does NOT Go Here

Do NOT put these in `forge/launcher/config`:
- ❌ LLM/AI model settings → Use `forge/shared/config/settings/`
- ❌ Database configuration → Use `forge/shared/config/settings/`
- ❌ Domain prompts → Use `forge/shared/config/prompts/`
- ❌ Business logic settings → Use `forge/shared/config/settings/`

## Architecture Rule

> **If the Sandbox or Engine needs it, it belongs in `forge/shared/config`**
> 
> **If only the Launcher UI needs it, it belongs here**

## Example Files (Future)

```yaml
# ui_preferences.yaml
window:
  width: 1200
  height: 800
  position: center
  
theme:
  mode: dark
  accent_color: "#6366f1"
  
navigation:
  last_page: "entities"
  sidebar_expanded: true
```
