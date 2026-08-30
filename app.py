import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
from PIL import Image
from sqlalchemy import create_engine
import plotly.express as px

# Configuração visual da página
st.set_page_config(page_title="Meus Gastos", page_icon="📸", layout="wide")

st.title("📸 Leitor de Notas e Dashboard Financeiro")
st.write("Extraia itens, importe planilhas e cruze os dados!")

# Função segura para conectar ao banco
@st.cache_resource
def get_engine():
    if "SUPABASE_URL" in st.secrets:
        return create_engine(st.secrets["SUPABASE_URL"])
    return None

# Criação das 4 abas
aba1, aba2, aba3, aba4 = st.tabs(["📸 Tirar Foto", "📁 Foto da Galeria", "📊 Subir Planilha (Mobilis)", "📈 Dashboard e Gráficos"])

imagem_selecionada = None

# ---------------- ABA 1 e 2: GEMINI ----------------
with aba1:
    foto_camera = st.camera_input("Tire a foto do documento")
    if foto_camera:
        imagem_selecionada = foto_camera

with aba2:
    foto_arquivo = st.file_uploader("Escolha uma imagem da sua galeria", type=['jpg', 'jpeg', 'png'])
    if foto_arquivo:
        imagem_selecionada = foto_arquivo

if imagem_selecionada:
    with st.spinner("Lendo os itens e o valor total..."):
        try:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            image = Image.open(imagem_selecionada)
            model = genai.GenerativeModel('gemini-3.6-flash')
            
            prompt = """
            Analise esta imagem (recibo ou nota fiscal).
            Extraia CADA ITEM listado na nota e também o VALOR TOTAL pago na nota.
            
            Para cada item, crie um dicionário com:
            1. "Data": Data da compra (DD/MM/AAAA).
            2. "Item": Nome do produto.
            3. "Valor_Item": Preço daquele item (só número, ex: 15.50).
            4. "Categoria": Categoria lógica (Alimentação, Limpeza, etc).
            5. "Valor_Total_Nota": O valor total final da nota inteira.
            
            Retorne EXCLUSIVAMENTE um formato JSON válido (uma lista de dicionários).
            Exemplo:
            [{"Data": "30/08/2026", "Item": "Arroz", "Valor_Item": "25.90", "Categoria": "Alimentação", "Valor_Total_Nota": "157.00"}]
            """
            response = model.generate_content([prompt, image])
            texto_limpo = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            
            df_itens = pd.DataFrame(json.loads(texto_limpo))
            df_itens['Valor_Item'] = pd.to_numeric(df_itens['Valor_Item'], errors='coerce')
            df_itens['Valor_Total_Nota'] = pd.to_numeric(df_itens['Valor_Total_Nota'], errors='coerce')
            
            st.success("Itens extraídos!")
            st.dataframe(df_itens)
            
            engine = get_engine()
            if engine:
                if st.button("Salvar Itens no Banco de Dados"):
                    df_itens.to_sql('gastos_itens', engine, if_exists='append', index=False)
                    st.success("Itens salvos no Supabase com sucesso! Vá para a aba Dashboard para ver os gráficos.")
            else:
                st.warning("⚠️ Configure o Supabase para salvar os dados.")
                
        except Exception as e:
            st.error(f"Erro ao processar: {e}")

# ---------------- ABA 3: PLANILHA MOBILIS ----------------
with aba3:
    st.header("Importar Extrato Bancário / Mobilis")
    planilha_banco = st.file_uploader("Suba o arquivo XLS/XLSX do Mobilis", type=['xls', 'xlsx'])
    
    if planilha_banco:
        try:
            df_banco = pd.read_excel(planilha_banco)
            st.write("Prévia dos dados bancários:")
            st.dataframe(df_banco.head())
            
            engine = get_engine()
            if engine:
                if st.button("Salvar Planilha no Banco de Dados"):
                    df_banco.to_sql('gastos_bancarios', engine, if_exists='append', index=False)
                    st.success("Planilha salva no Supabase com sucesso!")
        except Exception as e:
            st.error(f"Erro ao ler planilha: {e}")

# ---------------- ABA 4: DASHBOARD E CRUZAMENTO ----------------
with aba4:
    st.header("📈 Gráficos de Despesas")
    engine = get_engine()
    
    if engine:
        tem_notas = False
        try:
            df_notas = pd.read_sql_table('gastos_itens', engine)
            tem_notas = True
        except ValueError:
            pass 
            
        tem_mobilis = False
        try:
            df_mobilis = pd.read_sql_table('gastos_bancarios', engine)
            tem_mobilis = True
        except ValueError:
            pass

        if tem_notas and not df_notas.empty:
            
            # Filtro de Data
            datas_disponiveis = df_notas['Data'].dropna().unique().tolist()
            data_selecionada = st.multiselect("Filtrar por Data das Notas", datas_disponiveis, default=datas_disponiveis)
            df_notas_filtrado = df_notas[df_notas['Data'].isin(data_selecionada)]
            
            if not df_notas_filtrado.empty:
                st.write("---")
                # GRÁFICO 1: Barras (Fácil leitura)
                st.subheader("Resumo por Categoria")
                df_cat = df_notas_filtrado.groupby('Categoria')['Valor_Item'].sum().reset_index()
                df_cat = df_cat.sort_values(by='Valor_Item', ascending=True)
                fig_bar = px.bar(
                    df_cat, 
                    x='Valor_Item', 
                    y='Categoria', 
                    orientation='h', 
                    text_auto='$.2f',
                    color='Categoria'
                )
                fig_bar.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)

                st.write("---")
                # GRÁFICO 2: Sunburst (Tamanho gigante para caber os itens)
                st.subheader("Detalhamento por Item")
                fig_sun = px.sunburst(
                    df_notas_filtrado, 
                    path=['Categoria', 'Item'], 
                    values='Valor_Item'
                )
                # Força o gráfico a ter 700 pixels de altura e tirar as margens
                fig_sun.update_layout(height=700, margin=dict(t=10, l=0, r=0, b=10))
                fig_sun.update_traces(textinfo="label+value")
                st.plotly_chart(fig_sun, use_container_width=True)
                
                st.write("---")
                st.subheader("Tabela de Itens")
                st.dataframe(df_notas_filtrado, use_container_width=True)
            else:
                st.info("Selecione pelo menos uma data para ver os gráficos.")
                
        # CRUZAMENTO (Se tiver Mobilis e Notas)
        if tem_notas and tem_mobilis:
            st.write("---")
            st.subheader("🔍 Cruzamento: Notas vs Extrato (Mobilis)")
            
            coluna_valor_mobilis = [c for c in df_mobilis.columns if 'valor' in c.lower() or 'amount' in c.lower() or 'saída' in c.lower()]
            
            if coluna_valor_mobilis:
                col_val = coluna_valor_mobilis[0]
                df_mobilis['Valor_Banco_Positivo'] = pd.to_numeric(df_mobilis[col_val], errors='coerce').abs()
                
                st.write(f"Comparando os Valores Totais das Notas com a coluna '{col_val}' do extrato bancário.")
                st.dataframe(df_mobilis[['Data', col_val, 'Valor_Banco_Positivo']].head())
            else:
                st.info("Não consegui encontrar automaticamente a coluna de 'Valor' na sua planilha.")
                
        if not tem_notas and not tem_mobilis:
            st.info("Ainda não existem dados salvos no banco. Envie uma foto de nota ou a planilha para começar.")
