"""
Simple Streamlit Frontend for Research Paper Analysis
Upload PDF -> View Parsed Sections and Results
"""

import streamlit as st
import requests
import time

# Page config
st.set_page_config(
    page_title="Research Paper Analyzer",
    page_icon="📄",
    layout="wide"
)

# API URL
API_URL = "http://localhost:8000"

# Simple CSS
st.markdown("""
<style>
    .main-title {
        text-align: center;
        color: #1f77b4;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


def api_call(endpoint, method="GET", **kwargs):
    """Simple API call with error handling."""
    try:
        url = f"{API_URL}{endpoint}"
        
        if method == "GET":
            response = requests.get(url, **kwargs)
        elif method == "POST":
            response = requests.post(url, **kwargs)
        elif method == "DELETE":
            response = requests.delete(url, **kwargs)
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.ConnectionError:
        st.error("❌ API not running. Start FastAPI on http://localhost:8000")
        return None
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return None


def main():
    """Main app."""
    
    # Title
    st.markdown('<h1 class="main-title">📄 Research Paper Analyzer</h1>', unsafe_allow_html=True)
    st.write("Upload a research paper PDF and view the extracted sections and information.")
    st.markdown("---")
    
    # Tabs
    tab1, tab2 = st.tabs(["📤 Upload Paper", "📁 My Documents"])
    
    with tab1:
        upload_tab()
    
    with tab2:
        documents_tab()


def upload_tab():
    """Upload and process tab."""
    
    st.header("📤 Upload Research Paper")
    
    # File upload
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type="pdf",
        help="Upload a research paper in PDF format"
    )
    
    if uploaded_file:
        # File info
        file_size = uploaded_file.size / (1024 * 1024)
        st.info(f"📁 **{uploaded_file.name}** ({file_size:.1f} MB)")
        
        if st.button("🚀 Upload & Process", type="primary"):
            
            # Upload
            with st.spinner("Uploading..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                result = api_call("/upload", method="POST", files=files)
            
            if result:
                doc_id = result["document_id"]
                st.success(f"✅ Uploaded! Document ID: `{doc_id}`")
                
                # Wait for processing
                st.info("⏳ Processing with GROBID...")
                progress_bar = st.progress(0)
                
                for i in range(60):  # Wait up to 60 seconds
                    status_result = api_call(f"/status/{doc_id}")
                    
                    if status_result:
                        status = status_result["status"]
                        progress_bar.progress((i + 1) / 60)
                        
                        if status == "completed":
                            st.success("🎉 Processing completed!")
                            show_results(status_result)
                            break
                        elif status == "failed":
                            st.error(f"❌ Failed: {status_result.get('error', 'Unknown error')}")
                            break
                    
                    time.sleep(1)
                else:
                    st.warning("⏰ Still processing. Check 'My Documents' tab.")


def show_results(status_result):
    """Display processing results."""
    
    result = status_result.get("result", {})
    
    if result.get("status") != "success":
        st.error(f"❌ Processing failed: {result.get('error', 'Unknown error')}")
        return
    
    st.markdown("---")
    st.header("📊 Analysis Results")
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{len(result.get('sections', []))}</h3>
            <p>Sections</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{len(result.get('authors', []))}</h3>
            <p>Authors</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{len(result.get('references', []))}</h3>
            <p>References</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <h3>{result.get('processing_time', 0):.1f}s</h3>
            <p>Process Time</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Paper details
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Title
        st.subheader("📄 Title")
        st.write(result.get('title', 'Not found'))
        
        # Abstract
        st.subheader("📝 Abstract")
        abstract = result.get('abstract', '')
        if abstract and abstract != "Abstract not found":
            st.write(abstract)
        else:
            st.warning("Abstract not found")
    
    with col2:
        # Authors
        st.subheader("👥 Authors")
        authors = result.get('authors', [])
        if authors:
            for author in authors[:5]:
                st.write(f"**{author.get('name', 'Unknown')}**")
                st.caption(author.get('affiliation', 'No affiliation'))
        else:
            st.write("No authors found")
    
    # Sections
    st.subheader("📑 Sections")
    sections = result.get('sections', [])
    
    if sections:
        for i, section in enumerate(sections, 1):
            with st.expander(f"{i}. {section.get('title', 'Untitled')}"):
                content = section.get('content', 'No content')
                st.write(content)
    else:
        st.warning("No sections found")
    
    # References
    if result.get('references'):
        st.subheader("📚 References (First 5)")
        for i, ref in enumerate(result['references'][:5], 1):
            st.write(f"{i}. {ref}")


def documents_tab():
    """Documents management tab."""
    
    st.header("📁 My Documents")
    
    # Get documents
    docs = api_call("/documents")
    
    if not docs:
        return
    
    if len(docs) == 0:
        st.info("No documents uploaded yet. Use the 'Upload Paper' tab to get started!")
        return
    
    # Display documents
    for doc in docs:
        with st.expander(f"📄 {doc['filename']} - {doc['status'].upper()}"):
            
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.write(f"**ID:** `{doc['document_id']}`")
                st.write(f"**Status:** {doc['status']}")
                st.write(f"**Size:** {doc['file_size'] / 1024:.1f} KB")
                st.write(f"**Uploaded:** {doc['upload_time']}")
                
                # Show additional info if completed
                if doc['status'] == 'completed':
                    st.write(f"**Title:** {doc.get('title', 'N/A')}")
                    st.write(f"**Authors:** {doc.get('authors_count', 0)}")
                    st.write(f"**Sections:** {doc.get('sections_count', 0)}")
            
            with col2:
                if doc['status'] == 'completed':
                    if st.button("👁️ View Results", key=f"view_{doc['document_id']}"):
                        status_result = api_call(f"/status/{doc['document_id']}")
                        if status_result:
                            st.markdown("---")
                            show_results(status_result)
            
            with col3:
                if st.button("🗑️ Delete", key=f"del_{doc['document_id']}", type="secondary"):
                    result = api_call(f"/documents/{doc['document_id']}", method="DELETE")
                    if result:
                        st.success("Deleted!")
                        st.rerun()


if __name__ == "__main__":
    main()