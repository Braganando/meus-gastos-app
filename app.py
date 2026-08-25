import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px

# 1. CONFIGURAÇÕES INICIAIS
st.set_page_config(page_title="Controle Inteligente", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# 2. INTERFACE DO APLICATIVO
st.title("📊 Gestor Financeiro")

tab1, tab2, tab3 = st.tabs(["✍️ Manual", "📁 Upload de CSV", "📈 Dashboard"])

# --- ABA 1: REGISTRO MANUAL ---
with tab1:
    st.subheader("Adicionar Despesa Manualmente")
    with st.form("form_manual", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            item = st.text_input("O que você comprou?")
            local = st.text_input("Onde comprou?")
        with col2:
            valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
            categorias = ["Alimentação", "Transporte", "Saúde", "Educação", "Lazer", "Moradia", "Outros"]
            categoria = st.selectbox("Categoria", categorias)
        
        if st.form_submit_button("Salvar Manualmente"):
            if item and local and valor > 0:
                dados = {"item": item, "local": local, "valor": float(valor), "categoria": categoria}
                try:
                    supabase.table("despesas").insert(dados).execute()
                    st.success("Salvo com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
            else:
                st.warning("Preencha todos os campos corretamente.")

# --- ABA 2: UPLOAD APENAS CSV ---
with tab2:
    st.subheader("Suba a planilha CSV gerada pelo Gemini")
    arquivo_upload = st.file_uploader("Envie o arquivo .csv", type=['csv'])
    
    if arquivo_upload:
        try:
            # Lendo o formato específico do arquivo anexado (separador por vírgula)
            df_csv = pd.read_csv(arquivo_upload, sep=',')
            
            st.write("Visão Geral da Planilha:")
            st.dataframe(df_csv[['Descrição', 'Categoria', 'Valor Líquido (R$)']].head(10))
            
            # Campo extra para definir o "Local" de toda a compra
            local_compra = st.text_input("Qual o nome do estabelecimento (Local)?", placeholder="Ex: Supermercado Assaí")
            
            if st.button("Salvar Lista no Banco de Dados"):
                if not local_compra:
                    st.warning("Por favor, digite o nome do estabelecimento antes de salvar.")
                else:
                    # Mapeia as colunas da planilha para as colunas do banco de dados
                    df_banco = pd.DataFrame()
                    df_banco['item'] = df_csv['Descrição']
                    df_banco['categoria'] = df_csv['Categoria']
                    df_banco['valor'] = df_csv['Valor Líquido (R$)']
                    df_banco['local'] = local_compra
                    
                    # Garantir que não haja itens vazios
                    df_banco['categoria'] = df_banco['categoria'].fillna('Outros')
                    df_banco['valor'] = df_banco['valor'].fillna(0.0)
                    df_banco['item'] = df_banco['item'].fillna('Item Desconhecido')
                    
                    dados_lote = df_banco.to_dict(orient="records")
                    
                    try:
                        supabase.table("despesas").insert(dados_lote).execute()
                        st.success(f"{len(dados_lote)} itens registrados com sucesso no banco!")
                    except Exception as db_erro:
                        st.error(f"Erro ao inserir no banco: {db_erro}")
                        
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}. Verifique se as colunas estão corretas.")

# --- ABA 3: DASHBOARD ---
with tab3:
    st.subheader("Análise das suas Despesas")
    if st.button("Atualizar Gráficos 🔄"):
        pass 
        
    try:
        resposta = supabase.table("despesas").select("*").execute()
        dados_banco = resposta.data
        
        if len(dados_banco) > 0:
            df = pd.DataFrame(dados_banco)
            total_gasto = df['valor'].sum()
            st.metric(label="Total Gasto", value=f"R$ {total_gasto:.2f}")
            
            col_graf1, col_graf2 = st.columns(2)
            with col_graf1:
                fig_pizza = px.pie(df, values='valor', names='categoria', title="Gastos por Categoria", hole=0.3)
                st.plotly_chart(fig_pizza, use_container_width=True)
                
            with col_graf2:
                gastos_por_cat = df.groupby('categoria')['valor'].sum().reset_index()
                fig_barras = px.bar(gastos_por_cat, x='categoria', y='valor', title="Total por Categoria", text_auto='.2f', color='categoria')
                st.plotly_chart(fig_barras, use_container_width=True)
                
            st.write("📋 Histórico Completo:")
            st.dataframe(df[['data_registro', 'item', 'local', 'categoria', 'valor']].sort_values(by="data_registro", ascending=False))
        else:
            st.info("Nenhum dado cadastrado ainda. Vá nas abas anteriores e registre algo!")
    except Exception as e:
        st.error(f"Erro ao carregar dashboard: {e}")
