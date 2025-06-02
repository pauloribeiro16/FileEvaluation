import json
import os # Adicionado para os.path.splitext
import requests
import time
import traceback 
import utils 

# --- Configurações do Ollama ---
OLLAMA_CHAT_ENDPOINT = "http://localhost:11434/api/chat" # NOVO ENDPOINT
OLLAMA_MODEL = "gemma3:1b" # CONFIRME O SEU MODELO
OLLAMA_REQUEST_TIMEOUT = 240 

# Variável global para guardar o system prompt carregado
_system_prompt_content = None

def get_system_prompt():
    """Carrega e retorna o system prompt, guardando-o em cache na memória."""
    global _system_prompt_content
    if _system_prompt_content is None:
        _system_prompt_content = utils.load_prompt_template("rgpd_single_field_assessment_prompt.txt")
        if not _system_prompt_content:
            print("[OLLAMA ERRO CRÍTICO] System prompt não pôde ser carregado! As análises falharão.")
            # Poderia levantar uma exceção aqui ou retornar um valor que indique falha
            _system_prompt_content = "ERRO: System prompt não carregado." 
    return _system_prompt_content

def analyze_single_field_with_ollama_chat(unique_field_key, field_description):
    """
    Analisa um único campo com Ollama usando a API /api/chat para manter contexto.
    unique_field_key: string no formato "filename.json::path.to.property"
    field_description: string da descrição da propriedade
    """
    log_prefix = f"[OLLAMA_CHAT {unique_field_key}]"
    print(f"{log_prefix} Iniciando análise via API de Chat...")

    filename_context, full_path_in_schema = unique_field_key.split("::", 1)
    path_parts = full_path_in_schema.split('.')
    field_name = path_parts[-1]

    system_prompt = get_system_prompt()
    if "ERRO: System prompt não carregado" in system_prompt:
         return {"sensibilidade_rgpd": "ERRO_SYSTEM_PROMPT", "justificacao_rgpd": system_prompt}

    # Construir a mensagem do utilizador específica para este campo
    # O template do system_prompt já contém as instruções gerais e os critérios RGPD
    # Agora precisamos apenas da parte variável para o campo atual.
    user_message_content = f"""
Analise o seguinte campo específico:
Nome do Modelo/Ficheiro de Contexto: {os.path.splitext(filename_context)[0]}
Caminho Completo da Chave no Esquema: {full_path_in_schema}
Nome da Chave Final: {field_name}
Descrição da Chave (do esquema): {field_description if field_description else "N/A"}

Lembre-se de responder APENAS em formato JSON com as chaves "sensibilidade_rgpd" e "justificacao_rgpd" para ESTE campo.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message_content}
    ]

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "format": "json" # Pedir explicitamente formato JSON na resposta do assistant
    }
    
    # --- Logging Detalhado do Pedido ---
    print(f"{log_prefix} Endpoint: {OLLAMA_CHAT_ENDPOINT}")
    # print(f"{log_prefix} Modelo: {OLLAMA_MODEL}") # Já no payload
    # try:
    #     payload_json_str = json.dumps(payload, indent=2, ensure_ascii=False)
    #     print(f"{log_prefix} Payload JSON a ser enviado:\n{payload_json_str[:1500]}...") # Imprimir parte do payload
    # except Exception as e:
    #     print(f"{log_prefix} ERRO ao serializar payload para log: {e}")
    # --- Fim do Logging Detalhado do Pedido ---

    analysis_result = {"sensibilidade_rgpd": "ERRO_DESCONHECIDO_OLLAMA_CHAT", "justificacao_rgpd": "Análise via chat não concluída."}
    response_text_for_log_on_error = "Resposta não capturada antes do erro."

    try:
        print(f"{log_prefix} Enviando pedido POST para API de Chat...")
        response = requests.post(OLLAMA_CHAT_ENDPOINT, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT)
        response_text_for_log_on_error = response.text
        print(f"{log_prefix} Resposta recebida. Status HTTP: {response.status_code}")
        
        # Log da resposta bruta (manter conciso, a menos que depurando ativamente)
        # print(f"{log_prefix} Resposta Bruta (início): {response_text_for_log_on_error[:300]}...")

        response.raise_for_status() 
        response_data = response.json() # Resposta da API /api/chat

        # A resposta do modelo estará dentro de response_data["message"]["content"]
        # e essa content DEVE ser uma string JSON por causa do "format": "json"
        if "message" in response_data and isinstance(response_data["message"], dict) and "content" in response_data["message"]:
            analysis_json_str = response_data["message"]["content"]
            # print(f"{log_prefix} String JSON extraída de message.content: {analysis_json_str}")
            try:
                analysis_from_model = json.loads(analysis_json_str)
                if isinstance(analysis_from_model, dict) and "sensibilidade_rgpd" in analysis_from_model and "justificacao_rgpd" in analysis_from_model:
                    analysis_result = analysis_from_model
                    # print(f"{log_prefix} String JSON interna parseada com sucesso.")
                else:
                    print(f"{log_prefix} ERRO: Resposta JSON interna (chat) não tem o formato esperado: {analysis_json_str[:200]}...")
                    analysis_result = {"sensibilidade_rgpd": "ERRO_FORMATO_OLLAMA_CHAT_INTERNO", "justificacao_rgpd": f"Resposta inesperada: {analysis_json_str}"}
            except json.JSONDecodeError as je:
                print(f"{log_prefix} ERRO CRÍTICO: Falha ao decodificar JSON da string de resposta interna (chat): '{analysis_json_str[:200]}...' Erro: {je}")
                analysis_result = {"sensibilidade_rgpd": "ERRO_DECODE_OLLAMA_CHAT_INTERNO", "justificacao_rgpd": analysis_json_str, "exception": str(je)}
        elif "error" in response_data:
            print(f"{log_prefix} ERRO estruturado retornado por Ollama (chat): {response_data['error']}")
            analysis_result = {"sensibilidade_rgpd": "ERRO_API_OLLAMA_CHAT_ESTRUTURADO", "justificacao_rgpd": response_data['error']}
        else: # Formato inesperado da resposta da API /api/chat
            print(f"{log_prefix} ERRO: Formato inesperado da API /api/chat (sem 'message' ou 'error'): {str(response_data)[:200]}...")
            analysis_result = {"sensibilidade_rgpd": "ERRO_FORMATO_API_CHAT_OLLAMA", "justificacao_rgpd": str(response_data)}
            
    except requests.exceptions.HTTPError as http_err:
        print(f"{log_prefix} ERRO HTTP (chat): {http_err}. Resposta: {response_text_for_log_on_error[:300]}...")
        analysis_result = {"sensibilidade_rgpd": "ERRO_HTTP_OLLAMA_CHAT", "justificacao_rgpd": response_text_for_log_on_error, "status_code": http_err.response.status_code if http_err.response else "N/A"}
    # ... (outros blocos except como antes, ajustando a mensagem para indicar "_CHAT") ...
    except requests.exceptions.Timeout:
        print(f"{log_prefix} ERRO: Timeout ({OLLAMA_REQUEST_TIMEOUT}s) (chat).")
        analysis_result = {"sensibilidade_rgpd": "ERRO_TIMEOUT_OLLAMA_CHAT", "justificacao_rgpd": f"Timeout de {OLLAMA_REQUEST_TIMEOUT}s"}
    except requests.exceptions.RequestException as req_err:
        print(f"{log_prefix} ERRO DE REQUESTS (chat): {req_err}")
        analysis_result = {"sensibilidade_rgpd": "ERRO_REQUESTS_OLLAMA_CHAT", "justificacao_rgpd": str(req_err)}
    except json.JSONDecodeError as json_err: # Se response.json() falhar
        print(f"{log_prefix} ERRO DE DECODIFICAÇÃO JSON (resposta principal chat): {json_err}. Resposta: {response_text_for_log_on_error[:300]}...")
        analysis_result = {"sensibilidade_rgpd": "ERRO_DECODE_JSON_RESPOSTA_PRINCIPAL_CHAT", "justificacao_rgpd": response_text_for_log_on_error, "exception": str(json_err)}
    except Exception as ex:
        print(f"{log_prefix} ERRO CRÍTICO INESPERADO (chat): {ex}")
        # print(traceback.format_exc()) 
        analysis_result = {"sensibilidade_rgpd": "ERRO_INESPERADO_GERAL_OLLAMA_CHAT", "justificacao_rgpd": str(ex)}
    
    print(f"{log_prefix} Resultado: Sensibilidade='{analysis_result.get('sensibilidade_rgpd', 'N/A')}'")
    return analysis_result