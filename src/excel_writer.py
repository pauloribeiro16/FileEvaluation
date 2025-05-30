import pandas as pd

def apply_basic_styles_to_summary(writer, df, sheet_name):
    if df.empty:
        print(f"  [EXCEL_WRITER DEBUG] DataFrame para sumário '{sheet_name}' está vazio, pulando formatação.")
        return
    print(f"  [EXCEL_WRITER DEBUG] Aplicando estilos à folha de sumário '{sheet_name}'...")
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
    print(f"  [EXCEL_WRITER DEBUG] Estilos aplicados à folha de sumário '{sheet_name}'.")


def apply_styles_merge_and_highlight(writer, df, sheet_name, highlights_map):
    if df.empty:
        print(f"  [EXCEL_WRITER DEBUG] DataFrame para folha '{sheet_name}' está vazio.")
        # Ainda assim, criar a folha e o cabeçalho se df.columns existir
        if not df.columns.empty:
            workbook = writer.book; worksheet = writer.sheets[sheet_name]
            header_format = workbook.add_format({'bold': True, 'text_wrap': False, 'valign': 'vcenter', 'align': 'center', 'fg_color': '#4F81BD', 'font_color': 'white', 'border': 1})
            for col_num, value in enumerate(df.columns.values):
                 worksheet.write(0, col_num, value, header_format)
            print(f"  [EXCEL_WRITER DEBUG] Cabeçalho escrito para folha vazia '{sheet_name}'.")
        return

    print(f"  [EXCEL_WRITER DEBUG] Aplicando estilos, união e realces para folha '{sheet_name}'...")
    workbook = writer.book; worksheet = writer.sheets[sheet_name]
    header_format = workbook.add_format({'bold': True, 'text_wrap': False, 'valign': 'vcenter', 'align': 'center', 'fg_color': '#4F81BD', 'font_color': 'white', 'border': 1})
    data_format_default = workbook.add_format({'border': 1, 'valign': 'vcenter'})
    highlight_formats = {}
    if highlights_map:
        unique_colors = set(h_color for h_color in highlights_map.values() if h_color)
        for color_hex in unique_colors:
            highlight_formats[color_hex] = workbook.add_format({'border': 1, 'valign': 'vcenter', 'fg_color': color_hex})

    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)

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

    for col_idx, column_title in enumerate(df.columns):
        max_len = len(str(column_title))
        if not df.empty and column_title in df:
            col_series = df[column_title].dropna()
            if not col_series.empty:
                current_col_max_len = col_series.astype(str).map(len).max()
                if pd.notna(current_col_max_len): max_len = max(max_len, int(current_col_max_len))
        adjusted_width = min(max(max_len + 5, 15), 70)
        worksheet.set_column(col_idx, col_idx, adjusted_width)
    print(f"  [EXCEL_WRITER DEBUG] Estilos, união e realces aplicados para folha '{sheet_name}'.")