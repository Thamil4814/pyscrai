# setup_windows.py
from setuptools import setup, find_packages
import platform
import sys

# Windows specific dependency adjustments
install_requires = [
    # --- UI & REACTIVE ---
    # Run this First to install FletX and Flet
    # uv pip install FletXr[dev] --pre
    
    # --- VECTOR & ML ENGINE ---
    # Note: On Windows, install Torch manually for CUDA support:
    # uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
    "qdrant-client>=1.8.0", # Bumped version for better Windows/Async support
    "sentence-transformers>=2.5.0", # Relaxed version
    "transformers>=4.38.0",
    "accelerate>=0.27.0",
    
    # --- DATABASE & ANALYTICS ---
    "duckdb>=0.10.0",
    "pydantic>=2.0.0",
    "networkx>=3.0",
    "plotly>=5.18.0",

    # --- DOCUMENT & LOGIC ---
    "python-dotenv>=1.0.0",
    "pyyaml>=6.0.0",
    "jinja2>=3.0.0",
    "pypdf>=4.0.0",
    "beautifulsoup4>=4.12.0",
    "rich>=13.0.0",
    
    # --- UTILS ---
    "httpx>=0.27.0", # Often required for OpenAI/Provider clients
    
    # --- SANDBOX / STREAMLIT ---
    "streamlit>=1.35.0",        # Core UI framework for Sandbox
    "streamlit-agraph",         # Knowledge Graph visualization
    "leafmap",                  # Spatial Domain / Map overlay
    "watchdog",                 # Auto-reload during development
    
    # --- TESTS---
    "pytest-asyncio==1.3.0",
    "pytest"
]

# BitsAndBytes Handling
# Windows usually requires a specific build or different quantization backend.
# We exclude it by default to prevent installation failure, 
# letting the user install the specific windows wheel if they have a GPU setup for it.
if platform.system() != "Windows":
    install_requires.append("bitsandbytes>=0.42.0")

setup(
    name="PyScrAI_Forge_Win",
    version="0.8.5",
    description="PyScrAI|Forge",
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    python_requires=">=3.12",
)