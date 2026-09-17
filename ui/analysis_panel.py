# ui/analysis_panel.py
import streamlit as st
import pandas as pd
import uuid

from visualization.chart_generator import generate_custom_chart
from utils.formatters import convert_df_to_excel, convert_df_to_txt, apply_format
from ui.push_dialog import open_push_extractor_dialog
from utils.session_manager import safe_set, restore_state

# 🌟 [회원님 의도 100% 반영] 사이드바 날짜 필터(render_date_filter)는 제외하고 오리지널 필터 모듈만 호출
from ui.components.data_filters import (
    render_numeric_filter,
    render_categorical_filter,
    render_video_name_filter
)
from ui.components.dashboard_widget import render_dashboard_widget

def render_analysis_panel():
    st.markdown("""
        <style>
        /* 1. 사이드바 및 메인 화면의 모든 요소 상하 간격 대폭 축소 */
        div[data-testid="stVerticalBlock"] { gap: 0.4rem !important; }
        
        /* 2. 테두리가 있는 필터 박스 내부 여백 축소 */
        div[data-testid="stVerticalBlockBorderWrapper"] { padding: 0.6rem !important; }
        
        /* 3. 최상단 Header padding 제거 */
        .block-container { padding-top: 4.5rem !important; padding-bottom: 0.5rem !important; }

        /* 4. 하단 유령 공백(Spacer) 강제 파괴 */
        div[data-testid="element-container"] { margin-bottom: 0px !important; padding-bottom: 0px !important; }
        iframe, .stPlotlyChart { margin-bottom: 0px !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("⚙️ 분석할 최종 DB 선택")
    analysis_mode = st.radio(
        "어떤 기준의 데이터를 분석하시겠습니까?",
        ["🎬 [최종 DB 1] 콘텐츠별 성과 종합", "👥 [최종 DB 2] 순수 시청자 이력 상세"],
        horizontal=True,
        label_visibility="collapsed"
    )

    mode_key = "db1" if "최종 DB 1" in analysis_mode else "db2"
    target_df = st.session_state['db_content'] if mode_key == "db1" else st.session_state['db_audience']

    all_cols = target_df.columns.tolist()
    num_cols = target_df.select_dtypes(include=['number']).columns.tolist()

    filtered_df = target_df.copy()

    # =====================================================================
    # 🔍 좌측 사이드바: 상세 데이터 필터링 및 피벗 생성기
    # =====================================================================
    with st.sidebar:
        st.subheader("🔍 상세 데이터 필터링")
        st.caption("원하는 조건으로 데이터를 정밀하게 필터링합니다.")
        
        ft_key = f"filter_targets_{mode_key}"
        restore_state(mode_key, ft_key)
        
        # 유효하지 않은 컬럼(이전 DB 찌꺼기) 자동 정리
        if ft_key in st.session_state: 
            st.session_state[ft_key] = [c for c in st.session_state[ft_key] if c in all_cols]

        filter_targets = st.multiselect("원하는 필터 항목 추가", all_cols, key=ft_key, on_change=safe_set, args=(mode_key, ft_key))

        if filter_targets:
            for col in filter_targets:
                with st.container(border=True):
                    st.markdown(f"**🔹 [{col}] 필터**")
                    if col in num_cols:
                        filtered_df = render_numeric_filter(filtered_df, col, mode_key)
                    elif col == '영상명':
                        filtered_df = render_video_name_filter(filtered_df, col, mode_key)
                    else:
                        filtered_df = render_categorical_filter(filtered_df, col, mode_key)
        
        filtered_df.reset_index(drop=True, inplace=True)
        filtered_df.index = filtered_df.index + 1
        st.success(f"💡 현재 조회된 데이터: **{len(filtered_df):,}건**")

        st.divider()

        # 2. 동적 피벗 및 대시보드 생성기 (세션 상태 복구 최적화 적용)
        st.subheader("🧮 피벗 테이블 생성기")
        st.caption("행, 열, 값을 조합하여 분석 보드를 구성하세요.")
        
        # 🌟 [다이어트] 피벗 세션 복구 루프 간소화
        pv_keys = ['rows', 'cols', 'vals', 'chart']
        for k in pv_keys:
            full_key = f"pv_{k}_{mode_key}"
            restore_state(mode_key, full_key)
            if k != 'chart' and full_key in st.session_state:
                st.session_state[full_key] = [c for c in st.session_state[full_key] if c in all_cols]

        rows = st.multiselect("🔽 행 (Rows)", all_cols, key=f"pv_rows_{mode_key}", on_change=safe_set, args=(mode_key, f"pv_rows_{mode_key}"))
        cols = st.multiselect("▶️ 열 (Columns)", all_cols, key=f"pv_cols_{mode_key}", on_change=safe_set, args=(mode_key, f"pv_cols_{mode_key}"))
        vals = st.multiselect("🔢 값 (Values)", all_cols, key=f"pv_vals_{mode_key}", on_change=safe_set, args=(mode_key, f"pv_vals_{mode_key}"))
        
        agg_dict = {}
        if vals:
            with st.container(border=True):
                st.markdown("⚙️ **값 계산 방식**")
                for val in vals:
                    c1, c2 = st.columns([6, 4])
                    c1.write(f"▪️ {val}")
                    agg_val_key = f"pv_agg_{mode_key}_{val}"
                    restore_state(mode_key, agg_val_key)
                    
                    default_val = "sum" if val in num_cols else "count"
                    default_idx = ['sum', 'mean', 'count', 'max', 'min'].index(default_val)
                    if agg_val_key in st.session_state and st.session_state[agg_val_key] in ['sum', 'mean', 'count', 'max', 'min']:
                        default_idx = ['sum', 'mean', 'count', 'max', 'min'].index(st.session_state[agg_val_key])
                        
                    selected_agg = c2.selectbox("방식", ['sum', 'mean', 'count', 'max', 'min'], index=default_idx, key=agg_val_key, label_visibility="collapsed", on_change=safe_set, args=(mode_key, agg_val_key))
                    agg_dict[val] = selected_agg
                    st.session_state.persist[mode_key][agg_val_key] = selected_agg

        chart_type = st.radio("📊 차트 종류", ["막대 그래프", "꺾은선 그래프"], horizontal=True, key=f"pv_chart_{mode_key}", on_change=safe_set, args=(mode_key, f"pv_chart_{mode_key}"))

        overlap = set(rows) & set(cols)
        if overlap: 
            st.warning("행과 열은 중복될 수 없습니다.")
        pivot_ready = bool(rows) and bool(vals) and not overlap

        if st.button("⬇️ 분석 대시보드에 추가", use_container_width=True, disabled=not pivot_ready):
            filter_snapshots = {r_col: list(st.session_state[f"sel_{mode_key}_{r_col}"]) for r_col in rows if f"sel_{mode_key}_{r_col}" in st.session_state}

            st.session_state.custom_dashboards.append({
                'id': str(uuid.uuid4()), 'mode': analysis_mode, 'rows': list(rows), 
                'cols': list(cols) if cols else [], 'vals': list(vals), 'agg': agg_dict, 
                'chart_type': chart_type, 'df_snapshot': filtered_df.copy(),
                'filter_snapshots': filter_snapshots,
                'mode_key': mode_key
            })
            st.rerun()

    # =====================================================================
    # 📋 메인 화면 본문: 원본 데이터 뷰 및 실시간 피벗 미리보기
    # =====================================================================
    tab_raw, tab_preview = st.tabs(["📋 완성된 원본 데이터 뷰 (Raw Data)", "👁️ 실시간 피벗 미리보기"])

    with tab_raw:
        st.caption(f"선택하신 **[{analysis_mode}]** 기준의 'None' 표기가 제거된 깨끗한 데이터입니다.")
        dl_col1, dl_col2, dl_col3 = st.columns([1, 1, 1])
        with dl_col1:
            st.download_button("📥 현재 원본 데이터 엑셀(.xlsx) 다운로드", data=convert_df_to_excel(filtered_df), file_name=f"raw_data_{mode_key}_filtered.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with dl_col2:
            st.download_button("📝 현재 원본 데이터 텍스트(.txt) 다운로드", data=convert_df_to_txt(filtered_df), file_name=f"raw_data_{mode_key}_filtered.txt", mime="text/plain", use_container_width=True)
        with dl_col3:
            if st.button("📱 원클릭 앱 푸시 타겟 추출기", disabled=(mode_key != "db2"), use_container_width=True):
                st.session_state.pop('ai_copy_result', None) # 🌟 [안전한 최적화] KeyError 방지용 pop 처리
                open_push_extractor_dialog(filtered_df)

        st.caption("🚀 **화면 로딩 최적화 적용:** 미리보기 표는 최대 1,000행까지만 표시됩니다. (엑셀 다운로드 시 전체 데이터 포함)")
        st.dataframe(apply_format(filtered_df.head(1000)), use_container_width=True, height=350)

    with tab_preview:
        if pivot_ready:
            try:
                fig, preview_table = generate_custom_chart(filtered_df, rows, cols, vals, agg_dict, chart_type, mode_key)
                prev_c1, prev_c2 = st.columns([1, 1])
                with prev_c1: 
                    st.caption("🚀 표 미리보기는 1,000행 제한")
                    st.dataframe(apply_format(preview_table.head(1000), rows), use_container_width=True, height=350)
                with prev_c2: 
                    st.plotly_chart(fig, use_container_width=True, key=f"preview_chart_{mode_key}")
            except Exception as e:
                st.error(f"⚠️ 피벗 생성 오류 발생: {str(e)} \n(텍스트 데이터를 연산하려 했거나 행/값 중복이 발생했습니다. 삭제 후 다시 추가해 주세요.)")
        else:
            st.info("👈 왼쪽 사이드바의 [🧮 피벗 테이블 생성기]에서 행(Rows)과 값(Values)을 지정하면 분석 결과가 표시됩니다.")

    st.markdown("---")
    st.header("📊 나만의 맞춤형 피벗 대시보드")
    if not st.session_state.custom_dashboards:
        st.caption("왼쪽 사이드바 하단의 [대시보드에 추가] 버튼을 누르면 이 곳에 차트와 피벗테이블이 누적됩니다.")
    else:
        for idx, widget in enumerate(st.session_state.custom_dashboards):
            if widget['mode'] == analysis_mode: 
                render_dashboard_widget(idx, widget, filtered_df)