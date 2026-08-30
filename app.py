import streamlit as st
import google.generativeai as genai

st.set_page_config(page_title="Diagnóstico")

st.title("🛠️ Diagnóstico de Conexão")

try:
    # Tenta conectar com a sua chave
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    st.success("Conexão com o Google estabelecida!")
    
    st.write("Os modelos de Inteligência Artificial liberados para a sua chave são:")
    
    # Pede a lista de modelos para o Google
    modelos_liberados = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            modelos_liberados.append(m.name)
            
    st.write(modelos_liberados)
    
except Exception as e:
    st.error(f"Erro ao testar a conexão: {e}")
