# utils/formatters.py
import pandas as pd
import io
import streamlit as st
from utils.data_cleaner import fill_zero_id

def format_seconds_to_hhmmss(v):
    if pd.isna(v) or v == "": return ""
    try:
        v = float(v)
        if v < 0: return ""
        h = int(v // 3600)
        m = int((v % 3600) // 60)
        s = int(v % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except:
        return str(v)

def apply_format(df, rows=None):
    display_df = df.copy()
    if rows and len(rows) > 1 and len(display_df) > 1:
        last_row = None
        for idx, row in display_df.iterrows():
            if last_row is not None:
                parent_match = True
                for r_col in rows:
                    if r_col in display_df.columns:
                        if parent_match and str(row[r_col]) == str(last_row[r_col]):
                            display_df.at[idx, r_col] = ""  
                        else:
                            parent_match = False  
            last_row = df.loc[idx]  
            
    format_dict = {}
    for col in display_df.columns:
        if pd.api.types.is_numeric_dtype(display_df[col]):
            col_str = str(col)
            if '율' in col_str or '비율' in col_str: format_dict[col] = "{:.2f}%"
            elif '시간' in col_str or '타임' in col_str: format_dict[col] = format_seconds_to_hhmmss
            elif '수' in col_str or '건' in col_str or '갯수' in col_str: format_dict[col] = "{:,.0f}"
    return display_df.style.format(format_dict, na_rep="")

def get_formatted_df(df):
    df_out = df.copy()
    for col in df_out.columns:
        col_clean = str(col).replace(' ', '').replace('-', '').upper()
        if 'R고객번호' in col_clean:
            df_out[col] = fill_zero_id(df_out[col])
        elif pd.api.types.is_numeric_dtype(df_out[col]):
            col_str = str(col)
            if '율' in col_str or '비율' in col_str: 
                df_out[col] = df_out[col].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "")
            elif '시간' in col_str or '타임' in col_str: 
                df_out[col] = df_out[col].apply(format_seconds_to_hhmmss)
            elif '수' in col_str or '건' in col_str or '갯수' in col_str: 
                df_out[col] = df_out[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")
    return df_out

@st.cache_data(show_spinner=False)
def convert_df_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        get_formatted_df(df).to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

@st.cache_data(show_spinner=False)
def convert_df_to_txt(df):
    return get_formatted_df(df).to_csv(index=False, sep='\t').encode('utf-8-sig')

@st.cache_data(show_spinner=False)
def convert_raw_df_to_excel(df):
    df_out = df.copy()
    for col in df_out.columns:
        if str(col).replace(' ', '').replace('-', '').upper() == 'R고객번호':
            df_out[col] = fill_zero_id(df_out[col])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_out.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()