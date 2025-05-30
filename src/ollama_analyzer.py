# src/ollama_analyzer.py

import json
import requests
import time
import traceback 
import utils 
import os
# --- Configurações do Ollama ---
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:1b" # CONFIRME O SEU MODELO (ex: "gemma:2b")
OLLAMA_REQUEST_TIMEOUT = 240 

def analyze_single_field_with_ollama(unique_field_key, field_description):
    log_prefix = f"[OLLAMA {unique_field_key}]" # Log mais curto
    print(f"{log_prefix} Iniciando análise...") # Log principal da função

    filename_context, full_path_in_schema = unique_field_key.split("::", 1)
    path_parts = full_path_in_schema.split('.')
    field_name = path_parts[-1]

    prompt_template = utils.load_prompt_template("rgpd_single_field_assessment_prompt.txt")
    if not prompt_template:
        print(f"{log_prefix} ERRO: Template de prompt não carregado.") # Log de erro
        return {"sensibilidade_rgpd": "ERRO_PROMPT_NAO_ENCONTRADO", "justificacao_rgpd": "Template de prompt não pôde ser carregado."}

    prompt_text = prompt_template.format(
        model_name_context=os.path.splitext(filename_context)[0],
        full_field_path=full_path_in_schema,
        field_name=field_name,
        field_description=field_description if field_description else "N/A"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt_text,
        "stream": False,
        "format": "json"
    }
    
    # Logs detalhados do pedido (comentados por defeito)
    # print(f"{log_prefix} Endpoint: {OLLAMA_ENDPOINT}")
    # print(f"{log_prefix} Modelo: {OLLAMA_MODEL}")
    # prompt_para_log = payload.get('prompt', '')
    # print(f"{log_prefix} Tamanho do Prompt (caracteres): {len(prompt_para_log)}")
    # # ... (outros prints detalhados do prompt e payload) ...

    analysis_result = {"sensibilidade_rgpd": "ERRO_DESCONHECIDO_OLLAMA", "justificacao_rgpd": "Análise não concluída."}
    response_text_for_log_on_error = "Resposta não capturada antes do erro."

    try:
        # print(f"{log_prefix} Enviando pedido POST...") # Pode ser mantido se quiser ver cada envio
        response = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT)
        response_text_for_log_on_error = response.text
        
        # Log do status HTTP é útil
        print(f"{log_prefix} Status HTTP: {response.status_code}") 
        
        # Logs da resposta bruta (comentados por defeito)
        # print(f"{log_prefix} Tamanho da Resposta Bruta (caracteres): {len(response_text_for_log_on_error)}")
        # # ... (outros prints da resposta bruta) ...

        response.raise_for_status() 
        response_data = response.json()

        if "response" in response_data:
            analysis_json_str = response_data["response"]
            try:
                analysis_from_model = json.loads(analysis_json_str)
                if isinstance(analysis_from_model, dict) and "sensibilidade_rgpd" in analysis_from_model and "justificacao_rgpd" in analysis_from_model:
                    analysis_result = analysis_from_model
                else: # Formato inesperado do JSON interno
                    print(f"{log_prefix} ERRO: Formato JSON interno inesperado: {analysis_json_str[:200]}...")
                    analysis_result = {"sensibilidade_rgpd": "ERRO_FORMATO_OLLAMA_INTERNO", "justificacao_rgpd": f"Resposta inesperada: {analysis_json_str}"}
            except json.JSONDecodeError as je: # Falha ao decodificar JSON interno
                print(f"{log_prefix} ERRO CRÍTICO: Falha ao decodificar JSON interno: '{analysis_json_str[:200]}...' Erro: {je}")
                analysis_result = {"sensibilidade_rgpd": "ERRO_DECODE_OLLAMA_INTERNO", "justificacao_rgpd": analysis_json_str, "exception": str(je)}
        elif "error" in response_data: # Erro estruturado do Ollama
            print(f"{log_prefix} ERRO API Ollama: {response_data['error']}")
            analysis_result = {"sensibilidade_rgpd": "ERRO_API_OLLAMA_ESTRUTURADO", "justificacao_rgpd": response_data['error']}
        else: # Formato JSON principal inesperado
            print(f"{log_prefix} ERRO: Formato JSON principal inesperado (sem 'response' ou 'error'): {str(response_data)[:200]}...")
            analysis_result = {"sensibilidade_rgpd": "ERRO_FORMATO_INESPERADO_OLLAMA", "justificacao_rgpd": str(response_data)}
            
    except requests.exceptions.HTTPError as http_err:
        print(f"{log_prefix} ERRO HTTP: {http_err}. Resposta: {response_text_for_log_on_error[:300]}...")
        analysis_result = {"sensibilidade_rgpd": "ERRO_HTTP_OLLAMA", "justificacao_rgpd": response_text_for_log_on_error, "status_code": http_err.response.status_code if http_err.response else "N/A"}
    except requests.exceptions.Timeout:
        print(f"{log_prefix} ERRO: Timeout ({OLLAMA_REQUEST_TIMEOUT}s).")
        analysis_result = {"sensibilidade_rgpd": "ERRO_TIMEOUT_OLLAMA", "justificacao_rgpd": f"Timeout de {OLLAMA_REQUEST_TIMEOUT}s"}
    except requests.exceptions.RequestException as req_err: # Outros erros de 'requests'
        print(f"{log_prefix} ERRO DE REQUESTS: {req_err}")
        analysis_result = {"sensibilidade_rgpd": "ERRO_REQUESTS_OLLAMA", "justificacao_rgpd": str(req_err)}
    except json.JSONDecodeError as json_err: # Erro se response.json() falhar
        print(f"{log_prefix} ERRO DE DECODIFICAÇÃO JSON (resposta principal): {json_err}. Resposta: {response_text_for_log_on_error[:300]}...")
        analysis_result = {"sensibilidade_rgpd": "ERRO_DECODE_JSON_RESPOSTA_PRINCIPAL", "justificacao_rgpd": response_text_for_log_on_error, "exception": str(json_err)}
    except Exception as ex:
        print(f"{log_prefix} ERRO CRÍTICO INESPERADO: {ex}")
        # print(traceback.format_exc()) # Manter comentado a menos que precise do stack trace completo
        analysis_result = {"sensibilidade_rgpd": "ERRO_INESPERADO_GERAL_OLLAMA", "justificacao_rgpd": str(ex)}
    
    # Log do resultado final da análise para este campo
    print(f"{log_prefix} Resultado: Sensibilidade='{analysis_result.get('sensibilidade_rgpd', 'N/A')}'")
    # print(f"{log_prefix} --- FIM DO PEDIDO OLLAMA ---") # Opcional, pode remover para menos verbosidade
    return analysis_result