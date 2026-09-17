# utils/data_cleaner.py
import pandas as pd
import numpy as np
import datetime
import re

def fill_zero_id(series):
    s = series.astype(str).str.strip()
    s = s.str.replace(r'\.0$', '', regex=True)
    mask = s.str.lower().isin(['nan', 'none', '<na>', '']) | series.isna()
    s = s.str.zfill(8)
    # 🌟 [방어막 3] 글자 'None'이 아닌 완벽한 시스템 결측치(np.nan)로 치환
    s[mask] = np.nan 
    return s

def clean_id(series):
    s = series.astype(str).str.strip()
    s = s.str.replace(r'\.0$', '', regex=True)
    mask = s.str.lower().isin(['nan', 'none', '<na>', '']) | series.isna()
    s[mask] = np.nan
    return s

def clean_percent(series):
    has_percent = series.astype(str).str.contains('%', na=False)
    s = series.astype(str).str.replace('%', '', regex=False).str.replace(',', '', regex=False).str.strip()
    s = s.replace(['nan', 'none', '<na>', ''], np.nan)
    s = pd.to_numeric(s, errors='coerce').fillna(0.0)
    
    mask_needs_mult = (s > 0) & (s <= 1.0) & (~has_percent)
    s = np.where(mask_needs_mult, s * 100, s)
    return pd.Series(s, index=series.index)

def parse_time_to_seconds(val):
    if pd.isna(val): return 0.0
    if isinstance(val, (int, float)): return float(val)
    if isinstance(val, datetime.time):
        return float(val.hour * 3600 + val.minute * 60 + val.second)
    
    val_str = str(val).strip()
    if not val_str: return 0.0
    val_str = val_str.replace('초', '').replace('분', ':').replace('시', ':').replace(' ', '')
    parts = val_str.split(':')
    try:
        if len(parts) == 3: return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2: return float(parts[0]) * 60 + float(parts[1])
        else: return float(parts[0])
    except:
        return 0.0

def clean_date(series):
    return pd.to_datetime(series, errors='coerce').dt.strftime('%Y-%m-%d')

def standardize_columns(df):
    df.columns = df.columns.str.strip()
    rename_dict = {
        '콘텐츠 아이디': '콘텐츠ID', '콘텐츠 ID': '콘텐츠ID',
        'R 고객번호': 'R고객번호', 'R-고객번호': 'R고객번호', 
        '고객번호': 'R고객번호',  # 🌟 [방어막 1] 사원 엑셀의 '고객번호'도 무조건 'R고객번호'로 강제 통일!
        '노출 클릭율': '노출클릭율', '노출 클릭률': '노출클릭율',
        '시청유지율': '시청 유지율',
        '노출 수': '노출수', '클릭 수': '클릭수',
        '영상제목': '영상명', '프로그램명': '영상명',
        '메뉴': '메뉴명', '업로더구분': '업로더 구분'
    }
    for old_col, new_col in rename_dict.items():
        if old_col in df.columns and old_col != new_col:
            if new_col in df.columns:
                df[new_col] = df[new_col].fillna(df[old_col])
                df = df.drop(columns=[old_col])
            else:
                df = df.rename(columns={old_col: new_col})
    return df

def strip_strings(df):
    for c in df.columns:
        if df[c].dtype == 'object':
            df[c] = df[c].apply(lambda x: str(x).strip() if isinstance(x, str) else x)
    return df

# ==========================================
# DB 정제 함수들
# ==========================================
def clean_df1(df1):
    df1 = standardize_columns(df1)
    df1 = strip_strings(df1)
    df1 = df1.dropna(subset=['콘텐츠ID']).copy()
    df1['콘텐츠ID'] = clean_id(df1['콘텐츠ID'])
    if '등록일' in df1.columns: df1['등록일'] = clean_date(df1['등록일'])
    if '노출클릭율' in df1.columns: df1['노출클릭율'] = clean_percent(df1['노출클릭율'])
    for c in ['조회수', '노출수', '클릭수']:
        if c in df1.columns: df1[c] = pd.to_numeric(df1[c].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
    for c in ['러닝타임', '평균 시청 지속시간']:
        if c in df1.columns: df1[c] = df1[c].apply(parse_time_to_seconds)
    return df1

def clean_df2(df2):
    df2 = standardize_columns(df2)
    df2 = strip_strings(df2)
    # 🌟 [방어막 2] 시청자 취향 분석을 위해 '콘텐츠ID'와 'R고객번호' 둘 중 하나라도 없으면 무조건 날려버림
    df2 = df2.dropna(subset=['콘텐츠ID', 'R고객번호']).copy()
    df2['콘텐츠ID'] = clean_id(df2['콘텐츠ID'])
    df2['R고객번호'] = fill_zero_id(df2['R고객번호'])
    if '시청일' in df2.columns: df2['시청일'] = clean_date(df2['시청일'])
    if '시청 유지율' in df2.columns: df2['시청 유지율'] = clean_percent(df2['시청 유지율'])
    for c in ['조회수', '노출수', '클릭수']:
        if c in df2.columns: df2[c] = pd.to_numeric(df2[c].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0)
    for c in ['러닝타임', '평균 시청 지속시간', '시청시간']:
        if c in df2.columns: df2[c] = df2[c].apply(parse_time_to_seconds)
    return df2

def clean_df3(df3):
    df3 = standardize_columns(df3)
    df3 = strip_strings(df3)
    # 🌟 사원 DB에 R고객번호가 없다면 터지지 않고 부드럽게 무시
    if 'R고객번호' in df3.columns:
        df3['R고객번호'] = fill_zero_id(df3['R고객번호'])
        df3 = df3.dropna(subset=['R고객번호']).copy()
    return df3

def mask_sensitive_data(text):
    if not text:
        return ""
        
    masked_text = text

    # 1. RRN 등 완벽 차단 (14자리 일련번호 무시 방어막 포함)
    masked_text = re.sub(r'(?<!\d)(\d{6})[-]?(\d{7})(?!\d)', r'\1-*******', masked_text)
    
    # 2. 휴대전화 및 일반 전화번호 정밀 마스킹 
    masked_text = re.sub(r'(?<!\d)(01[016789]|02|0[3-9]{2})[-.\s]?(\d{3,4})[-.\s]?(\d{4})(?!\d)', r'\1-****-****', masked_text)
    
    return masked_text