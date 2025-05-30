import json
import requests
import time
import utils # Para carregar prompts

# --- Configurações do Ollama ---
OLLAMA_ENDPOINT = "http://localhost:11434/api/generate" # Ou /api/chat se preferir
OLLAMA_MODEL = "llama3.1:latest"
OLLAMA_REQUEST_TIMEOUT = 240 # Aumentado, análise de lote pode demorar

def ollama_api_request(payload, request_type_log=""):
    """Função genérica para fazer pedidos à API Ollama e tratar respostas."""
    analysis_result = {"error": f"Análise Ollama ({request_type_log}) não concluída."} 
    log_prefix = f"[OLLAMA API {request_type_log.upper()}]"
    try:
        print(f"{log_prefix} Enviando pedido...")
        # print(f"{log_prefix} Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}") # Descomente para depuração profunda
        response = requests.post(OLLAMA_ENDPOINT, json=payload, timeout=OLLAMA_REQUEST_TIMEOUT)
        print(f"{log_prefix} Resposta recebida. Status: {response.status_code}")
        # print(f"{log_prefix} Conteúdo bruto: {response.text[:500]}...") # Descomente para depuração profunda
        response.raise_for_status()
        response_data = response.json()

        if "response" in response_data: # 'response' contém a string JSON da resposta do modelo
            analysis_json_str = response_data["response"]
            try:
                analysis_result = json.loads(analysis_json_str)
            except json.JSONDecodeError as je:
                print(f"{log_prefix} ERRO CRÍTICO: Falha ao decodificar JSON da string de resposta: {analysis_json_str} - Erro: {je}")
                analysis_result = {"error": "ERRO_DECODE_OLLAMA", "details": analysis_json_str}
        elif "error" in response_data: # Erro retornado pela API do Ollama
            print(f"{log_prefix} ERRO retornado por Ollama: {response_data['error']}")
            analysis_result = {"error": "ERRO_API_OLLAMA", "details": response_data['error']}
        else: # Resposta inesperada da API
            print(f"{log_prefix} ERRO: Chave 'response' ou 'error' não encontrada na resposta: {response_data}")
            analysis_result = {"error": "ERRO_NO_RESPONSE_OLLAMA", "details": str(response_data)}
            
    except requests.exceptions.Timeout:
        print(f"{log_prefix} ERRO: Timeout ({OLLAMA_REQUEST_TIMEOUT}s) ao comunicar com Ollama.")
        analysis_result = {"error": "ERRO_TIMEOUT_OLLAMA"}
    except requests.exceptions.RequestException as e:
        print(f"{log_prefix} ERRO CRÍTICO de comunicação com Ollama: {e}")
        analysis_result = {"error": "ERRO_COMUNICACAO_OLLAMA", "details": str(e)}
    except Exception as ex:
        print(f"{log_prefix} ERRO CRÍTICO inesperado: {ex}")
        analysis_result = {"error": "ERRO_INESPERADO_OLLAMA", "details": str(ex)}
    
    print(f"{log_prefix} Resultado da análise (ou erro): {str(analysis_result)[:200]}...")
    return analysis_result


def analyze_document_summary_with_ollama(filename, schema_title, schema_description, top_properties_list):
    """Analisa o sumário de um documento/esquema com Ollama."""
    print(f"-- [OLLAMA DOC] Iniciando análise de sumário para: {filename} --")
    prompt_template = utils.load_prompt_template("rgpd_document_assessment_prompt.txt")
    if not prompt_template:
        return {"error": "Template de prompt de documento não encontrado."}

    prompt_text = prompt_template.format(
        filename=filename,
        schema_title=schema_title,
        schema_description=schema_description[:1000], # Limitar tamanho da descrição
        top_level_properties_summary=", ".join(top_properties_list[:20]) # Limitar número de props
    )
    payload = {"model": OLLAMA_MODEL, "prompt": prompt_text, "stream": False, "format": "json"}
    result = ollama_api_request(payload, request_type_log=f"DOC_SUMMARY_{filename}")
    print(f"-- [OLLAMA DOC] Fim da análise de sumário para: {filename} --")
    return result


def analyze_field_batch_with_ollama(fields_batch):
    """
    Analisa um lote de campos com Ollama.
    fields_batch: lista de dicts, cada dict com {'caminho_completo_chave': str, 'descricao': str}
    """
    if not fields_batch:
        return []
        
    batch_identifier = fields_batch[0]['caminho_completo_chave'].split("::")[0] # Pega o nome do ficheiro do primeiro item para log
    print(f"-- [OLLAMA BATCH] Iniciando análise de lote (contexto aprox.: {batch_identifier}, {len(fields_batch)} campos) --")
    
    prompt_template = utils.load_prompt_template("rgpd_field_batch_assessment_prompt.txt")
    if not prompt_template:
        return [{"error": "Template de prompt de lote não encontrado."}] * len(fields_batch)

    # Formatar a lista de campos para o placeholder {campos_json_lista_string}
    # Cada campo precisa ter: caminho_completo_chave, nome_final_chave, descricao_chave, contexto_ficheiro
    campos_para_prompt_list = []
    for field_data in fields_batch:
        path_parts = field_data['caminho_completo_chave'].split("::")[-1].split('.')
        nome_final_chave = path_parts[-1]
        contexto_ficheiro = field_data['caminho_completo_chave'].split("::")[0]
        campos_para_prompt_list.append({
            "caminho_completo_chave": field_data['caminho_completo_chave'], # Este é o ID que queremos de volta
            "nome_final_chave": nome_final_chave,
            "descricao_chave": field_data['descricao'][:500], # Limitar tamanho
            "contexto_ficheiro": contexto_ficheiro
        })
    
    campos_json_lista_string = json.dumps(campos_para_prompt_list, indent=2, ensure_ascii=False)

    prompt_text = prompt_template.replace("{campos_json_lista_string}", campos_json_lista_string)
    # print(f"[OLLAMA BATCH DEBUG] Prompt Lote:\n{prompt_text}") # Descomente para depuração

    payload = {"model": OLLAMA_MODEL, "prompt": prompt_text, "stream": False, "format": "json"}
    
    results = ollama_api_request(payload, request_type_log=f"FIELD_BATCH_{batch_identifier}")

    # A API retorna uma lista de resultados se o prompt for bem sucedido
    if isinstance(results, list):
        print(f"-- [OLLAMA BATCH] Fim da análise de lote. {len(results)} resultados recebidos. --")
        return results
    else: # Se houve um erro geral na chamada da API, retorna uma lista de erros
        print(f"-- [OLLAMA BATCH] Fim da análise de lote. Erro geral na API: {results.get('error', 'Desconhecido')} --")
        return [{"caminho_completo_chave_analisada": field['caminho_completo_chave'], 
                   "sensibilidade_rgpd": results.get('error', "ERRO_LOTE_OLLAMA"), 
                   "justificacao_rgpd": results.get('details', "Falha na análise do lote.")} 
                  for field in fields_batch]