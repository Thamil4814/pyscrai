import streamlit as st
from pathlib import Path
from forge.shared.domain.ingestion.extraction.service import ExtractionService

class ExtractionLab:
    def render(self, session):
        st.header("⚗️ Extraction Lab")
        st.caption("Ingest documents and transmute them into knowledge entities.")

        col_left, col_right = st.columns([1, 2], gap="large")

        with col_left:
            st.subheader("1. Ingest")
            uploaded_files = st.file_uploader(
                "Upload Source Material (PDF/TXT)", 
                accept_multiple_files=True
            )
            
            if uploaded_files:
                if st.button(f"Process {len(uploaded_files)} Files"):
                    self._handle_ingest(session, uploaded_files)

            st.divider()
            st.subheader("2. Configuration")
            chunk_size = st.slider("Chunk Size", 256, 2048, 512)
            overlap = st.slider("Overlap", 0, 512, 50)
            
            if st.button("Run Extraction", type="primary", use_container_width=True):
                self._run_extraction(session, chunk_size, overlap)

        with col_right:
            st.subheader("3. Live Logs")
            with st.status("System Ready", expanded=True) as status:
                st.write("Waiting for command...")

    def _handle_ingest(self, session, files):
        source_dir = session.project_path / "source_docs"
        source_dir.mkdir(exist_ok=True)
        count = 0
        for uploaded_file in files:
            dest_path = source_dir / uploaded_file.name
            with open(dest_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            count += 1
        st.success(f"Ingested {count} files into {source_dir.name}")

    def _run_extraction(self, session, chunk_size, overlap):
        source_dir = session.project_path / "source_docs"
        db_path = str(session.project_path / "world.duckdb")
        
        if not source_dir.exists() or not list(source_dir.glob("*.pdf")) + list(source_dir.glob("*.txt")):
            st.warning("No documents found. Please upload files first.")
            return
        
        with st.status("Extracting entities...", expanded=True) as status:
            try:
                st.write("🔧 Initializing ExtractionService...")
                service = ExtractionService(
                    db_connection_string=db_path,
                    chunk_size=chunk_size,
                    chunk_overlap=overlap
                )
                
                st.write(f"📂 Processing documents in {source_dir.name}...")
                result = service.process_directory(source_dir)
                
                if "error" in result:
                    st.error(f"❌ {result['error']}")
                    status.update(label="Extraction failed", state="error")
                else:
                    st.write(f"✅ Processed {result['processed_files']} files")
                    st.write(f"🔍 Extracted {result['entities_count']} entities")
                    status.update(label="Extraction complete", state="complete")
                    st.success(f"Successfully extracted {result['entities_count']} entities from {result['processed_files']} documents")
            
            except Exception as e:
                st.error(f"❌ Extraction failed: {str(e)}")
                status.update(label="Extraction error", state="error")
