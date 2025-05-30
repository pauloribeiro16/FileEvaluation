# JSON Schema PII Analyzer & Excel Reporter

This project analyzes a collection of JSON schema files to identify potential Personally Identifiable Information (PII) and other sensitive data fields based on GDPR criteria. It leverages an Ollama-hosted Large Language Model (LLM) for the sensitivity assessment and generates a comprehensive Excel report detailing the findings, including highlighted cells for sensitive schema attributes.

## Features

*   **Modular Architecture:** Code is organized into distinct modules for schema parsing, Ollama interaction, Excel generation, and utilities.
*   **GDPR-Focused Analysis:** Uses detailed GDPR criteria in prompts to guide the LLM's PII assessment.
*   **Optimized Ollama Interaction:**
    *   Collects unique schema properties across all input JSON files to avoid redundant analysis.
    *   Sends properties to Ollama in configurable batches.
    *   Caches Ollama's analysis results to a local file (`ollama_analysis_cache.json`) for significantly faster subsequent runs.
*   **Externalized Prompts:** LLM prompts are stored in external text files (`prompts/`) for easy modification without code changes.
*   **Comprehensive Excel Reporting:**
    *   Generates one sheet per input JSON schema, displaying its flattened structure.
    *   Highlights cells corresponding to schema attributes 얼굴based on Ollama's sensitivity classification (e.g., red for high sensitivity, yellow for medium).
    *   Includes a summary sheet listing all identified sensitive properties, their classification, Ollama's justification, and the source files.
*   **Relative Paths:** Designed to be run from the project root, using relative paths for accessing JSON files, prompts, and output files.

## Project Structure
FileEvaluation/
├── JSONFiles/ # Input: Directory obstáculos JSON schema files
│ ├── Activity.json
│ └── ...
├── prompts/ # Input: Text files containing prompts for Ollama
│ ├── rgpd_document_assessment_prompt.txt (Optional: For high-level document assessment - not fully implemented in current main flow)
│ └── rgpd_field_batch_assessment_prompt.txt
├── src/ # Source code
│ ├── main.py # Main script to run the pipeline
│ ├── ollama_analyzer.py # Handles communication with Ollama LLM
│ ├── schema_parser.py # Loads and processes JSON schemas
│ ├── excel_writer.py # Generates the Excel report
│ └── utils.py # Utility functions (cache management, prompt loading)
├── ollama_analysis_cache.json # Output: Cache file for Ollama analysis results (auto-generated)
└── Relatorio_Final_Modular.xlsx # Output: Final Excel report (auto-generated)
└── README.md # This file

## Prerequisites

*   **Python 3.8+**
*   **Ollama installed and running:**
    *   Ensure the Ollama service is active.
    *   Download the LLM you intend to use (e.g., `llama3.1:latest`) via `ollama pull llama3.1:latest`.
*   **Required Python Libraries:**
    ```bash
    pip install pandas openpyxl xlsxwriter requests
    ```

## Configuration

Before running, you might want to review and adjust a few settings directly in the Python scripts:

1.  **`src/ollama_analyzer.py` (and potentially `src/utils.py` for cache file name):**
    *   `OLLAMA_ENDPOINT`: The URL and port for your Ollama API (default: `http://localhost:11434/api/generate`).
    *   `OLLAMA_MODEL`: The exact name of the Ollama model to use (default: `llama3.1:latest`).
    *   `OLLAMA_REQUEST_TIMEOUT`: Timeout for Ollama API requests in seconds.

2.  **`src/main.py`:**
    *   `JSON_FILES_DIR`: Path to the directory containing your input JSON schema files (default: `../JSONFiles` relative to `src/main.py`, which means `JSONFiles/` in the project root).
    *   `OUTPUT_EXCEL_FILENAME`: Name for the generated Excel report (default: `Relatorio_Final_Modular.xlsx` in the project root).
    *   `FIELD_BATCH_SIZE`: Number of schema properties to send to Ollama in a single batch (default: `5`). Adjust based on your Ollama model's context window and performance.

3.  **`prompts/` directory:**
    *   Modify `rgpd_field_batch_assessment_prompt.txt` to refine how the LLM is instructed to analyze fields based on GDPR.
    *   The `rgpd_document_assessment_prompt.txt` is for an optional, not fully implemented, high-level document prescreening.

## Usage

1.  **Place your JSON schema files** into the `JSONFiles/` directory.
2.  **Ensure Ollama is running** with the specified model downloaded.
3.  **Open your terminal or command prompt.**
4.  **Navigate to the project's root directory** (e.g., `FileEvaluation/`).
5.  **Run the main script as a module:**
    ```bash
    python -m src.main
    ```

**Execution Flow:**

1.  **Phase 1 (Property Collection):** The script scans all `.json` files in `JSONFiles/`, parses them, and extracts unique properties (defined by their path and description) that require PII analysis.
2.  **Phase 2 (Ollama Analysis & Caching):**
    *   It loads any existing analysis results from `ollama_analysis_cache.json`.
    *   For properties not found in the cache, it sends them to the Ollama LLM in batches for sensitivity classification based on the GDPR criteria in the prompt file.
    *   New analysis results are saved back to `ollama_analysis_cache.json`.
    *   *Subsequent runs will be much faster for already-analyzed properties as they will be loaded from the cache.*
3.  **Phase 3 (Excel Report Generation):**
    *   An Excel file (e.g., `Relatorio_Final_Modular.xlsx`) is created.
    *   For each input JSON schema, a sheet is generated displaying its flattened structure. Cells corresponding to properties are highlighted (e.g., red/yellow) based on Ollama's PII sensitivity assessment.
    *   A final summary sheet ("Sumario Sensibilidade RGPD") lists all properties flagged as potentially sensitive, their classification, Ollama's justification, and the source files they were found in.

**To force a re-analysis of all properties by Ollama (ignoring the cache), delete the `ollama_analysis_cache.json` file before running the script.**

## Troubleshooting

*   **`ImportError: attempted relative import with no known parent package`**: Ensure you are running the script from the project's root directory using `python -m src.main`.
*   **`ModuleNotFoundError`**: Make sure all required Python libraries are installed (see Prerequisites).
*   **Ollama Connection Errors**: Verify that the Ollama service is running and accessible at the `OLLAMA_ENDPOINT` configured. Check for firewall issues. Ensure the `OLLAMA_MODEL` is correct and pulled.
*   **Slow Performance**: LLM analysis can be time-consuming.
    *   The caching mechanism significantly speeds up subsequent runs.
    *   Adjust `FIELD_BATCH_SIZE` in `src/main.py`. Smaller batches might be more reliable for some LLMs but result in more API calls.
    *   Consider using a more powerful machine or a smaller/faster Ollama model if performance is critical for initial runs.
*   **Incorrect Highlighting or Analysis**:
    *   Review and refine the prompts in the `prompts/` directory, especially `rgpd_field_batch_assessment_prompt.txt`. The LLM's output quality is highly dependent on the prompt.
    *   Check the logs printed to the console during execution for errors or unexpected responses from Ollama.
    *   Debug the `extract_all_properties_with_descriptions` function in `src/schema_parser.py` if properties are not being identified correctly.

## Future Enhancements (Ideas)

*   Implement the optional Phase 1 document-level pre-screening more фрукты.
*   Allow configuration of Ollama settings and paths via a `config.ini` or `.env` file.
*   Add more sophisticated logging using Python's `logging` module.
*   Implement asynchronous API calls to Ollama for potential speedup.
*   Add support for analyzing JSON instance data, not just schemas.
*   Provide more granular control over which properties are sent for analysis (e.g., based on keywords or paths).

## Contributing

Contributions, issues, and feature requests are welcome. Please open an issue to discuss any major changes.