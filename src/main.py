import os
import json
import pandas as pd
import time
import utils
import schema_parser
import ollama_analyzer
import excel_writer # Este irá importar as funções de estilo

# --- Configurações Globais ---
JSON_FILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "JSONFiles")
OUTPUT_EXCEL_FILENAME = "Relatorio_Final_Modular.xlsx" # Relativo ao diretório do projeto
FIELD_BATCH_SIZE = 5 # Quantos campos enviar para Ollama por vez na Fase 2

def run_analysis_pipeline():
    print("--- INICIANDO PIPELINE DE ANÁLISE DE ESQUEMAS JSON ---")

    # --- Fase 1: Coleta e Pré-Análise de Documentos ---
    print("\n--- FASE 1: Coleta e Pré-Análise de Documentos ---")
    document_level_analysis = {} # filename -> ollama_doc_analysis_result
    all_properties_for_detailed_analysis = {} # unique_key (filename::path) -> description

    json_files = [f for f in os.listdir(JSON_FILES_DIR) if f.endswith(".json")]
    if not json_files:
        print(f"[FASE 1 ERRO] Nenhum ficheiro .json encontrado em {JSON_FILES_DIR}")
        return

    for filename in json_files:
        print(f"  [Fase 1] Processando: {filename}")
        filepath = os.path.join(JSON_FILES_DIR, filename)
        schema_data = schema_parser.load_schema(filepath)
        if not schema_data:
            document_level_analysis[filename] = {"error": "Falha ao carregar esquema."}
            continue

        metadata = schema_parser.extract_schema_metadata(schema_data)
        
        # Chamada ao Ollama para análise de sumário do documento (pode ser opcional ou mais simples)
        # Por agora, vamos focar em extrair todas as propriedades para análise detalhada
        # doc_analysis_result = ollama_analyzer.analyze_document_summary_with_ollama(
        #     filename, metadata["title"], metadata["description"], metadata["top_properties"]
        # )
        # document_level_analysis[filename] = doc_analysis_result
        # print(f"    [Fase 1] Análise de sumário para {filename}: {doc_analysis_result.get('sensibilidade_documento', 'N/A')}")

        # Extrair todas as propriedades com descrições significativas para a Fase 2
        # A chave será 'filename::path.to.property'
        file_properties = schema_parser.extract_all_properties_with_descriptions(
            schema_data, filename_context=filename
        )
        all_properties_for_detailed_analysis.update(file_properties)
        print(f"    [Fase 1] {len(file_properties)} propriedades com descrição encontradas em {filename}.")

    print(f"--- FASE 1 CONCLUÍDA. {len(all_properties_for_detailed_analysis)} propriedades únicas para análise PII detalhada. ---")
    if not all_properties_for_detailed_analysis:
        print("Nenhuma propriedade com descrição significativa encontrada para análise detalhada. Terminando.")
        return

    # --- Fase 2: Análise Detalhada de Campos em Lote com Ollama e Cache ---
    print("\n--- FASE 2: Análise Detalhada de Campos em Lote com Ollama e Cache ---")
    ollama_cache = utils.load_ollama_cache()
    
    fields_to_analyze_in_batch = []
    for unique_key, description in all_properties_for_detailed_analysis.items():
        if unique_key not in ollama_cache: # Só adicionar se não estiver no cache
            fields_to_analyze_in_batch.append({
                "caminho_completo_chave": unique_key, # ex: "Activity.json::properties.user.name"
                "descricao": description
            })
    
    print(f"  [Fase 2] {len(fields_to_analyze_in_batch)} novas propriedades para enviar ao Ollama (total: {len(all_properties_for_detailed_analysis)}, cacheadas: {len(ollama_cache)}).")

    newly_analyzed_count = 0
    for i in range(0, len(fields_to_analyze_in_batch), FIELD_BATCH_SIZE):
        batch = fields_to_analyze_in_batch[i:i + FIELD_BATCH_SIZE]
        if not batch:
            continue
            
        print(f"  [Fase 2] Processando lote {i//FIELD_BATCH_SIZE + 1} (Campos {i+1} a {min(i+FIELD_BATCH_SIZE, len(fields_to_analyze_in_batch))})")
        time.sleep(1.0) # Delay entre lotes
        batch_results = ollama_analyzer.analyze_field_batch_with_ollama(batch)
        
        for result in batch_results:
            if isinstance(result, dict) and "caminho_completo_chave_analisada" in result:
                ollama_cache[result["caminho_completo_chave_analisada"]] = {
                    "sensibilidade_rgpd": result.get("sensibilidade_rgpd"),
                    "justificacao_rgpd": result.get("justificacao_rgpd")
                }
                newly_analyzed_count +=1
            else:
                # Tentar encontrar a qual campo do batch este erro se refere, se possível
                # Esta parte é um pouco mais complexa se o Ollama não retornar o ID do campo com erro.
                # Por agora, vamos assumir que se 'results' não é uma lista, é um erro geral do lote.
                print(f"    [Fase 2 ERRO] Resultado inesperado para um item do lote: {result}")


        if newly_analyzed_count > 0 and (i//FIELD_BATCH_SIZE + 1) % 2 == 0 : # Salvar a cada X lotes processados
            print(f"    [Fase 2] Salvando cache Ollama com {len(ollama_cache)} entradas...")
            utils.save_ollama_cache(ollama_cache)
    
    if newly_analyzed_count > 0 : # Salvar no final também
         print(f"  [Fase 2] Salvando cache Ollama final com {len(ollama_cache)} entradas...")
         utils.save_ollama_cache(ollama_cache)

    print(f"--- FASE 2 CONCLUÍDA. Análise Ollama e cache atualizados. ---")

    # --- Fase 3: Geração do Relatório Excel ---
    print("\n--- FASE 3: Geração do Relatório Excel ---")
    # Caminho para o ficheiro Excel de saída (um nível acima de src/)
    project_root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_excel_path = os.path.join(project_root_dir, OUTPUT_EXCEL_FILENAME)

    all_files_excel_data = {} # Para guardar {filename: {'schema_data': ..., 'collected_rows': ...}}
    
    # Recarregar os esquemas para o achatamento do Excel
    for filename_to_excel in json_files:
        filepath_to_excel = os.path.join(JSON_FILES_DIR, filename_to_excel)
        schema_data_for_excel = schema_parser.load_schema(filepath_to_excel)
        if schema_data_for_excel:
            all_files_excel_data[filename_to_excel] = {'schema_data': schema_data_for_excel, 'collected_rows': []}
            # Achatamento específico para a estrutura do Excel
            all_files_excel_data[filename_to_excel]['collected_rows'] = schema_parser.flatten_schema_for_excel(
                schema_data_for_excel
            )
        else:
            all_files_excel_data[filename_to_excel] = {'error': "Falha ao recarregar esquema para Excel."}


    with pd.ExcelWriter(output_excel_path, engine='xlsxwriter') as writer:
        for filename, file_content in all_files_excel_data.items():
            sheet_name = os.path.splitext(filename)[0][:31]
            print(f"  [Fase 3] Preparando folha Excel '{sheet_name}' para {filename}...")

            if 'error' in file_content:
                error_df = pd.DataFrame([{"Erro": file_content['error']}])
                error_df.to_excel(writer, sheet_name=f"Erro_{sheet_name}"[:25], index=False)
                continue

            collected_rows = file_content['collected_rows']
            if not collected_rows:
                empty_df = pd.DataFrame([{"Info": f"Esquema {filename} sem dados para exibir."}])
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

                # Determinar realce
                current_row_path_parts = row_dict['keys']
                analysis_for_this_excel_row = None
                property_path_that_matched_excel_row = None

                # Tentar encontrar a qual propriedade principal (analisada) esta linha do Excel pertence
                for i in range(len(current_row_path_parts), 0, -1):
                    # O caminho de uma propriedade no esquema é "properties.nome.subnome"
                    # O `ollama_cache` usa chaves como "filename.json::properties.nome.subnome"
                    potential_schema_prop_path = ".".join(current_row_path_parts[:i])
                    unique_key_for_cache = f"{filename}::{potential_schema_prop_path}"
                    
                    if unique_key_for_cache in ollama_cache:
                        analysis_for_this_excel_row = ollama_cache[unique_key_for_cache]
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
                            cell_highlights[(df_row_idx + 1, col_idx_excel)] = color_to_apply
                        if ".".join(current_row_path_parts) == property_path_that_matched_excel_row:
                            value_col_idx = len(current_row_path_parts)
                            cell_highlights[(df_row_idx + 1, value_col_idx)] = color_to_apply
            
            column_names_excel = [f"Nível {i+1}" for i in range(max_cols -1)] + ["Valor Atributo Esquema"]
            df_excel = pd.DataFrame(excel_df_data, columns=column_names_excel)
            df_excel.to_excel(writer, sheet_name=sheet_name, index=False, header=True)
            excel_writer.apply_styles_merge_and_highlight(writer, df_excel, sheet_name, cell_highlights)
            print(f"    [Fase 3] Folha Excel '{sheet_name}' gerada.")

        # Gerar folha de sumário
        summary_data_list = []
        for unique_key, analysis_data in ollama_cache.items():
            sens_rgpd = analysis_data.get("sensibilidade_rgpd", "N/A")
            if sens_rgpd not in [None, "NAO_DADO_PESSOAL"] and not sens_rgpd.startswith("ERRO_"):
                filename_ctx, path_str_ctx = unique_key.split("::", 1)
                # Obter a descrição original (all_properties_for_detailed_analysis tem unique_key como chave)
                original_description = all_properties_for_detailed_analysis.get(unique_key, "Descrição não encontrada")

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
        else:
            print("  [Fase 3] Nenhum dado sensível para o sumário final.")
            
    print(f"--- PIPELINE CONCLUÍDO. Resultados em: {output_excel_path} ---")


if __name__ == "__main__":
    # Para executar, navegue até o diretório que contém a pasta 'src' e execute:
    # python -m src.main 
    # ou se estiver dentro de src/: python main.py (mas os imports relativos podem precisar de ajuste)
    # Melhor: executar do diretório raiz do projeto (um nível acima de src)
    # Adicionar o diretório raiz ao sys.path se necessário, ou ajustar os imports.
    
    # Forma mais simples de executar se o script main.py estiver em src/
    # e você estiver no diretório raiz do projeto:
    # python src/main.py
    
    # Se for executar este ficheiro main.py diretamente e ele estiver em src/
    # os imports from . import utils podem precisar ser from utils
    # Para manter os imports relativos, é melhor executar como um módulo.
    
    # Alternativa para execução direta (se main.py estiver em src/):
    # import sys
    # # Adicionar o diretório pai (raiz do projeto) ao path para que 'src' possa ser encontrado
    # parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # if parent_dir not in sys.path:
    #    sys.path.insert(0, parent_dir)
    # from src import utils # Agora deve funcionar
    
    # Para simplificar a execução direta deste ficheiro main.py se ele estiver em 'src'
    # e os outros módulos também:
    if __package__ is None or __package__ == '':
        # Executando como script, ajustar imports se necessário
        # Esta é uma forma comum de lidar com imports relativos quando se executa um ficheiro dentro de um pacote.
        # Mas a melhor forma é executar como módulo a partir do diretório pai.
        pass


    # Limpar cache para teste (opcional)
    # cache_file_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), utils.OLLAMA_ANALYSIS_CACHE_FILE)
    # if os.path.exists(cache_file_path):
    #     print(f"[MAIN __main__ DEBUG] Removendo cache antigo: {cache_file_path}")
    #     os.remove(cache_file_path)
        
    run_analysis_pipeline()