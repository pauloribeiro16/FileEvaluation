import json
import os

OLLAMA_ANALYSIS_CACHE_FILE = "ollama_analysis_cache.json" # Relativo ao diretório de execução do main.py

def load_prompt_template(prompt_filename):
    """Carrega um template de prompt de um ficheiro."""
    # Assume que a diretoria 'prompts' está um nível acima de 'src'
    # ou ao mesmo nível do script principal que chama esta função.
    # Para ser mais robusto, podemos usar o caminho do script atual.
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Vai para o diretório do projeto
    prompts_dir = os.path.join(script_dir, "prompts")
    filepath = os.path.join(prompts_dir, prompt_filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"[UTILS ERRO] Ficheiro de prompt não encontrado: {filepath}")
        return None
    except Exception as e:
        print(f"[UTILS ERRO] Erro ao carregar prompt de {filepath}: {e}")
        return None

def load_ollama_cache():
    """Carrega o cache de análise do Ollama do disco."""
    # O caminho do cache será relativo ao local de execução do main.py
    cache_path = OLLAMA_ANALYSIS_CACHE_FILE
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
    """Salva o cache de análise do Ollama no disco."""
    cache_path = OLLAMA_ANALYSIS_CACHE_FILE
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        # print(f"[CACHE INFO] Cache Ollama salvo em {cache_path} com {len(cache_data)} entradas.") # Pode ser verboso para cada save
    except Exception as e:
        print(f"[CACHE ERRO] Erro ao salvar cache Ollama em {cache_path}: {e}")