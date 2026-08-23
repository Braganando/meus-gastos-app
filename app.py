import streamlit as st
from datetime import datetime

# Configuração focada no mobile
st.set_page_config(page_title="Meus Gastos", layout="centered")

st.title("💸 Registro Rápido")

# Formulário de entrada
with st.form("form_gastos", clear_on_submit=True):
    item = st.text_input("O que você comprou?")
    local = st.text_input("Onde comprou?")
    
    # Valores já configurados para Reais
    valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", step=10.0)
    
    # Botão largo para facilitar o toque no celular
    salvar = st.form_submit_button("Registrar Gasto", use_container_width=True)
    
    if salvar:
        if item and local and valor > 0:
            data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # TODO: Lógica de inserção no banco de dados aqui
            
            st.success(f"Registrado: {item} no valor de R$ {valor:.2f}!")
        else:
            st.error("Preencha todos os campos para salvar.")