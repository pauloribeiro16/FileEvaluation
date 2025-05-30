import json
import os

# O caminho do cache será relativo ao local de execução do main.py (raiz do projeto)
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
    except Exception as e:
        print(f"[UTILS ERRO] Erro ao carregar prompt de {filepath}: {e}")
        return None

def load_ollama_cache():
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
    cache_path = OLLAMA_ANALYSIS_CACHE_FILE
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        # print(f"[CACHE INFO] Cache Ollama salvo em {cache_path} com {len(cache_data)} entradas.")
    except Exception as e:
        print(f"[CACHE ERRO] Erro ao salvar cache Ollama em {cache_path}: {e}")