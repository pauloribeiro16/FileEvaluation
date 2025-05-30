import json
import os

def load_schema(filepath):
    """Carrega um esquema JSON de um ficheiro."""
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

def extract_schema_metadata(schema_data):
    """Extrai metadados de alto nível de um esquema."""
    if not isinstance(schema_data, dict):
        return {"title": "N/A", "description": "N/A", "top_properties": []}
    
    title = schema_data.get("title", "Sem Título")
    description = schema_data.get("description", "Sem Descrição")
    top_properties = []
    if "properties" in schema_data and isinstance(schema_data["properties"], dict):
        top_properties = list(schema_data["properties"].keys())
    return {"title": title, "description": description, "top_properties": top_properties}


def extract_all_properties_with_descriptions(schema_data, current_path_parts=None, descriptions_map=None, filename_context=""):
    """
    Extrai todas as propriedades com suas descrições de um esquema JSON.
    Retorna um dicionário onde a chave é 'filename::path.to.property' e o valor é a descrição.
    """
    if current_path_parts is None: current_path_parts = []
    if descriptions_map is None: descriptions_map = {}

    if isinstance(schema_data, dict):
        for key, value in schema_data.items():
            # Não adicionar o próprio 'properties' ao caminho se for o primeiro nível de current_path_parts
            # ou se current_path_parts estiver vazio e key for 'properties'.
            # Queremos caminhos como 'properties.user.name', não 'properties.properties.user.name'.
            
            # Evitar caminhos internos como 'properties.user.type'
            if key.startswith("$") or key in ["type", "format", "enum", "pattern", "minLength", "maxLength", "required", "default"]:
                 continue # Pula chaves de metadados do JSON schema dentro de uma propriedade

            new_path_parts = current_path_parts + [str(key)]

            if key == "properties" and isinstance(value, dict):
                # Estamos dentro de um bloco 'properties', então os próximos níveis são nomes de propriedades reais
                for prop_name, prop_schema in value.items():
                    # O caminho da propriedade começa a partir do 'properties'
                    # Se current_path_parts já é ['properties'], então prop_path_parts será ['properties', prop_name]
                    # Se current_path_parts é [], e key é 'properties', então new_path_parts é ['properties']
                    # e prop_path_parts será ['properties', prop_name]
                    
                    # A lógica aqui é que `current_path_parts` ao entrar nesta função
                    # para um sub-esquema (ex: dentro de allOf ou items) já pode conter 'properties'.
                    # Se current_path_parts está vazio, e entramos pela primeira vez em 'properties',
                    # o caminho da propriedade será 'properties.prop_name'.
                    
                    # Caminho para esta propriedade específica
                    actual_prop_path_parts = current_path_parts + [key, prop_name] if current_path_parts and current_path_parts[-1] != key else [key, prop_name]
                    if not current_path_parts and key == "properties": # Caso raiz
                        actual_prop_path_parts = [key, prop_name]


                    prop_full_path_str = ".".join(actual_prop_path_parts)
                    unique_key_for_map = f"{filename_context}::{prop_full_path_str}"

                    if isinstance(prop_schema, dict) and "description" in prop_schema:
                        desc_text = prop_schema["description"]
                        if desc_text and len(desc_text.strip()) >= 5: # Apenas descrições significativas
                             descriptions_map[unique_key_for_map] = desc_text
                    
                    # Recursão para propriedades aninhadas (ex: objeto dentro de objeto)
                    # O novo `current_path_parts` para a recursão é `actual_prop_path_parts`
                    extract_all_properties_with_descriptions(prop_schema, actual_prop_path_parts, descriptions_map, filename_context)

            elif key == "allOf" and isinstance(value, list):
                for item_schema in value:
                    # Para allOf, continuamos com o mesmo current_path_parts, pois as propriedades
                    # dos itens de allOf são "misturadas" no nível atual.
                    extract_all_properties_with_descriptions(item_schema, list(current_path_parts), descriptions_map, filename_context)
            
            elif key == "items" and isinstance(value, dict):
                # Para items (descrevendo objetos num array), o `new_path_parts` (que inclui 'items')
                # torna-se o `current_path_parts` para a recursão.
                # Propriedades dentro de 'items.properties' terão caminhos como 'path.to.array.items.properties.child_prop'
                extract_all_properties_with_descriptions(value, new_path_parts, descriptions_map, filename_context)
    return descriptions_map


def flatten_schema_for_excel(schema_data, current_keys=None, collected_rows=None):
    """Achatamento do esquema para exibição no Excel (semelhante ao anterior)."""
    if current_keys is None: current_keys = []
    if collected_rows is None: collected_rows = []

    if isinstance(schema_data, dict):
        if not schema_data: return
        for key, value in schema_data.items():
            flatten_schema_for_excel(value, current_keys + [str(key)], collected_rows)
    elif isinstance(schema_data, list):
        if not schema_data: return
        for item in schema_data: # Não adicionar índice da lista ao caminho de chave do esquema
            flatten_schema_for_excel(item, list(current_keys), collected_rows)
    else:
        collected_rows.append({'keys': list(current_keys), 'value': schema_data})
    return collected_rows