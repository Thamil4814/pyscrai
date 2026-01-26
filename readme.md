python -m forge.extractor.main

.\.venv\Scripts\streamlit.exe run forge/sandbox/app.py


Merging Extractor into Sandbox: 

### **Feasibility Verdict: Highly Recommended**

Yes, this is **absolutely feasible** and, frankly, a strategic architectural win.

Merging the Extractor capabilities into the Streamlit app simplifies your architecture from a "Hybrid Flet + Streamlit" stack to a single **Unified Streamlit Application**.

Here is the breakdown of why this works and how it simplifies your life:

### **1. The "Drift" Problem Solved**

You hit the nail on the head. The current "Dual-Database" architecture (`intel.duckdb` vs `world.duckdb`) exists primarily because the Extractor and Sandbox were separate apps that needed to share data without stepping on each other's toes.

* **Current State:** You need complex logic to detect if the "Raw Data" (`intel.duckdb`) changed and then sync it to the "World" (`world.duckdb`).
* **Unified State:** If Extraction happens inside the Sandbox, you can write directly to the `entities` table in `world.duckdb`. There is no "syncing" because the source of truth is singular. You eliminate the entire `drift_wizard.py` and `SyncService` logic.

### **2. Porting Logic is Straightforward**

The heavy lifting of extraction is already decoupled in your `forge/shared` library.

* **The Logic:** `forge.shared.domain.ingestion.extraction.service` is "headless" (it doesn't care about UI). It can be imported into Streamlit just as easily as Flet.
* **The UI:** The Settings page in Flet (`settings_controller.py`) translates almost 1:1 to Streamlit widgets (sliders for chunk size, text inputs for API keys).

### **3. The One "Gotcha": Long-Running Processes**

The main trade-off is user experience during the actual extraction.

* **Flet:** Good at async updates; the UI stays responsive while the backend crunches PDFs.
* **Streamlit:** Runs the script from top to bottom. If you click "Start Extraction," the UI will "freeze" (showing a spinner) until the batch is done unless you implement it carefully with `st.status` or background threads.
* *Mitigation:* Use `st.status("Processing documents...")` to show real-time logs/progress. It is acceptable for a "batch job" workflow.



---

### **Proposed Architecture: The "Unified Forge"**

If we proceed with this, the `forge/sandbox` becomes simply `forge/app`.

#### **1. New Page: `pages/01_project_hub.py**`

* **Replaces:** `project_controller.py` (Flet) and `project_selector.py` (Streamlit).
* **Features:**
* "Create New Project" form (Folder name, basic config).
* "Load Project" list.
* This sets the `session.project_path` for the rest of the app.



#### **2. New Page: `pages/02_extraction_lab.py**`

* **Replaces:** The entire Flet Extractor UI.
* **Inputs:**
* **Settings Panel:** Configure chunk size, overlap, LLM provider (ported from `settings_controller.py`).
* **Ingest:** A simple `st.file_uploader` to drop PDFs into the project `source_docs/` folder.


* **Action:**
* **"Run Extraction" Button:** Calls `ExtractionService.extract()`.
* **Output:** Writes directly to `world.duckdb`.



#### **3. Simplified Database Manager**

Your `SandboxDB` class gets much simpler:

```python
class SandboxDB:
    def connect(self):
        # No more ATTACH intel.duckdb
        # Just one connection to world.duckdb
        self.conn = duckdb.connect(str(self.project_path / "world.duckdb"))

```

### **Strategic Recommendation**

**Do it.**

1. **Drop Flet:** It removes an entire dependency chain and the complexity of maintaining two UI paradigms.
2. **Consolidate DB:** It removes the most fragile part of your code (the drift/sync logic).
3. **Focus:** You can spend all your energy making *one* really good Streamlit app instead of two "okay" apps.

**Would you like me to outline the file structure for this "Unified Forge" or start by porting a specific controller (like Settings) to a Streamlit view?**