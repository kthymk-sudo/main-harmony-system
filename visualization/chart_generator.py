# visualization/chart_generator.py
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

@st.cache_data(show_spinner=False)
def generate_custom_chart(df, rows, cols, vals, agg, chart_type, mode_key="db1", custom_sort_dict=None):
    # 🌟 [방어막: 피벗 연산 전 데이터 증발 방지] 행/열 기준값에 빈칸(NaN)이 있으면 해당 실적이 날아가므로 "미상"으로 치환!
    safe_df = df.copy()
    fill_cols = rows + (cols if cols else [])
    for c in fill_cols:
        # 혹시라도 비어있는 데이터는 "(미상)"으로 표기하여 통계에 합산되도록 유도
        safe_df[c] = safe_df[c].fillna("(미상)").replace("", "(미상)")

    # 안전하게 정제된 데이터로 피벗 연산 수행
    pivot_df = pd.pivot_table(safe_df, index=rows, columns=cols if cols else None, values=vals, aggfunc=agg, fill_value=0)

    if isinstance(pivot_df.columns, pd.MultiIndex):
        existing_vals = [v for v in vals if v in pivot_df.columns.get_level_values(0).unique()]
        pivot_df = pivot_df.loc[:, existing_vals]
    else:
        existing_vals = [v for v in vals if v in pivot_df.columns]
        pivot_df = pivot_df[existing_vals]

    if isinstance(pivot_df.columns, pd.MultiIndex):
        new_cols = []
        for c in pivot_df.columns:
            val_name = str(c[0])
            col_names = [str(x) for x in c[1:] if str(x) != '']
            if col_names: new_cols.append(f"{'-'.join(col_names)}({val_name})")
            else: new_cols.append(val_name)
        pivot_df.columns = new_cols
        
    flat_df = pivot_df.reset_index()

    for r_col in rows:
        click_order = None
        if custom_sort_dict and r_col in custom_sort_dict:
            click_order = custom_sort_dict[r_col]
        else:
            sel_filter_key = f"sel_{mode_key}_{r_col}"
            if sel_filter_key in st.session_state and st.session_state[sel_filter_key]:
                click_order = st.session_state[sel_filter_key]
        
        if click_order:
            existing_vals = flat_df[r_col].unique().tolist()
            full_order = click_order + [x for x in existing_vals if x not in click_order]
            flat_df[r_col] = pd.Categorical(flat_df[r_col], categories=full_order, ordered=True)
            flat_df = flat_df.sort_values(by=rows).reset_index(drop=True)
            flat_df[r_col] = flat_df[r_col].astype(str)

    x_axis = rows[0]
    if len(rows) > 1:
        merge_col = "__X축_통합__"
        flat_df[merge_col] = flat_df[rows].astype(str).agg(' - '.join, axis=1)
        x_axis = merge_col

    if not cols:
        if "막대" in chart_type: fig = px.bar(flat_df, x=x_axis, y=vals, barmode='group', text_auto=True)
        else: fig = px.line(flat_df, x=x_axis, y=vals, markers=True)
        y_title = ", ".join(vals) if len(vals) <= 3 else "선택된 다중 측정값"
    else:
        exclude_cols = set(rows) | {x_axis}
        value_vars = [c for c in flat_df.columns if c not in exclude_cols]
        melted_df = flat_df.melt(id_vars=[x_axis], value_vars=value_vars, var_name='비교그룹', value_name='측정값')
        
        if "막대" in chart_type: fig = px.bar(melted_df, x=x_axis, y='측정값', color='비교그룹', barmode='group', text_auto=True)
        else: fig = px.line(melted_df, x=x_axis, y='측정값', color='비교그룹', markers=True)
        y_title = "측정값"

    for trace in fig.data:
        trace_name = str(trace.name) if trace.name else ""
        is_percent = any(keyword in trace_name for keyword in ['율', '비율'])
        
        if is_percent:
            if "막대" in chart_type: trace.texttemplate = '%{y:.2f}%'
            trace.hovertemplate = '%{name}<br>%{x}<br><b>%{y:.2f}%</b>'
        else:
            if "막대" in chart_type: trace.texttemplate = '%{y:,.0f}'
            trace.hovertemplate = '%{name}<br>%{x}<br><b>%{y:,.0f}</b>'

    fig.update_layout(
        xaxis_title=x_axis if len(rows) == 1 else '선택 항목 조합', 
        yaxis_title=y_title, 
        legend_title_text='구분/항목',
        xaxis={'categoryorder': 'array', 'categoryarray': flat_df[x_axis].tolist()}
    )
    
    table_df = flat_df.copy()
    if "__X축_통합__" in table_df.columns:
        table_df.drop(columns=["__X축_통합__"], inplace=True)
        
    table_df.index = np.arange(1, len(table_df) + 1)
    
    return fig, table_df