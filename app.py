import streamlit as st
from supabase import create_client, Client

# Configuração focada no mobile
st.set_page_config(page_title="Meus Gastos", layout="centered")

# Inicializar cliente Supabase com cache para performance
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_connection()

st.title("💸 Registro Rápido")

# Formulário de entrada
with st.form("form_gastos", clear_on_submit=True):
    item = st.text_input("O que você comprou?")
    local = st.text_input("Onde comprou?")
    
    # Valores configurados para Reais
    valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", step=10.0)
    
    salvar = st.form_submit_button("Registrar Gasto", use_container_width=True)
    
    if salvar:
        if item and local and valor > 0:
            # Prepara o dicionário de dados (a data é inserida automaticamente pelo banco)
            dados = {
                "item": item,
                "local": local,
                "valor": float(valor)
            }
            
            # Tenta inserir no banco de dados
            try:
                resposta = supabase.table("despesas").insert(dados).execute()
                st.success(f"Registrado: {item} no valor de R$ {valor:.2f}!")
            except Exception as e:
                st.error(f"Erro ao salvar no banco de dados: {e}")
        else:
            st.error("Preencha todos os campos para salvar.")
