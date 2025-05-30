import json
import os

def load_schema(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[SCHEMA_PARSER ERRO] Ficheiro de esquema não encontrado: {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"[SCHEMA_PARSER ERRO] Erro ao decodificar JSON em {filepath}: {e}")
        return None
    except Exception as e:
        print(f"[SCHEMA_PARSER ERRO] Erro inesperado ao carregar {filepath}: {e}")
        return None

def extract_all_properties_with_descriptions(schema_data, current_path_parts=None, properties_map=None, filename_context=""):
    """
    Extrai todas as propriedades com suas descrições de um esquema JSON.
    Retorna um dicionário onde a chave é 'filename::path.to.property' e o valor é a descrição.
    Foca em propriedades dentro de 'properties' e 'items.properties'.
    """
    if current_path_parts is None: current_path_parts = []
    if properties_map is None: properties_map = {}

    if isinstance(schema_data, dict):
        # Caso 1: Estamos num objeto que contém uma chave "properties"
        if "properties" in schema_data and isinstance(schema_data["properties"], dict):
            # O caminho para as propriedades filhas incluirá "properties"
            # Se current_path_parts já é ['path','to','object'], new_base_path será ['path','to','object','properties']
            new_base_path_for_props = current_path_parts + ["properties"]
            for prop_name, prop_schema in schema_data["properties"].items():
                prop_path_parts = new_base_path_for_props + [prop_name]
                prop_full_path_str = ".".join(prop_path_parts)
                unique_key_for_map = f"{filename_context}::{prop_full_path_str}"

                description_text = ""
                if isinstance(prop_schema, dict) and "description" in prop_schema:
                    description_text = prop_schema["description"]
                
                # Adicionar mesmo se a descrição for curta/vazia, o filtro pode ser feito depois
                # Mas é melhor filtrar aqui se a descrição é essencial para a análise Ollama
                if description_text and len(description_text.strip()) >= 1: # Descrição mínima
                    properties_map[unique_key_for_map] = description_text
                
                # Recursão para propriedades aninhadas (ex: objeto dentro de objeto)
                # O novo `current_path_parts` para a recursão é `prop_path_parts`
                if isinstance(prop_schema, dict): # Apenas recursar se prop_schema for um dict
                    extract_all_properties_with_descriptions(prop_schema, prop_path_parts, properties_map, filename_context)
        
        # Caso 2: Estamos num objeto que representa um item de array e contém "properties"
        # (geralmente current_path_parts já terminaria com "items")
        # Esta lógica é coberta pela recursão geral se 'items' tiver 'properties'

        # Caso 3: allOf - processar cada sub-esquema
        if "allOf" in schema_data and isinstance(schema_data["allOf"], list):
            for item_schema in schema_data["allOf"]:
                # Para allOf, continuamos com o mesmo current_path_parts, pois as propriedades
                # dos itens de allOf são "misturadas" no nível atual.
                extract_all_properties_with_descriptions(item_schema, list(current_path_parts), properties_map, filename_context)
        
        # Caso 4: items (descrevendo objetos num array)
        if "items" in schema_data and isinstance(schema_data["items"], dict):
            # O `current_path_parts` para a recursão em `items` será `current_path_parts + ['items']`
            extract_all_properties_with_descriptions(schema_data["items"], current_path_parts + ["items"], properties_map, filename_context)

    return properties_map


def flatten_schema_for_excel(schema_data, current_keys=None, collected_rows=None):
    if current_keys is None: current_keys = []
    if collected_rows is None: collected_rows = []

    if isinstance(schema_data, dict):
        if not schema_data: return
        for key, value in schema_data.items():
            flatten_schema_for_excel(value, current_keys + [str(key)], collected_rows)
    elif isinstance(schema_data, list):
        if not schema_data: return
        # Para listas no esquema (ex: enum, required), não queremos iterar e criar múltiplas entradas de caminho
        # A menos que seja uma lista de sub-esquemas (allOf, anyOf, oneOf - já tratados)
        # Por simplicidade, vamos representar a lista como um valor.
        # Ou, se for uma lista de escalares (ex: enum: ["A", "B"]), o 'value' será a lista.
        # A lógica anterior de apenas chamar recursivamente para cada item pode ser melhor para 'allOf'.
        # Vamos manter a lógica anterior:
        for item_index, item in enumerate(schema_data): # Adicionar índice para diferenciar itens de lista
             # Poderíamos adicionar o índice ao caminho se fosse importante, ex: current_keys + [f"[{item_index}]"]
             # Mas para esquemas, geralmente não queremos isso no caminho da chave.
             flatten_schema_for_excel(item, list(current_keys), collected_rows) # Sem índice no caminho por agora
    else:
        collected_rows.append({'keys': list(current_keys), 'value': schema_data})
    return collected_rows