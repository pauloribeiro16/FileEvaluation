# src/schema_parser.py
import json
import os

def load_schema(filepath):
    # ... (como antes) ...
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[SCHEMA_PARSER ERRO] Ficheiro de esquema não encontrado: {filepath}")
    except json.JSONDecodeError as e:
        print(f"[SCHEMA_PARSER ERRO] Erro ao decodificar JSON em {filepath}: {e}")
    except Exception as e:
        print(f"[SCHEMA_PARSER ERRO] Erro inesperado ao carregar {filepath}: {e}")
    return None


def _extract_properties_recursive(schema_data, current_path_parts, properties_map, filename_context):
    """Função auxiliar recursiva para extract_all_properties_with_descriptions."""
    if not isinstance(schema_data, dict):
        return

    if "properties" in schema_data and isinstance(schema_data["properties"], dict):
        base_path_for_props = current_path_parts + ["properties"]
        for prop_name, prop_schema in schema_data["properties"].items():
            prop_path_parts = base_path_for_props + [prop_name]
            prop_full_path_str = ".".join(prop_path_parts)
            unique_key_for_map = f"{filename_context}::{prop_full_path_str}"

            description_text = ""
            if isinstance(prop_schema, dict) and "description" in prop_schema:
                description_text = prop_schema["description"]
            
            # Adiciona a propriedade ao mapa se tiver descrição (o filtro de relevância é feito depois)
            properties_map[unique_key_for_map] = description_text
            
            if isinstance(prop_schema, dict):
                _extract_properties_recursive(prop_schema, prop_path_parts, properties_map, filename_context)
    
    if "allOf" in schema_data and isinstance(schema_data["allOf"], list):
        for item_schema in schema_data["allOf"]:
            _extract_properties_recursive(item_schema, list(current_path_parts), properties_map, filename_context)
    
    if "items" in schema_data and isinstance(schema_data["items"], dict):
        _extract_properties_recursive(schema_data["items"], current_path_parts + ["items"], properties_map, filename_context)


def extract_all_properties_with_descriptions(schema_data, filename_context):
    """
    Extrai todas as propriedades com suas descrições de um esquema JSON.
    A chave do mapa retornado é 'filename::path.to.property'.
    """
    properties_map = {}
    _extract_properties_recursive(schema_data, [], properties_map, filename_context)
    return properties_map


def flatten_schema_for_excel(schema_data, current_keys=None, collected_rows=None):
    # ... (como antes) ...
    if current_keys is None: current_keys = []
    if collected_rows is None: collected_rows = []

    if isinstance(schema_data, dict):
        if not schema_data: return collected_rows # Retornar a lista
        for key, value in schema_data.items():
            flatten_schema_for_excel(value, current_keys + [str(key)], collected_rows)
    elif isinstance(schema_data, list):
        if not schema_data: return collected_rows
        for item in schema_data:
             flatten_schema_for_excel(item, list(current_keys), collected_rows)
    else:
        collected_rows.append({'keys': list(current_keys), 'value': schema_data})
    return collected_rows