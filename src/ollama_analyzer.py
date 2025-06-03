# src/ollama_analyzer.py
import json
import os
import requests
import time
import traceback 
import utils 

# --- Configuration ---
OLLAMA_CHAT_ENDPOINT = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen3:1.7b" # CONFIRM YOUR MODEL (e.g., "gemma:2b")
OLLAMA_REQUEST_TIMEOUT = 240 

# Cache for loaded prompt components
_prompt_cache = {}

def _load_prompt_component(filename):
    """Loads a prompt component from file and caches it in memory."""
    if filename not in _prompt_cache:
        content = utils.load_prompt_template(filename)
        if not content:
            print(f"[OLLAMA PROMPT ERRO] Failed to load prompt component: {filename}")
            _prompt_cache[filename] = f"ERROR: Prompt component '{filename}' not loaded."
        else:
            _prompt_cache[filename] = content
    return _prompt_cache[filename]

def _build_ollama_messages(field_info):
    """
    Builds the 'messages' list for the Ollama chat API.
    field_info: dict containing model_name_context, full_field_path, field_name, field_description
    """
    system_instructions = _load_prompt_component("system_instructions_rgpd_expert.txt")
    user_task_template = _load_prompt_component("user_task_and_field_info_template.txt")
    response_examples = _load_prompt_component("response_format_examples.txt")

    if "ERROR:" in system_instructions or "ERROR:" in user_task_template or "ERROR:" in response_examples:
        return None # Indicates a critical error in loading prompts

    # Inject field-specific info into the user task template
    user_message_content = user_task_template.format(
        model_name_context=field_info["model_name_context"],
        full_field_path=field_info["full_field_path"],
        field_name=field_info["field_name"],
        field_description=field_info["field_description"]
    )

    # Construct the full user message, including response examples for few-shot prompting
    # The examples help the model adhere to the format and task.
    full_user_prompt_with_examples = f"{user_message_content}\n\n--- RESPONSE FORMAT EXAMPLES ---\n{response_examples}"

    return [
        {"role": "system", "content": system_instructions},
        {"role": "user", "content": full_user_prompt_with_examples}
    ]

def _parse_ollama_model_response(model_response_str, log_prefix):
    """Parses the JSON string returned by the LLM."""
    try:
        analysis_from_model = json.loads(model_response_str)
        if isinstance(analysis_from_model, dict) and \
           "pii_sensitivity_assessment" in analysis_from_model and \
           "gdpr_justification" in analysis_from_model:
            return analysis_from_model
        else:
            print(f"{log_prefix} ERRO: Model's JSON response has unexpected format: {model_response_str[:200]}...")
            return {"pii_sensitivity_assessment": "ERROR_MODEL_JSON_FORMAT", 
                    "gdpr_justification": f"Unexpected model JSON format: {model_response_str}"}
    except json.JSONDecodeError as je:
        print(f"{log_prefix} ERRO CRÍTICO: Failed to decode model's JSON response string. Error: {je}")
        return {"pii_sensitivity_assessment": "ERROR_MODEL_JSON_DECODE", 
                "gdpr_justification": f"Model returned non-JSON string: {model_response_str[:200]}...", 
                "exception": str(je)}

def _handle_ollama_api_error(response, log_prefix, response_text_on_error):
    """Handles errors from the Ollama API response itself (not model errors)."""
    if "error" in response: # Structured error from Ollama API
        print(f"{log_prefix} ERRO API Ollama: {response['error']}")
        return {"pii_sensitivity_assessment": "ERROR_OLLAMA_API_STRUCTURED", 
                "gdpr_justification": response['error']}
    else: # Unexpected API response format
        print(f"{log_prefix} ERRO: Unexpected Ollama API response format (no 'message' or 'error'): {str(response)[:200]}...")
        return {"pii_sensitivity_assessment": "ERROR_OLLAMA_API_FORMAT", 
                "gdpr_justification": f"Unexpected API response: {str(response)}"}


def analyze_single_field_ollama(unique_field_key, field_description, current_count=0, total_count=0):
    """
    Orchestrates the analysis of a single field with Ollama using the chat API and structured prompts.
    """
    progress_log = f"({current_count}/{total_count})" if total_count > 0 else ""
    log_prefix = f"[OLLAMA_CHAT {unique_field_key} {progress_log}]"
    print(f"{log_prefix} Starting analysis...")

    filename_context, full_path_in_schema = unique_field_key.split("::", 1)
    field_name = full_path_in_schema.split('.')[-1]

    field_info = {
        "model_name_context": os.path.splitext(filename_context)[0],
        "full_field_path": full_path_in_schema,
        "field_name": field_name,
        "field_description": field_description if field_description else "N/A"
    }

    messages = _build_ollama_messages(field_info)
    if messages is None: # Error loading prompt components
        return {"pii_sensitivity_assessment": "ERROR_PROMPT_LOADING", 
                "gdpr_justification": "Failed to load one or more prompt components."}

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "format": "json" # Instruct Ollama that the *assistant's message content* should be JSON
    }
    
    # print(f"{log_prefix} Payload to be sent (partial messages for brevity):")
    # print(json.dumps({"model": OLLAMA_MODEL, "messages": [{"role": m["role"], "content": m["content"][:200] + "..."} for m in messages], "format": "json"}, indent=2))


    analysis_result = {"pii_sensitivity_assessment": "ERROR_OLLAMA_CALL_UNHANDLED", "gdpr_justification": "Ollama call did not complete as expected."}
    response_text_for_log = "Response not captured."
    http_status = "N/A"

    try:
        response = requests.post(OLLAMA_CHAT_ENDPOINT, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT)
        http_status = response.status_code
        response_text_for_log = response.text
        
        print(f"{log_prefix} HTTP Status: {http_status}")
        # print(f"{log_prefix} Raw Response (first 300 chars): {response_text_for_log[:300]}...") # Uncomment for deep debug

        response.raise_for_status() # Raises HTTPError for 4xx/5xx
        
        response_data_json = response.json() # Parse the API's JSON response

        if "message" in response_data_json and isinstance(response_data_json["message"], dict) and "content" in response_data_json["message"]:
            model_response_content_str = response_data_json["message"]["content"]
            analysis_result = _parse_ollama_model_response(model_response_content_str, log_prefix)
        else: # API response format is not as expected (e.g., no "message" or "content")
            analysis_result = _handle_ollama_api_error(response_data_json, log_prefix, response_text_for_log)
            
    except Exception as ex:
        analysis_result = utils._handle_ollama_request_exception(ex, log_prefix, response_text_for_log, http_status) # Use utils version
    
    print(f"{log_prefix} Result: Sensitivity='{analysis_result.get('pii_sensitivity_assessment', 'N/A')}'")
    return analysis_result