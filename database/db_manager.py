# database/db_manager.py
import sqlite3
import pandas as pd
import numpy as np
import streamlit as st
from config import DB_PATH
from utils.data_cleaner import standardize_columns, fill_zero_id, clean_percent

def upsert_to_db(df1=None, df2=None, df3=None):
    conn = sqlite3.connect(DB_PATH)

    def _upsert_table(df, table_name, subset_keys):
        """임시 테이블(Temp Table)을 활용한 초고속/무손실 병합 내부 함수"""
        if df is None or df.empty:
            return

        valid_keys = [k for k in subset_keys if k in df.columns]
        
        for k in valid_keys:
            df[k] = df[k].astype(str).str.strip()
            df[k] = df[k].replace({'nan': 'UNKNOWN', 'None': 'UNKNOWN', '': 'UNKNOWN'})
            df[k] = df[k].fillna('UNKNOWN')

        if valid_keys:
            df = df.drop_duplicates(subset=valid_keys, keep='last')

        cursor = conn.cursor()

        cursor.execute(f"SELECT count(name) FROM sqlite_master WHERE type='table' AND name='{table_name}'")

        if cursor.fetchone()[0] == 0:
            df.to_sql(table_name, conn, if_exists='replace', index=False)
        else:
            
            cursor.execute(f"PRAGMA table_info('{table_name}')")
            existing_cols = [info[1] for info in cursor.fetchall()]
            
            for col in df.columns:
                if col not in existing_cols:
                    cursor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{col}" TEXT')

            temp_table = f"temp_{table_name}"
            df.to_sql(temp_table, conn, if_exists='replace', index=False)
            cols_str = ", ".join([f'"{c}"' for c in df.columns])

            if valid_keys:
                if len(valid_keys) == 1:
                    where_clause = f'"{valid_keys[0]}" IN (SELECT "{valid_keys[0]}" FROM "{temp_table}")'
                else:
                    keys_str = ", ".join([f'"{k}"' for k in valid_keys])
                    where_clause = f'({keys_str}) IN (SELECT {keys_str} FROM "{temp_table}")'

                delete_query = f'DELETE FROM "{table_name}" WHERE {where_clause}'
                cursor.execute(delete_query)

            insert_query = f'INSERT INTO "{table_name}" ({cols_str}) SELECT {cols_str} FROM "{temp_table}"'
            cursor.execute(insert_query)

            cursor.execute(f'DROP TABLE "{temp_table}"')

        conn.commit()

    try:
        _upsert_table(df1, 'tb_content', ['콘텐츠ID'])
        _upsert_table(df2, 'tb_history', ['콘텐츠ID', 'R고객번호', '시청일', '시청시간대'])
        _upsert_table(df3, 'tb_employee', ['고객번호'])

    except Exception as e:
        import streamlit as st
        st.error(f"🚨 데이터베이스 누적 중 오류가 발생하여 안전하게 작업을 중단했습니다: {e}")
    finally:
        conn.close()

def load_from_db():
    conn = sqlite3.connect(DB_PATH)
    try: df1 = pd.read_sql("SELECT * FROM tb_content", conn)
    except: df1 = pd.DataFrame(columns=['콘텐츠ID', '등록일', '채널명', '영상명', '러닝타임'])
    
    try: df2 = pd.read_sql("SELECT * FROM tb_history", conn)
    except: df2 = pd.DataFrame(columns=['콘텐츠ID', 'R고객번호', '시청일', '시청시간대', '시청 유지율', '시청시간'])
    
    try: df3 = pd.read_sql("SELECT * FROM tb_employee", conn)
    except: df3 = pd.DataFrame(columns=['R고객번호'])
    
    conn.close()
    return df1, df2, df3

@st.cache_data(show_spinner=False)
def process_core_databases(df1, df2, df3, use_reg_date, reg_start_date, reg_end_date, use_view_date, view_start_date, view_end_date):
    df1 = standardize_columns(df1)
    df2 = standardize_columns(df2)
    df3 = standardize_columns(df3)

    df2['R고객번호'] = fill_zero_id(df2['R고객번호'])
    df3['R고객번호'] = fill_zero_id(df3['R고객번호'])

    if '시청 유지율' in df2.columns:
        df2['시청 유지율'] = clean_percent(df2['시청 유지율'])

    if '삭제 여부' in df1.columns:
        df1['temp_del'] = df1['삭제 여부'].astype(str).str.strip().str.upper()
        deleted_ids = df1[df1['temp_del'] == 'O']['콘텐츠ID'].dropna().unique().tolist()
        df1 = df1[df1['temp_del'] != 'O']
        df1.drop(columns=['temp_del'], inplace=True)
        if deleted_ids:
            df2 = df2[~df2['콘텐츠ID'].isin(deleted_ids)]

    meta_cols = ['채널명', '메뉴명', '영상명', '러닝타임', '업로더 구분', '제작자']
    for col in meta_cols:
        if col not in df1.columns: df1[col] = np.nan
        if col not in df2.columns: df2[col] = np.nan
        df1[col] = df1[col].replace(r'^\s*$', np.nan, regex=True)
        df2[col] = df2[col].replace(r'^\s*$', np.nan, regex=True)

    for col in meta_cols:
        map_2_to_1 = df2.dropna(subset=[col]).drop_duplicates(subset=['콘텐츠ID']).set_index('콘텐츠ID')[col].to_dict()
        df1[col] = df1[col].fillna(df1['콘텐츠ID'].map(map_2_to_1))
        map_1_to_2 = df1.dropna(subset=[col]).drop_duplicates(subset=['콘텐츠ID']).set_index('콘텐츠ID')[col].to_dict()
        df2[col] = df2[col].fillna(df2['콘텐츠ID'].map(map_1_to_2))

    if '등록일' not in df2.columns: df2['등록일'] = np.nan
    if '시청일' not in df1.columns: df1['시청일'] = np.nan

    map_reg = df1.dropna(subset=['등록일']).drop_duplicates(subset=['콘텐츠ID']).set_index('콘텐츠ID')['등록일'].to_dict()
    df2['등록일'] = df2['등록일'].fillna(df2['콘텐츠ID'].map(map_reg))
    map_view = df2.dropna(subset=['시청일']).drop_duplicates(subset=['콘텐츠ID']).set_index('콘텐츠ID')['시청일'].to_dict()
    df1['시청일'] = df1['시청일'].fillna(df1['콘텐츠ID'].map(map_view))

    df2 = df2[~df2['R고객번호'].isin(df3['R고객번호'])]

    df1_db1 = df1.copy()
    df2_db1 = df2.copy()
    
    if use_reg_date and '등록일' in df1_db1.columns:
        reg_dates_1 = pd.to_datetime(df1_db1['등록일'], errors='coerce').dt.date
        mask_df1 = reg_dates_1.isna() | ((reg_dates_1 >= reg_start_date) & (reg_dates_1 <= reg_end_date))
        df1_db1 = df1_db1[mask_df1]
        
    if use_view_date and '시청일' in df2_db1.columns:
        view_dates_1 = pd.to_datetime(df2_db1['시청일'], errors='coerce').dt.date
        mask_df2_for_db1 = view_dates_1.isna() | ((view_dates_1 >= view_start_date) & (view_dates_1 <= view_end_date))
        df2_db1 = df2_db1[mask_df2_for_db1]

    db_content = df1_db1.copy()
    if 'SO' in db_content.columns: db_content.rename(columns={'SO': '업로더SO'}, inplace=True)

    if not df2_db1.empty:
        agg_dict = {'시청이력_갯수': ('R고객번호', 'count'), '시청자_수': ('R고객번호', 'nunique')}
        if '시청 유지율' in df2_db1.columns: agg_dict['평균_시청_유지율'] = ('시청 유지율', 'mean')
        if '시청시간' in df2_db1.columns: agg_dict['시청시간'] = ('시청시간', 'sum')
        
        agg_metrics = df2_db1.groupby('콘텐츠ID').agg(**agg_dict).reset_index()

        if '시청 유지율' in df2_db1.columns:
            completed_views = df2_db1[df2_db1['시청 유지율'] >= 99.9].groupby('콘텐츠ID').size().reset_index(name='완료건수')
            agg_metrics = pd.merge(agg_metrics, completed_views, on='콘텐츠ID', how='left').fillna(0)
            agg_metrics['시청 완료율'] = np.where(agg_metrics['시청이력_갯수'] > 0, (agg_metrics['완료건수'] / agg_metrics['시청이력_갯수']) * 100, 0)
            agg_metrics.drop(columns=['완료건수'], inplace=True)
        else:
            agg_metrics['평균_시청_유지율'] = 0.0
            agg_metrics['시청 완료율'] = 0.0
            
        if '시청시간' not in agg_metrics.columns:
            agg_metrics['시청시간'] = 0.0
    else:
        agg_metrics = pd.DataFrame(columns=['콘텐츠ID', '시청이력_갯수', '평균_시청_유지율', '시청자_수', '시청시간', '시청 완료율'])

    agg_metrics.rename(columns={'시청이력_갯수': '시청이력 갯수', '평균_시청_유지율': '평균 시청 유지율', '시청자_수': '시청자 수', '시청시간': '총 시청시간'}, inplace=True)
    db_content = pd.merge(db_content, agg_metrics, on='콘텐츠ID', how='left').replace([np.inf, -np.inf], 0)
    for mc in ['시청이력 갯수', '평균 시청 유지율', '시청자 수', '총 시청시간', '시청 완료율']:
        if mc in db_content.columns: db_content[mc] = db_content[mc].fillna(0)

    if use_view_date and not use_reg_date:
        db_content = db_content[db_content['시청이력 갯수'] > 0]

    target_cols_1 = ['채널명', '메뉴명', '콘텐츠ID', '영상명', '업로더 구분', '업로더SO', '러닝타임', '조회수', '노출수', '클릭수', '노출클릭율', '평균 시청 지속시간', '총 시청시간', '등록일', '평균 시청 유지율', '시청 완료율', '시청이력 갯수', '시청자 수']
    db_content = db_content[[c for c in target_cols_1 if c in db_content.columns]]
    db_content.rename(columns={'노출클릭율': '노출 클릭율'}, inplace=True)
    db_content = db_content.replace({None: "", np.nan: ""}).fillna("")

    df1_db2 = df1.copy()
    df2_db2 = df2.copy()
    if 'SO' in df1_db2.columns: df1_db2.rename(columns={'SO': '업로더SO'}, inplace=True)
    if 'SO' in df2_db2.columns: df2_db2.rename(columns={'SO': '시청자SO'}, inplace=True)

    # 🌟 [방어막 2] 조인하기 전, 정보 제공용인 df1(콘텐츠 정보) 쪽에 중복된 콘텐츠ID가 없는지 한 번 더 확실하게 목을 조릅니다. (조인 뻥튀기 원천 차단)
    extra_cols_from_df1 = [c for c in ['콘텐츠ID', '업로더SO', '등록일'] if c in df1_db2.columns]
    df1_extra = df1_db2[extra_cols_from_df1].drop_duplicates(subset=['콘텐츠ID'], keep='first')
    
    overlap_cols = [c for c in extra_cols_from_df1 if c in df2_db2.columns and c != '콘텐츠ID']
    df2_db2_clean = df2_db2.drop(columns=overlap_cols)

    df2_db2_clean['콘텐츠ID'] = df2_db2_clean['콘텐츠ID'].astype(str).str.strip()
    df1_extra['콘텐츠ID'] = df1_extra['콘텐츠ID'].astype(str).str.strip()

    db_audience = pd.merge(df2_db2_clean, df1_extra, on='콘텐츠ID', how='left')

    try:
        conn = sqlite3.connect(DB_PATH)
        df_emp = pd.read_sql("SELECT 고객번호 FROM tb_employee", conn)
        emp_ids = df_emp['고객번호'].dropna().astype(str).str.strip().tolist()
        
        if 'R고객번호' in db_audience.columns:
            db_audience['R고객번호'] = db_audience['R고객번호'].astype(str).str.strip()
            db_audience = db_audience[~db_audience['R고객번호'].isin(emp_ids)]
    except Exception as e:
        pass
    finally:
        if 'conn' in locals(): conn.close()

    if use_reg_date and '등록일' in db_audience.columns:
        reg_dates = pd.to_datetime(db_audience['등록일'], errors='coerce').dt.date
        mask_db2_reg = reg_dates.isna() | ((reg_dates >= reg_start_date) & (reg_dates <= reg_end_date))
        db_audience = db_audience[mask_db2_reg]

    if use_view_date and '시청일' in db_audience.columns:
        view_dates = pd.to_datetime(db_audience['시청일'], errors='coerce').dt.date
        mask_db2_view = view_dates.isna() | ((view_dates >= view_start_date) & (view_dates <= view_end_date))
        db_audience = db_audience[mask_db2_view]

    target_cols_2 = ['R고객번호', '이웃고객명', '성별', '나이', '시청자SO', '콘텐츠ID', '채널명', '메뉴명', '영상명', '러닝타임', '시청시간', '시청일', '시청 유지율', '업로더 구분', '업로더SO', '제작자', '등록일']
    for col in target_cols_2:
        if col not in db_audience.columns: 
            db_audience[col] = ""  
            
    db_audience = db_audience[target_cols_2].replace({None: "", np.nan: ""}).fillna("")
    db_employee = None

    return db_content, db_audience, db_employee