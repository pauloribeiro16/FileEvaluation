import os
import json
import pandas as pd
import time

import utils
import schema_parser
import ollama_analyzer
import excel_writer

# --- Configurações Globais ---
PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_FILES_DIR = os.path.join(PROJECT_ROOT_DIR, "JSONFiles")
OUTPUT_EXCEL_FILENAME = os.path.join(PROJECT_ROOT_DIR, "Relatorio_Final_Modular.xlsx")

def run_analysis_pipeline():
    print("--- INICIANDO PIPELINE DE ANÁLISE DE ESQUEMAS JSON ---")

    # --- Fase 1: Coleta de Propriedades Únicas ---
    print("\n--- FASE 1: Coleta de Propriedades Únicas ---")
    all_unique_properties_to_analyze = {} 
    all_files_parsed_data = {} 

    if not os.path.exists(JSON_FILES_DIR):
        print(f"[FASE 1 ERRO] Diretório de JSONs não encontrado: {JSON_FILES_DIR}")
        return
        
    json_files = [f for f in os.listdir(JSON_FILES_DIR) if f.endswith(".json")]
    if not json_files:
        print(f"[FASE 1 ERRO] Nenhum ficheiro .json encontrado em {JSON_FILES_DIR}")
        return

    for filename in json_files:
        print(f"  [Fase 1] Processando ficheiro: {filename}") # Log do ficheiro
        filepath = os.path.join(JSON_FILES_DIR, filename)
        schema_data = schema_parser.load_schema(filepath)
        
        if not schema_data:
            all_files_parsed_data[filename] = {'error': "Falha ao carregar esquema."}
            continue

        all_files_parsed_data[filename] = {
            'schema_data': schema_data,
            'collected_rows_for_excel': schema_parser.flatten_schema_for_excel(schema_data)
        }
        file_properties_with_desc = schema_parser.extract_all_properties_with_descriptions(
            schema_data, filename_context=filename
        )
        all_unique_properties_to_analyze.update(file_properties_with_desc)
        # print(f"    [Fase 1] {len(file_properties_with_desc)} propriedades com descrição encontradas em {filename}.") # Pode ser verboso

    print(f"--- FASE 1 CONCLUÍDA. {len(all_unique_properties_to_analyze)} propriedades únicas para análise. ---")
    
    # --- Fase 2: Análise com Ollama e Cache ---
    print("\n--- FASE 2: Análise Detalhada de Campos com Ollama e Cache ---")
    ollama_cache = utils.load_ollama_cache()
    
    newly_analyzed_count = 0
    properties_to_send_to_ollama = []
    for unique_key, description in all_unique_properties_to_analyze.items():
        if unique_key not in ollama_cache:
            properties_to_send_to_ollama.append({"unique_key": unique_key, "description": description})

    total_new_to_analyze = len(properties_to_send_to_ollama)
    print(f"  [Fase 2] {total_new_to_analyze} novas propriedades para Ollama (total únicas: {len(all_unique_properties_to_analyze)}, Cached: {len(ollama_cache)}).")

    for idx, field_to_analyze in enumerate(properties_to_send_to_ollama):
        unique_key = field_to_analyze["unique_key"]
        description = field_to_analyze["description"]
            
        # Log da propriedade sendo analisada (já está no início de analyze_single_field_with_ollama)
        # print(f"  [Fase 2] Analisando nova propriedade {idx + 1}/{total_new_to_analyze}: {unique_key}") 
        time.sleep(0.2) # Reduzido o delay, ajuste se o Ollama sobrecarregar
        
        analysis_result = ollama_analyzer.analyze_single_field_with_ollama_chat(unique_key, description) # CHAMAR A NOVA FUNÇÃO
        ollama_cache[unique_key] = analysis_result
        newly_analyzed_count +=1

        if newly_analyzed_count > 0 and newly_analyzed_count % 10 == 0 : # Salvar a cada X análises
            print(f"    [Fase 2] Salvando cache Ollama com {len(ollama_cache)} entradas...")
            utils.save_ollama_cache(ollama_cache)
            # if newly_analyzed_count % 20 == 0: # Pausa maior menos frequente
            #     print(f"    [Fase 2] Pausando por 1 segundo após {newly_analyzed_count} análises...")
            #     time.sleep(1.0)
    
    if newly_analyzed_count > 0 : 
         print(f"  [Fase 2] Salvando cache Ollama final com {len(ollama_cache)} entradas...")
         utils.save_ollama_cache(ollama_cache)

    print(f"--- FASE 2 CONCLUÍDA. Cache com {len(ollama_cache)} entradas. ---")

    # --- Fase 3: Geração do Relatório Excel ---
    print("\n--- FASE 3: Geração do Relatório Excel ---")
    with pd.ExcelWriter(OUTPUT_EXCEL_FILENAME, engine='xlsxwriter') as writer:
        for filename, file_data in all_files_parsed_data.items():
            sheet_name = os.path.splitext(filename)[0][:31]
            print(f"  [Fase 3] Preparando folha Excel: '{sheet_name}'") # Log da folha

            if 'error' in file_data:
                # ... (tratamento de erro como antes) ...
                continue
            # ... (resto da lógica da Fase 3 como antes, os prints lá são geralmente informativos e não excessivamente verbosos) ...
            collected_rows = file_data['collected_rows_for_excel']
            if not collected_rows:
                print(f"    [Fase 3] Nenhum dado de esquema achatado para exibir em {filename}.")
                empty_df = pd.DataFrame([{"Info": f"Esquema {filename} sem dados para exibir."}], columns=["Info"])
                empty_df.to_excel(writer, sheet_name=sheet_name, index=False)
                excel_writer.apply_styles_merge_and_highlight(writer, empty_df, sheet_name, {})
                continue

            max_cols = max(len(row['keys']) for row in collected_rows) + 1 if collected_rows else 1
            excel_df_data = []
            cell_highlights = {}

            for df_row_idx, row_dict in enumerate(collected_rows):
                excel_row_list = list(row_dict['keys'])
                excel_row_list.append(row_dict['value'])
                excel_row_list.extend([None] * (max_cols - len(excel_row_list)))
                excel_df_data.append(excel_row_list)

                current_row_path_parts = row_dict['keys']
                analysis_for_this_excel_row = None
                property_path_that_matched_excel_row = None

                for i in range(len(current_row_path_parts), 0, -1):
                    potential_schema_prop_path = ".".join(current_row_path_parts[:i])
                    unique_key_for_cache_lookup = f"{filename}::{potential_schema_prop_path}"
                    
                    if unique_key_for_cache_lookup in ollama_cache:
                        analysis_for_this_excel_row = ollama_cache[unique_key_for_cache_lookup]
                        property_path_that_matched_excel_row = potential_schema_prop_path
                        break
                
                if analysis_for_this_excel_row:
                    sensibilidade = analysis_for_this_excel_row.get("sensibilidade_rgpd")
                    color_to_apply = None
                    if sensibilidade in ["DADO_PESSOAL_ALTA_SENSIBILIDADE", "DADO_SAUDE_ESPECIFICO", "LOCALIZACAO_SENSIVEL"]: 
                        color_to_apply = '#FFC7CE' 
                    elif sensibilidade in ["DADO_PESSOAL_MEDIA_SENSIBILIDADE", "DADO_FINANCEIRO_SENSIVEL", "OUTRO_DADO_SENSIVEL"]:
                        color_to_apply = '#FFEB9C'

                    if color_to_apply and property_path_that_matched_excel_row:
                        num_parts_in_matched_prop_path = len(property_path_that_matched_excel_row.split('.'))
                        for col_idx_excel in range(num_parts_in_matched_prop_path):
                            if col_idx_excel < len(excel_row_list) and excel_row_list[col_idx_excel] == property_path_that_matched_excel_row.split('.')[col_idx_excel]:
                                cell_highlights[(df_row_idx + 1, col_idx_excel)] = color_to_apply
                        if ".".join(current_row_path_parts) == property_path_that_matched_excel_row:
                            value_col_idx = len(current_row_path_parts)
                            if value_col_idx < max_cols :
                                cell_highlights[(df_row_idx + 1, value_col_idx)] = color_to_apply
            
            column_names_excel = [f"Nível {i+1}" for i in range(max_cols -1)] + ["Valor Atributo Esquema"]
            df_excel = pd.DataFrame(excel_df_data, columns=column_names_excel)
            df_excel.to_excel(writer, sheet_name=sheet_name, index=False, header=True)
            excel_writer.apply_styles_merge_and_highlight(writer, df_excel, sheet_name, cell_highlights)
            # print(f"    [Fase 3] Folha Excel '{sheet_name}' gerada.") # Já temos o log no início da iteração

        # Gerar folha de sumário
        summary_data_list = []
        if ollama_cache:
            for unique_key, analysis_data in ollama_cache.items():
                sens_rgpd = analysis_data.get("sensibilidade_rgpd", "N/A")
                if sens_rgpd not in [None, "NAO_DADO_PESSOAL"] and not sens_rgpd.startswith("ERRO_"):
                    filename_ctx, path_str_ctx = unique_key.split("::", 1)
                    original_description = all_unique_properties_to_analyze.get(unique_key, "Descrição não encontrada na coleta inicial.")
                    summary_data_list.append({
                        "Ficheiro de Origem": filename_ctx,
                        "Caminho da Chave no Esquema": path_str_ctx,
                        "Descrição Original": original_description,
                        "Classificação RGPD (Ollama)": sens_rgpd,
                        "Justificação (Ollama)": analysis_data.get("justificacao_rgpd", "N/A")
                    })
        
        if summary_data_list:
            summary_df_final = pd.DataFrame(summary_data_list)
            summary_sheet_name_final = "Sumario Sensibilidade RGPD"
            summary_df_final.to_excel(writer, sheet_name=summary_sheet_name_final, index=False)
            excel_writer.apply_basic_styles_to_summary(writer, summary_df_final, summary_sheet_name_final)
            print(f"  [Fase 3] Folha de sumário '{summary_sheet_name_final}' criada.")
        # ... (restante da lógica do sumário) ...
            
    print(f"--- PIPELINE CONCLUÍDO. Resultados em: {OUTPUT_EXCEL_FILENAME} ---")

if __name__ == "__main__":
    run_analysis_pipeline()