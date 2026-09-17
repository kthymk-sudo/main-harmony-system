# ui/components/tree_viewer.py
import streamlit as st

def draw_almind_tree(text):
    """아이콘 중복 및 가지 기호 겹침 현상을 완벽히 해결한 순정 트리 렌더러"""
    if not text:
        return
        
    normalized_text = text.replace("    ", "\t").replace("  ", "\t")
    lines = [line for line in normalized_text.split('\n') if line.strip()]
    
    for line in lines:
        indent = len(line) - len(line.lstrip('\t'))
        content = line.strip()
        
        content = content.lstrip("📂").lstrip("└").lstrip("🔹").lstrip("▶").strip()
        
        if indent == 0:
            st.markdown(f"### 🧠 **{content}**")
            st.write("") 
        elif indent == 1:
            st.markdown(f"&nbsp;&nbsp;&nbsp;&nbsp;📂 **{content}**")
        else:
            padding = "&nbsp;&nbsp;&nbsp;&nbsp;" * indent
            st.markdown(f"{padding} └ 🔹 {content}")