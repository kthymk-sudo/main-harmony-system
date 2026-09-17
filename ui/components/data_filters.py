# ui/components/data_filters.py
import streamlit as st
import pandas as pd
import re
import datetime

# 🌟 1단계에서 분리했던 상태 관리 함수
from utils.session_manager import safe_set, restore_state

def render_numeric_filter(df, col, mode_key):
    # 💡 1. 컬럼명 기반 단위 자동 추론
    unit = ""
    if any(x in col for x in ['율', '률', '비율', '%']): unit = "%"
    elif any(x in col for x in ['원', '매출', '금액', '비용']): unit = "원"
    elif any(x in col for x in ['명', '인원', '시청자', '고객']): unit = "명"
    elif any(x in col for x in ['건', '수', '회']): unit = "건"
    
    unit_label = f" ({unit})" if unit else ""
    
    cond_key = f"cond_{mode_key}_{col}"
    restore_state(mode_key, cond_key)
    
    current_cond = st.session_state.get(cond_key, ">")
    
    master_df = st.session_state['db_content'] if mode_key == "db1" else st.session_state['db_audience']
    min_val = float(master_df[col].min()) if not master_df[col].dropna().empty else 0.0
    max_val = float(master_df[col].max()) if not master_df[col].dropna().empty else 0.0
    
    if current_cond == "범위":
        c1, c2, c3 = st.columns([1.2, 1, 1])
        cond = c1.selectbox("비교 조건", [">", ">=", "<", "<=", "==", "범위"], key=cond_key, on_change=safe_set, args=(mode_key, cond_key))
        st.session_state.persist[mode_key][cond_key] = cond
        
        min_key, max_key = f"min_{mode_key}_{col}", f"max_{mode_key}_{col}"
        restore_state(mode_key, min_key)
        restore_state(mode_key, max_key)
        
        min_v = c2.number_input(f"최소값{unit_label}", value=min_val, key=min_key, on_change=safe_set, args=(mode_key, min_key))
        max_v = c3.number_input(f"최대값{unit_label}", value=max_val, key=max_key, on_change=safe_set, args=(mode_key, max_key))
        
        st.session_state.persist[mode_key][min_key] = min_v
        st.session_state.persist[mode_key][max_key] = max_v
        return df[(df[col] >= min_v) & (df[col] <= max_v)]
    else:
        c1, c2 = st.columns([1, 2])
        cond = c1.selectbox("비교 조건", [">", ">=", "<", "<=", "==", "범위"], key=cond_key, on_change=safe_set, args=(mode_key, cond_key))
        st.session_state.persist[mode_key][cond_key] = cond
        
        val_key = f"val_{mode_key}_{col}"
        restore_state(mode_key, val_key)
        
        val = c2.number_input(f"기준값{unit_label}", value=0.0, key=val_key, on_change=safe_set, args=(mode_key, val_key))
        st.session_state.persist[mode_key][val_key] = val
        
        if cond == ">": return df[df[col] > val]
        elif cond == ">=": return df[df[col] >= val]
        elif cond == "<": return df[df[col] < val]
        elif cond == "<=": return df[df[col] <= val]
        elif cond == "==": return df[df[col] == val]
        return df

def render_categorical_filter(df, col, mode_key):
    sel_key = f"sel_{mode_key}_{col}"
    restore_state(mode_key, sel_key)
    
    master_df = st.session_state['db_content'] if mode_key == "db1" else st.session_state['db_audience']
    
    # 🌟 [속도 최적화 1] 탐색 속도를 극대화하기 위해 리스트(List) 대신 집합(Set)을 사용하고, np.nan도 완벽히 거릅니다.
    master_unique = [x for x in master_df[col].unique() if pd.notna(x) and str(x).strip() != ""]
    current_vals_set = set(x for x in df[col].unique() if pd.notna(x) and str(x).strip() != "")
    selected_vals_set = set(st.session_state.get(sel_key, []))
    
    unique_vals = [x for x in master_unique if x in current_vals_set or x in selected_vals_set]
    
    if sel_key in st.session_state:
        valid_vals = [v for v in st.session_state[sel_key] if v in master_unique]
        if len(valid_vals) != len(st.session_state[sel_key]):
            st.session_state[sel_key] = valid_vals
            st.session_state.persist[mode_key][sel_key] = valid_vals
            
    selected = st.multiselect("항목 선택", unique_vals, key=sel_key, on_change=safe_set, args=(mode_key, sel_key), label_visibility="collapsed", placeholder="선택 (비워두면 모두 표시)")
    st.session_state.persist[mode_key][sel_key] = selected
    if selected: return df[df[col].isin(selected)]
    return df

def render_video_name_filter(df, col, mode_key):
    st.caption("🔍 키워드 포함/제외 대상과 목록 선택 대상을 함께 분석합니다.")
    kw_key = f"kw_{mode_key}_{col}"
    restore_state(mode_key, kw_key)
    kw_val = st.text_input("1. 키워드 일괄 포함 (자동 선택)", key=kw_key, placeholder="예: 홍보, 2023 (쉼표로 구분)", label_visibility="visible", on_change=safe_set, args=(mode_key, kw_key))
    st.session_state.persist[mode_key][kw_key] = kw_val
    
    kw_ex_key = f"kw_ex_{mode_key}_{col}"
    restore_state(mode_key, kw_ex_key)
    kw_ex_val = st.text_input("2. 키워드 일괄 제외 (자동 제외)", key=kw_ex_key, placeholder="예: 테스트, 구버전 (쉼표로 구분)", label_visibility="visible", on_change=safe_set, args=(mode_key, kw_ex_key))
    st.session_state.persist[mode_key][kw_ex_key] = kw_ex_val
    
    kw_mask = pd.Series(False, index=df.index)
    if kw_val.strip():
        kw_list = [k.strip() for k in kw_val.split(',') if k.strip()]
        if kw_list:
            pattern = '|'.join(map(re.escape, kw_list))
            # 🌟 [버그 방어] NaN 값이 "nan"이라는 문자열로 인식되어 오작동하는 것을 방지 (fillna 적용)
            kw_mask = df[col].fillna("").astype(str).str.contains(pattern, case=False)
    
    kw_ex_mask = pd.Series(False, index=df.index)
    if kw_ex_val.strip():
        kw_ex_list = [k.strip() for k in kw_ex_val.split(',') if k.strip()]
        if kw_ex_list:
            pattern_ex = '|'.join(map(re.escape, kw_ex_list))
            kw_ex_mask = df[col].fillna("").astype(str).str.contains(pattern_ex, case=False)
    
    master_df = st.session_state['db_content'] if mode_key == "db1" else st.session_state['db_audience']
    master_unique = [x for x in master_df[col].unique() if pd.notna(x) and str(x).strip() != ""]
    
    remaining_df = df[~(kw_mask | kw_ex_mask)]
    
    # 🌟 [속도 최적화 2] 
    current_vals_set = set(x for x in remaining_df[col].unique() if pd.notna(x) and str(x).strip() != "")
    
    sel_key = f"sel_{mode_key}_{col}"
    restore_state(mode_key, sel_key)
    selected_vals_set = set(st.session_state.get(sel_key, []))
    
    unique_vals = [x for x in master_unique if x in current_vals_set or x in selected_vals_set]
    
    if sel_key in st.session_state:
        valid_vals = [v for v in st.session_state[sel_key] if v in master_unique]
        if len(valid_vals) != len(st.session_state[sel_key]):
            st.session_state[sel_key] = valid_vals
            st.session_state.persist[mode_key][sel_key] = valid_vals

    selected = st.multiselect("3. 그 외 항목 쏙쏙 선택", unique_vals, key=sel_key, on_change=safe_set, args=(mode_key, sel_key), label_visibility="visible", placeholder="나머지 항목 중 추가 선택")
    st.session_state.persist[mode_key][sel_key] = selected
    
    has_inc, has_sel, has_exc = bool(kw_val.strip()), bool(selected), bool(kw_ex_val.strip())
    if has_inc or has_sel or has_exc:
        if has_inc or has_sel:
            dropdown_mask = df[col].isin(selected) if selected else pd.Series(False, index=df.index)
            inc_mask = kw_mask | dropdown_mask
        else:
            inc_mask = pd.Series(True, index=df.index)
        exc_mask = ~kw_ex_mask if has_exc else pd.Series(True, index=df.index)
        return df[inc_mask & exc_mask]
    return df

# =====================================================================
# 🌟 하이브리드 날짜/기간 필터 (컴포넌트 라이브러리 보존용)
# =====================================================================
def render_date_filter(df, col, mode_key):
    st.caption("📅 달력으로 선택하거나, ⌨️ 숫자로 직접 타이핑하여 기간을 설정하세요.")
    
    temp_df = df.copy()
    temp_df[col] = pd.to_datetime(temp_df[col], errors='coerce')
    valid_dates = temp_df[col].dropna()
    
    if valid_dates.empty:
        st.warning("유효한 날짜 데이터가 존재하지 않습니다.")
        return df
        
    min_date = valid_dates.min().date()
    max_date = valid_dates.max().date()

    type_key = f"date_type_{mode_key}_{col}"
    restore_state(mode_key, type_key)
    input_type = st.radio("입력 방식", ["📅 달력 선택", "⌨️ 직접 타이핑 (숫자 8자리)"], horizontal=True, key=type_key, on_change=safe_set, args=(mode_key, type_key), label_visibility="collapsed")
    st.session_state.persist[mode_key][type_key] = input_type

    start_date, end_date = min_date, max_date

    if "달력" in input_type:
        cal_key = f"cal_{mode_key}_{col}"
        restore_state(mode_key, cal_key)
        
        default_val = st.session_state.get(cal_key, (min_date, max_date))
        if not isinstance(default_val, tuple) or len(default_val) == 0:
            default_val = (min_date, max_date)

        date_range = st.date_input("기간 선택", value=default_val, min_value=min_date, max_value=max_date, key=cal_key, on_change=safe_set, args=(mode_key, cal_key), label_visibility="collapsed")
        st.session_state.persist[mode_key][cal_key] = date_range
        
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        elif isinstance(date_range, tuple) and len(date_range) == 1:
            start_date = end_date = date_range[0]
        else:
            start_date = end_date = date_range
    else:
        c1, c2 = st.columns(2)
        start_key = f"txt_start_{mode_key}_{col}"
        end_key = f"txt_end_{mode_key}_{col}"
        restore_state(mode_key, start_key)
        restore_state(mode_key, end_key)
        
        txt_start = c1.text_input("시작일 (YYYYMMDD)", value=st.session_state.get(start_key, min_date.strftime("%Y%m%d")), placeholder="예: 20240101", key=start_key, on_change=safe_set, args=(mode_key, start_key))
        txt_end = c2.text_input("종료일 (YYYYMMDD)", value=st.session_state.get(end_key, max_date.strftime("%Y%m%d")), placeholder="예: 20241231", key=end_key, on_change=safe_set, args=(mode_key, end_key))
        
        st.session_state.persist[mode_key][start_key] = txt_start
        st.session_state.persist[mode_key][end_key] = txt_end

        try:
            s_clean = re.sub(r'[^0-9]', '', txt_start)
            e_clean = re.sub(r'[^0-9]', '', txt_end)
            if len(s_clean) == 8: start_date = datetime.datetime.strptime(s_clean, "%Y%m%d").date()
            if len(e_clean) == 8: end_date = datetime.datetime.strptime(e_clean, "%Y%m%d").date()
        except ValueError:
            st.error("⚠️ 날짜 형식이 올바르지 않습니다. (예: 20240101)")
            
    mask = temp_df[col].notna() & (temp_df[col].dt.date >= start_date) & (temp_df[col].dt.date <= end_date)
    return df[mask]