# ui/components/dashboard_widget.py
import streamlit as st
from visualization.chart_generator import generate_custom_chart
from utils.formatters import convert_df_to_excel, convert_df_to_txt, apply_format

def update_dash_title(w_id):
    """대시보드 위젯의 제목을 수정하는 상태 업데이트 함수"""
    for w in st.session_state.custom_dashboards:
        if w['id'] == w_id: 
            w['custom_title'] = st.session_state[f"title_{w_id}"]

def render_dashboard_widget(idx, widget, filtered_df):
    """개별 대시보드 위젯(차트, 표, AI 브리핑)을 렌더링하는 전담 컴포넌트"""
    with st.container(border=True):
        head_col1, head_col2 = st.columns([9, 1])
        if 'custom_title' not in widget:
            agg_str = ", ".join([f"{k}({v})" for k, v in widget['agg'].items()]) if isinstance(widget['agg'], dict) else str(widget['agg'])
            widget['custom_title'] = f"📌 분석 {idx+1} : {widget['rows']} ➔ {widget['vals']} ({agg_str})"
            
        with head_col1: 
            st.text_input("📝 분석명 (자유롭게 수정 후 엔터)", value=widget['custom_title'], key=f"title_{widget['id']}", on_change=update_dash_title, args=(widget['id'],))
            st.caption(f"🔒 고정된 데이터: **{len(widget.get('df_snapshot', filtered_df)):,}건** (대시보드 추가 시점의 필터 상태가 안전하게 보존되었습니다.)")
        with head_col2:
            if st.button("❌ 삭제", key=f"del_{widget['id']}"):
                st.session_state.custom_dashboards = [w for w in st.session_state.custom_dashboards if w['id'] != widget['id']]
                st.rerun()
                
        try:
            dash_rows = widget['rows']
            dash_df = widget.get('df_snapshot', filtered_df).copy()
            dash_mode_key = widget.get('mode_key', 'db1')
            dash_snapshots = widget.get('filter_snapshots', {})
            
            fig, table_df = generate_custom_chart(dash_df, dash_rows, widget['cols'], widget['vals'], widget['agg'], widget['chart_type'], dash_mode_key, custom_sort_dict=dash_snapshots)
            
            if table_df.empty:
                st.warning("⚠️ 선택하신 필터 조건에 맞는 데이터가 없습니다. 상단에서 필터 조건을 완화해 주세요.")
            else:
                t1, t2, t3 = st.tabs(["📈 시각화 차트", "📋 피벗테이블 및 다운로드", "🤖 AI 인사이트 브리핑"])
                
                with t1:
                    st.plotly_chart(fig, use_container_width=True, key=f"dash_chart_{widget['id']}")
                    
                with t2:
                    dl_col1, dl_col2 = st.columns([1, 1])
                    with dl_col1:
                        st.download_button(label=f"📥 피벗 {idx+1} 엑셀 다운로드", data=convert_df_to_excel(table_df), file_name=f"pivot_analysis_{idx+1}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"excel_{widget['id']}")
                    with dl_col2:
                        st.download_button(label=f"📝 피벗 {idx+1} 텍스트 다운로드", data=convert_df_to_txt(table_df), file_name=f"pivot_analysis_{idx+1}.txt", mime="text/plain", key=f"txt_{widget['id']}")
                    st.caption("🚀 로딩 최적화를 위해 표 미리보기는 1,000행까지만 표시됩니다. (다운로드는 전체 데이터 포함)")
                    st.dataframe(apply_format(table_df, dash_rows), use_container_width=True, height=400)
                    
                with t3:
                    st.write("📊 분석 재료 기준: 현재 저장된 대시보드 뷰 스캔 완료")
                    
                    if 'ai_briefing' not in widget:
                        proc_key = f"ai_proc_{widget['id']}"
                        is_processing = st.session_state.get(proc_key, False)
                        
                        if st.button("✨ 구글 Gemini 기반 AI 인사이트 브리핑 도출하기", key=f"ai_calc_{widget['id']}", disabled=is_processing, use_container_width=True):
                            st.session_state[proc_key] = True 
                            st.rerun()
                            
                        if is_processing:
                            with st.spinner("AI가 전체 DB 통계와 피벗 데이터를 비교 대조하며 혁신적인 인사이트를 도출하고 있습니다..."):
                                try:
                                    from ai_engine.gemini_api import generate_ai_pivot_briefing
                                    data_string = table_df.to_csv(index=False, sep='\t')
                                    
                                    master_df = st.session_state['db_content'] if widget.get('mode_key', 'db1') == 'db1' else st.session_state['db_audience']
                                    num_cols = master_df.select_dtypes(include=['number']).columns
                                    global_stats_str = master_df[num_cols].agg(['mean', 'max']).round(2).to_csv(sep='\t') if len(num_cols) > 0 else "숫자형 통계 없음"
                                    
                                    widget['ai_briefing'] = generate_ai_pivot_briefing(data_string, widget['custom_title'], global_stats_str)
                                finally:
                                    st.session_state[proc_key] = False 
                                    st.rerun()
                    else:
                        st.info(widget['ai_briefing'])
                        if st.button("🔄 인사이트 새로고침 (재분석)", key=f"ai_refresh_{widget['id']}", use_container_width=True):
                            del widget['ai_briefing']
                            st.rerun()
                            
        except Exception as e:
            st.error(f"⚠️ 에러 발생: {str(e)} \n(삭제 후 다시 추가해 주세요.)")