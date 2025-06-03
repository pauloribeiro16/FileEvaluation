# src/utils.py
import json
import os
import requests

OLLAMA_ANALYSIS_CACHE_FILE = "ollama_analysis_cache.json" 

def load_prompt_template(prompt_filename):
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) 
    prompts_dir = os.path.join(script_dir, "prompts")
    filepath = os.path.join(prompts_dir, prompt_filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"[UTILS ERRO] Ficheiro de prompt não encontrado: {filepath}")
        return None
    # ... (restante como antes) ...
    except Exception as e:
        print(f"[UTILS ERRO] Erro ao carregar prompt de {filepath}: {e}")
        return None

def load_ollama_cache():
    # O cache é relativo à raiz do projeto onde main.py é executado
    project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # src -> project_root
    cache_path = os.path.join(project_root_dir, OLLAMA_ANALYSIS_CACHE_FILE)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                print(f"[CACHE INFO] Cache Ollama ({cache_path}) carregado com {len(cache_data)} entradas.")
                return cache_data
        except Exception as e:
            print(f"[CACHE ERRO] Erro ao carregar cache Ollama de {cache_path}: {e}. Um novo cache será usado.")
    return {}

def save_ollama_cache(cache_data):
    project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_path = os.path.join(project_root_dir, OLLAMA_ANALYSIS_CACHE_FILE)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[CACHE ERRO] Erro ao salvar cache Ollama em {cache_path}: {e}")


def clear_ollama_cache():
    """Elimina o ficheiro de cache do Ollama se existir."""
    project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cache_path = os.path.join(project_root_dir, OLLAMA_ANALYSIS_CACHE_FILE)
    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
            print(f"[CACHE INFO] Ficheiro de cache '{cache_path}' eliminado com sucesso.")
        except Exception as e:
            print(f"[CACHE ERRO] Erro ao eliminar ficheiro de cache '{cache_path}': {e}")
    else:
        print(f"[CACHE INFO] Ficheiro de cache '{cache_path}' não encontrado para eliminar.")

def _handle_ollama_request_exception(exception, log_prefix, response_text_on_error="N/A", status_code_on_error="N/A"):
    """Centralized exception handler for Ollama requests."""
    print(f"{log_prefix} ERROR DURING OLLAMA CALL: {type(exception).__name__} - {exception}")
    # Descomentar para depuração profunda de erros inesperados:
    # if not isinstance(exception, (requests.exceptions.HTTPError, requests.exceptions.Timeout, requests.exceptions.RequestException, json.JSONDecodeError) ):
    #    print(traceback.format_exc())

    details = str(exception)
    error_key = "ERROR_OLLAMA_CALL_GENERIC" # Chave em inglês
    additional_info = {}

    if isinstance(exception, requests.exceptions.HTTPError):
        error_key = "ERROR_OLLAMA_HTTP"
        details = f"Status {exception.response.status_code if exception.response else 'N/A'}, Response: {response_text_on_error[:300]}..."
        additional_info["status_code"] = exception.response.status_code if exception.response else 'N/A'
    elif isinstance(exception, requests.exceptions.Timeout):
        error_key = "ERROR_OLLAMA_TIMEOUT"
        # details = f"Timeout of {OLLAMA_REQUEST_TIMEOUT}s" # OLLAMA_REQUEST_TIMEOUT não está definido aqui, passar como arg ou usar string fixa
        details = "Request to Ollama timed out."
    elif isinstance(exception, requests.exceptions.RequestException):
        error_key = "ERROR_OLLAMA_REQUESTS"
    elif isinstance(exception, json.JSONDecodeError): 
        error_key = "ERROR_OLLAMA_JSON_DECODE_MAIN_RESPONSE"
        details = f"Failed to decode main API response: {response_text_on_error[:300]}..."
        additional_info["raw_response"] = response_text_on_error
    
    result = {
        "pii_sensitivity_assessment": error_key, 
        "gdpr_justification": details,
        "exception_type": type(exception).__name__
    }
    result.update(additional_info)
    if status_code_on_error != "N/A" and "status_code" not in result:
        result["http_status_code_captured"] = status_code_on_error
    return result