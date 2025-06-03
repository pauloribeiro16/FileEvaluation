# src/excel_writer.py
import pandas as pd
import os # Adicionado para os.path.splitext

def _determine_cell_highlight_color(sensitivity_label):
    # English sensitivity labels
    if sensitivity_label in ["PERSONAL_DATA_HIGH_SENSITIVITY", "SPECIFIC_HEALTH_DATA", "SENSITIVE_LOCATION_DATA"]: 
        return '#FFC7CE' # Light Red
    elif sensitivity_label in ["PERSONAL_DATA_MEDIUM_SENSITIVITY", "SENSITIVE_FINANCIAL_DATA", "OTHER_SENSITIVE_DATA"]:
        return '#FFEB9C' # Light Yellow
    return None

# ... (_prepare_excel_sheet_data_and_highlights como antes, mas usando "pii_sensitivity_assessment") ...
def _prepare_excel_sheet_data_and_highlights(filename, collected_rows, ollama_cache, max_cols_overall):
    excel_df_data = []
    cell_highlights = {} 

    for df_row_idx, row_dict in enumerate(collected_rows):
        excel_row_list = list(row_dict['keys'])
        excel_row_list.append(row_dict['value'])
        excel_row_list.extend([None] * (max_cols_overall - len(excel_row_list)))
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
            sensibilidade = analysis_for_this_excel_row.get("pii_sensitivity_assessment") # CHAVE EM INGLÊS
            color_to_apply = _determine_cell_highlight_color(sensibilidade)

            if color_to_apply and property_path_that_matched_excel_row:
                num_parts_in_matched_prop_path = len(property_path_that_matched_excel_row.split('.'))
                for col_idx_excel in range(num_parts_in_matched_prop_path):
                    if col_idx_excel < len(excel_row_list) and \
                       excel_row_list[col_idx_excel] == property_path_that_matched_excel_row.split('.')[col_idx_excel]:
                        cell_highlights[(df_row_idx + 1, col_idx_excel)] = color_to_apply
                if ".".join(current_row_path_parts) == property_path_that_matched_excel_row:
                    value_col_idx = len(current_row_path_parts)
                    if value_col_idx < max_cols_overall:
                        cell_highlights[(df_row_idx + 1, value_col_idx)] = color_to_apply
    return excel_df_data, cell_highlights


# ... (apply_styles_to_sheet e apply_styles_to_summary_sheet como antes, mas os nomes das colunas no DataFrame do sumário serão em inglês) ...
def apply_styles_to_sheet(writer, df, sheet_name, highlights_map):
    # ... (Mesma lógica, mas os nomes das colunas do df serão "Level X" e "Schema Attribute Value")
    if df.empty and (not hasattr(df, 'columns') or df.columns.empty):
        print(f"  [EXCEL_WRITER SHEET] DataFrame for sheet '{sheet_name}' is completely empty.")
        workbook = writer.book
        try: worksheet = writer.sheets[sheet_name]
        except KeyError: worksheet = workbook.add_worksheet(sheet_name)
        worksheet.write(0,0, "Empty Schema or No Data to Display.")
        return

    print(f"  [EXCEL_WRITER SHEET] Applying styles, merging, and highlights for sheet '{sheet_name}'...")
    # ... (resto da função como antes) ...
    workbook = writer.book; worksheet = writer.sheets[sheet_name]
    header_format = workbook.add_format({'bold': True, 'text_wrap': False, 'valign': 'vcenter', 'align': 'center', 'fg_color': '#4F81BD', 'font_color': 'white', 'border': 1})
    data_format_default = workbook.add_format({'border': 1, 'valign': 'vcenter'})
    highlight_formats = {}
    if highlights_map:
        unique_colors = set(h_color for h_color in highlights_map.values() if h_color)
        for color_hex in unique_colors:
            highlight_formats[color_hex] = workbook.add_format({'border': 1, 'valign': 'vcenter', 'fg_color': color_hex})

    if not df.columns.empty:
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
    
    if df.empty:
        print(f"  [EXCEL_WRITER SHEET] Sheet '{sheet_name}' has only header. Data styling skipped.")
        return

    for col_idx in range(len(df.columns)):
        current_row_on_worksheet = 1
        while current_row_on_worksheet <= len(df):
            value_to_check = df.iloc[current_row_on_worksheet - 1, col_idx]
            cell_format_to_use = data_format_default
            highlight_key = (current_row_on_worksheet, col_idx)
            if highlight_key in highlights_map and highlights_map[highlight_key] in highlight_formats:
                cell_format_to_use = highlight_formats[highlights_map[highlight_key]]

            if pd.isna(value_to_check):
                worksheet.write(current_row_on_worksheet, col_idx, None, cell_format_to_use)
                current_row_on_worksheet += 1; continue
            
            count_identical = 1
            for next_df_row_idx in range(current_row_on_worksheet, len(df)):
                if df.iloc[next_df_row_idx, col_idx] == value_to_check:
                    next_cell_format = data_format_default
                    next_highlight_key = (next_df_row_idx + 1, col_idx)
                    if next_highlight_key in highlights_map and highlights_map[next_highlight_key] in highlight_formats:
                        next_cell_format = highlight_formats[highlights_map[next_highlight_key]]
                    if cell_format_to_use != next_cell_format: break
                    count_identical += 1
                else: break
            
            if count_identical > 1:
                worksheet.merge_range(current_row_on_worksheet, col_idx, current_row_on_worksheet + count_identical - 1, col_idx, value_to_check, cell_format_to_use)
            else:
                worksheet.write(current_row_on_worksheet, col_idx, value_to_check, cell_format_to_use)
            current_row_on_worksheet += count_identical

    if not df.columns.empty:
        for col_idx, column_title in enumerate(df.columns):
            max_len = len(str(column_title))
            if not df.empty and column_title in df:
                col_series = df[column_title].dropna()
                if not col_series.empty:
                    current_col_max_len = col_series.astype(str).map(len).max()
                    if pd.notna(current_col_max_len): max_len = max(max_len, int(current_col_max_len))
            adjusted_width = min(max(max_len + 5, 15), 70)
            worksheet.set_column(col_idx, col_idx, adjusted_width)
    print(f"  [EXCEL_WRITER SHEET] Styles for sheet '{sheet_name}' applied.")


def apply_styles_to_summary_sheet(writer, df, sheet_name):
    # ... (Mesma lógica, mas os nomes das colunas do df serão em inglês)
    if df.empty:
        print(f"  [EXCEL_WRITER SUMMARY] DataFrame for summary '{sheet_name}' is empty.")
        if hasattr(df, 'columns') and not df.columns.empty:
            workbook = writer.book; worksheet = writer.sheets[sheet_name]
            header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'vcenter', 'align': 'left', 'fg_color': '#DDEBF7', 'border': 1})
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)
            print(f"  [EXCEL_WRITER SUMMARY] Header written for empty summary '{sheet_name}'.")
        return
    print(f"  [EXCEL_WRITER SUMMARY] Applying styles to summary sheet '{sheet_name}'...")
    # ... (resto da função como antes) ...
    workbook = writer.book; worksheet = writer.sheets[sheet_name]
    header_format = workbook.add_format({'bold': True, 'text_wrap': True, 'valign': 'vcenter', 'align': 'left', 'fg_color': '#DDEBF7', 'border': 1})
    data_format = workbook.add_format({'border': 1, 'valign': 'top', 'text_wrap': True}) 
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)
        header_len = len(str(value)); max_data_len = 0
        if value in df:
            col_series = df[value].dropna()
            if not col_series.empty:
                max_data_len = col_series.astype(str).str.len().max()
                if pd.isna(max_data_len): max_data_len = 0
            else: max_data_len = 0
        column_width = min(max(header_len, int(max_data_len)) + 5, 70)
        worksheet.set_column(col_num, col_num, column_width)

    for row_num in range(len(df)):
        for col_num in range(len(df.columns)):
            worksheet.write(row_num + 1, col_num, df.iloc[row_num, col_num], data_format)
    print(f"  [EXCEL_WRITER SUMMARY] Styles for summary sheet '{sheet_name}' applied.")


def generate_excel_report(output_filepath, all_files_parsed_data, ollama_cache, all_unique_properties_info):
    print(f"\n--- GENERATING EXCEL REPORT: {output_filepath} ---")
    with pd.ExcelWriter(output_filepath, engine='xlsxwriter') as writer:
        max_cols_overall = 0
        if all_files_parsed_data:
            for filename_iter, file_data_iter in all_files_parsed_data.items():
                if 'collected_rows_for_excel' in file_data_iter and file_data_iter['collected_rows_for_excel']:
                    current_max = max(len(row['keys']) for row in file_data_iter['collected_rows_for_excel']) + 1
                    if current_max > max_cols_overall: max_cols_overall = current_max
        if max_cols_overall == 0: max_cols_overall = 1

        for filename, file_data in all_files_parsed_data.items():
            sheet_name = os.path.splitext(filename)[0][:31]
            print(f"  [EXCEL_WRITER] Preparing data for sheet: '{sheet_name}'")

            if 'error' in file_data:
                # ... (error handling)
                error_df = pd.DataFrame([{"Error": file_data['error']}]) # Coluna em Inglês
                error_df.to_excel(writer, sheet_name=f"Error_{sheet_name}"[:26], index=False) # Nome da folha em Inglês
                apply_styles_to_sheet(writer, error_df, f"Error_{sheet_name}"[:26], {})
                continue

            collected_rows = file_data['collected_rows_for_excel']
            column_names_excel = [f"Level {i+1}" for i in range(max_cols_overall -1)] + ["Schema Attribute Value"] # Nomes em Inglês

            if not collected_rows:
                empty_df = pd.DataFrame(columns=column_names_excel)
                if column_names_excel: # Adicionar mensagem apenas se houver colunas
                    empty_df.loc[0, column_names_excel[0]] = "Empty Schema or No Data to Display."
                empty_df.to_excel(writer, sheet_name=sheet_name, index=False)
                apply_styles_to_sheet(writer, empty_df, sheet_name, {})
                continue
            
            excel_df_data, cell_highlights = _prepare_excel_sheet_data_and_highlights(
                filename, collected_rows, ollama_cache, max_cols_overall
            )
            df_excel = pd.DataFrame(excel_df_data, columns=column_names_excel)
            df_excel.to_excel(writer, sheet_name=sheet_name, index=False, header=True)
            apply_styles_to_sheet(writer, df_excel, sheet_name, cell_highlights)
            print(f"    [EXCEL_WRITER] Sheet '{sheet_name}' added to Excel.")

        # Generate summary sheet
        summary_data_list = []
        if ollama_cache:
            print(f"  [EXCEL_WRITER] Preparing data for Summary Sheet ({len(ollama_cache)} cache entries)...")
            for unique_key, analysis_data in ollama_cache.items():
                # Include all analyzed properties in the summary
                filename_ctx, path_str_ctx = unique_key.split("::", 1)
                original_description = all_unique_properties_info.get(unique_key, "Description not available")
                
                summary_data_list.append({
                    "Source File": filename_ctx, # Inglês
                    "Schema Key Path": path_str_ctx, # Inglês
                    "Original Description": original_description, # Inglês
                    "PII Classification (Ollama)": analysis_data.get("pii_sensitivity_assessment", "ERROR_NOT_SPECIFIED"), # Inglês
                    "Justification (Ollama)": analysis_data.get("gdpr_justification", "N/A") # Inglês
                })
        
        summary_sheet_name_final = "PII Analysis Summary" # Nome em Inglês
        if summary_data_list:
            summary_df_final = pd.DataFrame(summary_data_list)
            summary_df_final.to_excel(writer, sheet_name=summary_sheet_name_final, index=False)
            apply_styles_to_summary_sheet(writer, summary_df_final, summary_sheet_name_final)
            print(f"  [EXCEL_WRITER] Summary sheet '{summary_sheet_name_final}' created with {len(summary_data_list)} entries.")
        else:
            print("  [EXCEL_WRITER] No Ollama analysis data for the summary sheet.")
            empty_summary_df_cols = ["Source File", "Schema Key Path", "Original Description", "PII Classification (Ollama)", "Justification (Ollama)"]
            empty_summary_df = pd.DataFrame(columns=empty_summary_df_cols)
            empty_summary_df.loc[0, empty_summary_df_cols[0]] = "No Ollama analysis performed or all failed."
            empty_summary_df.to_excel(writer, sheet_name=summary_sheet_name_final, index=False)
            apply_styles_to_summary_sheet(writer, empty_summary_df, summary_sheet_name_final)

    print(f"--- EXCEL REPORT GENERATED: {output_filepath} ---")