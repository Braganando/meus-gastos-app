import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px

# 1. CONFIGURAÇÕES INICIAIS E SEGURANÇA
st.set_page_config(page_title="Controle Inteligente", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# Camada de sanitização de dados (caso a IA desobedeça a regra de formatação)
def limpar_dinheiro(val):
    if pd.isna(val): return 0.0
    val_str = str(val).upper().replace('R$', '').strip()
    
    if ',' in val_str and '.' in val_str:
        val_str = val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str:
        val_str = val_str.replace(',', '.')
        
    try:
        return float(val_str)
    except:
        return 0.0

# 2. INTERFACE DO APLICATIVO
st.title("📊 Gestor Financeiro Automático")

tab1, tab2, tab3 = st.tabs(["✍️ Manual", "📁 Upload Padronizado", "📈 Dashboard"])

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

# --- ABA 2: UPLOAD PADRONIZADO (Leitura do CSV do Gemini) ---
with tab2:
    st.subheader("Suba o arquivo .csv gerado pelo Super Prompt")
    
    arquivo_upload = st.file_uploader("Envie o arquivo", type=['csv'])
    
    if arquivo_upload:
        try:
            # Força a leitura usando o ponto e vírgula delimitado no prompt
            df_csv = pd.read_csv(arquivo_upload, sep=';', dtype=str)
            
            # Validação estrita de Schema
            colunas_esperadas = ['Data', 'Local', 'Item', 'Categoria', 'Valor']
            
            if all(col in df_csv.columns for col in colunas_esperadas):
                st.success("✅ Arquivo reconhecido e validado com sucesso!")
                st.dataframe(df_csv)
                
                if st.button("Gravar no Banco de Dados", type="primary"):
                    # Mapeia diretamente as colunas do CSV para o padrão do Supabase
                    df_banco = pd.DataFrame()
                    df_banco['item'] = df_csv['Item']
                    df_banco['local'] = df_csv['Local']
                    df_banco['categoria'] = df_csv['Categoria']
                    df_banco['valor'] = df_csv['Valor'].apply(limpar_dinheiro)
                    
                    dados_lote = df_banco.to_dict(orient="records")
                    
                    try:
                        supabase.table("despesas").insert(dados_lote).execute()
                        st.balloons() # Um pequeno feedback visual de sucesso
                        st.success(f"Excelente! {len(dados_lote)} registros inseridos no banco.")
                    except Exception as db_erro:
                        st.error(f"Erro de SQL ao inserir no banco: {db_erro}")
            else:
                st.error("❌ O arquivo não possui o padrão correto de colunas.")
                st.write(f"**Esperado:** {colunas_esperadas}")
                st.write(f"**Encontrado:** {df_csv.columns.tolist()}")
                
        except Exception as e:
            st.error(f"Erro de processamento: {e}. O arquivo pode estar corrompido ou vazio.")

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
            st.info("Nenhum dado cadastrado ainda.")
    except Exception as e:
        st.error(f"Erro ao carregar dashboard: {e}")
