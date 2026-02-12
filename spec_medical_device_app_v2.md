# Technical Specification: Medical Device Application & Agentic Review System

## 1. Introduction

This specification outlines the architecture and functional requirements for a **Medical Device Application Webpage** powered by Agentic AI. The system is designed to streamline the creation, management, and review of medical device applications (specifically modeled after the "20 entities" structure of standard application forms). It empowers users to interact with application data, review guidance, and AI agents through a centralized Streamlit interface deployed on Hugging Face Spaces.

## 2. System Architecture

### 2.1 High-Level Flow
1.  **Data Ingestion**: User uploads application datasets (CSV/JSON) or PDFs.
2.  **Form Generation**: System generates a structured Markdown application form (20 entities).
3.  **Guidance Integration**: User uploads/pastes Review Guidance (Text/MD/PDF).
4.  **Agentic Review**: AI Agents analyze the Application Form against the Review Guidance.
5.  **Report Generation**: System produces a Review Summary in Markdown.
6.  **Configuration**: User manages Agents and Skills via the UI.

### 2.2 Tech Stack
-   **Frontend**: Streamlit
-   **Deployment**: Hugging Face Spaces (Dockerized)
-   **Orchestration**: Custom Python Agent Framework using `agents.yaml` and `SKILL.md`.
-   **Model Providers**: OpenAI, Gemini (Google), Anthropic.
-   **Data Processing**: `pandas` (CSV/JSON), `pypdf`/`pdf2image` (PDF), `streamlit-ace` (Editor).

## 3. Functional Modules

### 3.1 Application Dataset Management
**Requirement**: "User can modify, download or upload application datasets (csv, json)."
-   **Upload**: File uploader accepting `.csv` and `.json`.
-   **View/Edit**: `st.data_editor` for tabular editing of dataset records.
-   **Download**: Export modified datasets as CSV or JSON.

### 3.2 Application Form Generation
**Requirement**: "System will create application form in markdown with 20 entities in a table with title and context."
-   **Entity Model**: The system defines a schema of 20 core entities (e.g., Device Name, Manufacturer, Indications, Sterilization Method, Shelf Life, etc.).
-   **Generation Logic**:
    -   Input: Selected row from Dataset.
    -   Output: Markdown table format.
    -   Example Format:
        ```markdown
        | Entity ID | Title | Context/Value |
        | :--- | :--- | :--- |
        | 01 | Device Name | SuperMed 3000 |
        | 02 | Intended Use | Treatment of acute... |
        ...
        ```
-   **Editing**: `st.text_area` or `st.markdown` (with `unsafe_allow_html=True` for rendering) allowing users to modify the generated form directly in Markdown or Plain Text view.

### 3.3 Review Guidance Management
**Requirement**: "User can paste or upload review guidance (text, markdown, pdf). User can modify, download..."
-   **Input Methods**:
    -   **Paste**: Text area for direct input.
    -   **Upload**: Support for `.txt`, `.md`, `.pdf`.
-   **PDF Handling**:
    -   If PDF is uploaded, system extracts text (using `pypdf`).
-   **Persistence**: Modified guidance is stored in Session State and can be downloaded as `.md`.

### 3.4 Agentic Review Execution
**Requirement**: "Agent will use the modified review guidance to execute on the previous application form and create review summary..."
-   **Workflow**:
    1.  **Context Assembly**: Combine `Application Form` + `Review Guidance` + `System Prompt (SKILL.md)`.
    2.  **Agent Selection**: User selects the specific "Reviewer Agent" from `agents.yaml`.
    3.  **Model Selection**: User overrides default model (Gemini-2.5, GPT-4o, etc.).
    4.  **Prompt Engineering**: User scans/edits the final prompt before execution.
    5.  **Execution**: Call LLM API.
    6.  **Output**: Generate Review Summary (Markdown).
-   **Report Features**:
    -   "Keep Prompt": Option to append the used prompt to the bottom of the generated report for audit trails.
    -   Editable Output: User can refine the generated summary.

### 3.5 PDF Trimming & OCR Pipeline
**Requirement**: "System will use python package to trim the pdf and do OCR..."
-   **PDF Viewer**: `iframe` based viewer for previewing uploaded PDFs.
-   **Trimming**: UI inputs for "Start Page" and "End Page". System slices the PDF using `pypdf`.
-   **OCR Strategy**:
    -   **Option A (Python)**: `pytesseract` (requires system dependencies) or purely text-based extraction if native PDF.
    -   **Option B (LLM)**: Gemini Flash (Multimodal) for high-accuracy OCR of scanned pages.
    -   **User Choice**: Toggle switch in UI.
-   **Reorganization**:
    -   Convert extraction to Markdown.
    -   **Keyword Highlighting**: Identify critical keywords (defined in `SKILL.md` or Session) and wrap them in HTML specifically: `<span style="color:coral">keyword</span>`.

### 3.6 Agent Configuration Studio
**Requirement**: "User can modify, download, upload agents.yaml, SKILL.md. Standardization..."
-   **Editors**: Tabbed interface to edit `agents.yaml` and `SKILL.md` content directly.
-   **Upload & Standardization**:
    -   If user uploads a non-standard `agents.yaml`, the system runs a "Standardizer Agent" (using a small model like `gpt-4o-mini`) to map the uploaded structure to the compliant schema required by the app.
    -   Standardized YAML is then loaded into the editor for verification.

## 4. UI/UX Design

### 4.1 Layout
-   **Sidebar**: Global Controls (API Keys, Reset Session).
-   **Main Tabs**:
    1.  **Dataset & Form**: Upload data, Select record, Generate Form.
    2.  **Guidance & Review**: Upload guidance, Run Review Agent.
    3.  **PDF Studio**: Upload PDF, Trim/OCR, View Results.
    4.  **Config Studio**: Edit Agents/Skills.

### 4.2 Application Form View
-   **Split View**:
    -   **Left**: The Rendered Markdown Form (Table).
    -   **Right**: The Raw Markdown Editor.

## 5. Implementation Details

### 5.1 Data Models (Pseudo-code)

**Application Form Entity**:
```python
@dataclass
class ApplicationEntity:
    id: str
    title: str
    context: str
```

**Dataset Loader**:
```python
def load_dataset(file):
    if file.name.endswith('.csv'):
        return pd.read_csv(file)
    elif file.name.endswith('.json'):
        return pd.read_json(file)
```

### 5.2 Agent Execution Logic
```python
def run_review(app_form_md, guidance_md, model_name):
    prompt = f"""
    You are a Regulatory Reviewer.
    
    # APPLICATION FORM
    {app_form_md}
    
    # REVIEW GUIDANCE
    {guidance_md}
    
    # TASK
    Analyze the application against the guidance. Produce a summary.
    """
    return call_llm(model=model_name, prompt=prompt)
```

## 6. Security & Deployment

-   **API Handling**: Keys provided via UI (Session State) or Environment Variables (Secrets).
-   **Sensitive Data**: No data logging. All processing is ephemeral.
-   **Deployment**: `Dockerfile` setup for Streamlit on Hugging Face.
