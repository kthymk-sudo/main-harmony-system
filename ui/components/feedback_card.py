# ui/components/feedback_card.py
import streamlit as st
import re

def render_feedback_cards(feedback_result):
    """AI 피드백 결과를 안전하게 3단 카드로 분리하여 렌더링하는 함수"""
    if not feedback_result or feedback_result == "API 호출 오류":
        return

    # 🛡️ 1차 방어선: AI가 헛소리를 적어도 $$제목$$ 형태만 기가 막히게 솎아내는 정규식
    pattern = r"\$\$(.*?)\$\$(.*?)(?=\$\$|$)"
    matches = re.findall(pattern, feedback_result, re.DOTALL)
    
    if len(matches) >= 3:
        cols = st.columns(3)
        for i in range(3):
            title = re.sub(r'^\d+\.?\s*', '', matches[i][0].strip())
            content = matches[i][1].strip()
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"#### 💡 {title}")
                    st.markdown(content)
    else:
        # 🛡️ 2차 방어선: '$$제목' 형태로만 썼을 경우 대비
        fallback_parts = [p.strip() for p in feedback_result.split("$$") if p.strip()]
        valid_parts = [p for p in fallback_parts if len(p) > 10]
        
        if len(valid_parts) >= 3:
            cols = st.columns(3)
            for i in range(3):
                lines = valid_parts[i].split("\n", 1)
                title = re.sub(r'^\d+\.?\s*', '', lines[0].strip())
                content = lines[1].strip() if len(lines) > 1 else ""
                with cols[i]:
                    with st.container(border=True):
                        st.markdown(f"#### 💡 {title}")
                        st.markdown(content)
        else:
            # 🚑 최후의 수단: 통짜 텍스트 출력
            with st.container(border=True):
                st.markdown(feedback_result)