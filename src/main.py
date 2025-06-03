# src/main.py
import os
import json
import pandas as pd
import time

import utils
import schema_parser
import ollama_analyzer # Já importa as constantes do ollama_analyzer
import excel_writer

# --- Configurações Globais ---
PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_FILES_DIR_CONFIG = os.path.join(PROJECT_ROOT_DIR, "JSONFiles")
# OUTPUT_EXCEL_FILENAME_CONFIG será definido dinamicamente

# Remover PROPERTIES_TO_SKIP_ANALYSIS, pois não vamos mais filtrar antes do LLM
# PROPERTIES_TO_SKIP_ANALYSIS = [...] 

def _collect_properties_for_analysis(json_files_dir):
    """
    Phase 1: Loads schemas, extracts all properties with descriptions.
    No pre-filtering here; LLM should assess everything.
    Returns:
        all_properties_to_analyze (dict): {unique_key: description} for analysis.
        all_files_parsed_data (dict): {filename: {'schema_data': ..., 'collected_rows_for_excel': ...}}
    """
    print("\n--- PHASE 1: Collecting All Properties with Descriptions ---")
    # ... (lógica interna como em _collect_all_properties da resposta anterior)
    all_properties_to_analyze = {} 
    all_files_parsed_data = {} 

    if not os.path.exists(json_files_dir):
        print(f"[PHASE 1 ERROR] JSONs directory not found: {json_files_dir}")
        return None, None
        
    json_files_list = [f for f in os.listdir(json_files_dir) if f.endswith(".json")]
    if not json_files_list:
        print(f"[PHASE 1 ERROR] No .json files found in {json_files_dir}")
        return None, None

    for filename in json_files_list:
        print(f"  [Phase 1] Processing file for collection: {filename}")
        filepath = os.path.join(json_files_dir, filename)
        schema_data = schema_parser.load_schema(filepath)
        
        if not schema_data:
            all_files_parsed_data[filename] = {'error': "Failed to load schema."}
            continue

        all_files_parsed_data[filename] = {
            'schema_data': schema_data,
            'collected_rows_for_excel': schema_parser.flatten_schema_for_excel(schema_data)
        }
        
        file_properties_with_desc = schema_parser.extract_all_properties_with_descriptions(
            schema_data, filename_context=filename
        )
        
        for unique_key, description_text in file_properties_with_desc.items():
             all_properties_to_analyze[unique_key] = description_text if description_text else ""

        print(f"    [Phase 1] {filename}: {len(file_properties_with_desc)} properties with description found (to be sent to LLM).")

    print(f"--- PHASE 1 COMPLETED. {len(all_properties_to_analyze)} unique properties with descriptions for PII analysis. ---")
    return all_properties_to_analyze, all_files_parsed_data


def _run_ollama_analysis_phase(properties_map_to_analyze, ollama_cache):
    """
    Phase 2: Sends properties for Ollama analysis, using and updating the cache.
    Returns: updated ollama_cache.
    """
    print("\n--- PHASE 2: Detailed Field Analysis with Ollama and Cache ---")
    # ... (lógica como antes, mas chamando ollama_analyzer.analyze_single_field_ollama) ...
    # ... (e usando as chaves de resultado em inglês: pii_sensitivity_assessment, gdpr_justification) ...
    properties_to_send_to_ollama = []
    for unique_key, description in properties_map_to_analyze.items():
        if unique_key not in ollama_cache:
            properties_to_send_to_ollama.append({"unique_key": unique_key, "description": description})

    total_new_to_analyze = len(properties_to_send_to_ollama)
    print(f"  [Phase 2] {total_new_to_analyze} new properties for Ollama (total unique candidates: {len(properties_map_to_analyze)}, already cached: {len(ollama_cache)}).")

    if total_new_to_analyze == 0 and ollama_cache:
        print("  [Phase 2] No new properties to analyze. Using existing cache.")
        return ollama_cache
    elif total_new_to_analyze == 0 and not ollama_cache:
        print("  [Phase 2] No properties to analyze and cache is empty. Ollama analysis skipped.")
        return ollama_cache

    newly_analyzed_this_run = 0
    for idx, field_to_analyze in enumerate(properties_to_send_to_ollama):
        unique_key = field_to_analyze["unique_key"]
        description = field_to_analyze["description"]
        
        time.sleep(0.2) 
        
        analysis_result = ollama_analyzer.analyze_single_field_ollama( # Nome da função atualizado
            unique_key, 
            description,
            current_count=idx + 1,
            total_count=total_new_to_analyze
        )
        ollama_cache[unique_key] = analysis_result 
        newly_analyzed_this_run +=1

        if newly_analyzed_this_run > 0 and newly_analyzed_this_run % 5 == 0 :
            print(f"    [Phase 2 CACHE] Saving Ollama cache with {len(ollama_cache)} entries...")
            utils.save_ollama_cache(ollama_cache)
            if newly_analyzed_this_run % 10 == 0: 
                print(f"    [Phase 2 DELAY] Pausing for 1 second...")
                time.sleep(1.0)
    
    if newly_analyzed_this_run > 0 :
         print(f"  [Phase 2 CACHE] Saving final Ollama cache with {len(ollama_cache)} entries...")
         utils.save_ollama_cache(ollama_cache)

    print(f"--- PHASE 2 COMPLETED. Ollama cache now has {len(ollama_cache)} total entries. ---")
    return ollama_cache


def run_pipeline():
    print("--- STARTING JSON SCHEMA ANALYSIS PIPELINE (Refactored v3 - English) ---")
    utils.clear_ollama_cache()

    model_name_cleaned = ollama_analyzer.OLLAMA_MODEL.replace(":", "_").replace("/", "_")
    output_excel_filename_dynamic = os.path.join(PROJECT_ROOT_DIR, f"Analysis_Report_{model_name_cleaned}.xlsx")
    print(f"[INFO] Output Excel file will be: {output_excel_filename_dynamic}")

    # Phase 1
    unique_properties_for_ollama, parsed_files_data = _collect_properties_for_analysis(JSON_FILES_DIR_CONFIG)
    if unique_properties_for_ollama is None:
        print("Pipeline aborted due to error in property collection.")
        return
    if not unique_properties_for_ollama:
        print("[INFO] No properties with descriptions found to send to Ollama.")

    # Phase 2
    current_ollama_cache = utils.load_ollama_cache() # Should be empty due to clear_ollama_cache()
    updated_ollama_cache = _run_ollama_analysis_phase(unique_properties_for_ollama, current_ollama_cache)

    # Phase 3
    excel_writer.generate_excel_report(
        output_excel_filename_dynamic,
        parsed_files_data, 
        updated_ollama_cache,
        unique_properties_for_ollama # Pass this for original descriptions in summary
    )
            
    print(f"--- PIPELINE COMPLETED. Results in: {output_excel_filename_dynamic} ---")

if __name__ == "__main__":
    run_pipeline()