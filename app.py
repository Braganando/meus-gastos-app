import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
import google.generativeai as genai
from PIL import Image
import pdfplumber
import json

# 1. CONFIGURAÇÕES INICIAIS
st.set_page_config(page_title="Controle Inteligente", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# Configurar IA do Google (Gemini)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-pro-latest')

# 2. FUNÇÃO DA INTELIGÊNCIA ARTIFICIAL
def extrair_dados_com_ia(conteudo, tipo_arquivo="texto"):
    prompt = """
    Você é um assistente financeiro de elite especializado em leitura de comprovantes e notas fiscais.
    Sua missão é analisar esta imagem/texto e extrair os dados de compra com precisão.
    
    1. Identifique o item principal (ou um resumo curto, ex: "Compra Mercado", "Almoço").
    2. Identifique o estabelecimento (local).
    3. Identifique o VALOR TOTAL Pago em Reais (use ponto para decimais).
    4. Categorize o gasto em: Alimentação, Transporte, Saúde, Educação, Lazer, Moradia, ou Outros.
    
    **IMPORTANTE:** Sua resposta DEVE SER ESTRITAMENTE um arquivo JSON válido. Não inclua texto extra, markdown (```json), comentários ou qualquer coisa que não seja o próprio objeto JSON abaixo:
    {
        "item": "string",
        "local": "string",
        "valor": 0.00,
        "categoria": "string"
    }
    """
    try:
        if tipo_arquivo == "imagem":
            response = model.generate_content([prompt, conteudo])
        else:
            response = model.generate_content(f"{prompt}\n\nConteúdo:\n{conteudo}")
            
        texto_limpo = response.text.replace("```json", "").replace("```", "").strip()
        
        if not texto_limpo:
            return None, "O Gemini retornou uma resposta vazia. Tente uma foto mais nítida."
            
        data = json.loads(texto_limpo)
        return data, None
        
    except json.JSONDecodeError:
        return None, f"A IA não respondeu no formato correto. Texto recebido:\n{response.text}"
    except Exception as e:
        return None, f"Ocorreu um erro na API do Gemini: {e}"

# 3. INTERFACE DO APLICATIVO
st.title("📊 Gestor Financeiro com IA")

tab1, tab2, tab3 = st.tabs(["✍️ Manual", "🤖 IA & Upload", "📈 Dashboard"])

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

# --- ABA 2: UPLOAD INTELIGENTE ---
with tab2:
    st.subheader("Deixe a IA ler seus recibos ou suba um CSV")
    arquivo_upload = st.file_uploader("Envie PDF, JPG, PNG ou CSV", type=['pdf', 'png', 'jpg', 'jpeg', 'csv'])
    
    if arquivo_upload:
        tipo = arquivo_upload.name.split('.')[-1].lower()
        
        if tipo == 'csv':
            try:
                df_csv = pd.read_csv(arquivo_upload, sep=';')
                df_csv = df_csv.rename(columns={
                    'Descrição': 'item',
                    'Nome no Cartão': 'local', 
                    'Valor (em R$)': 'valor',
                    'Categoria': 'categoria'
                })
                
                if 'categoria' in df_csv.columns:
                    df_csv['categoria'] = df_csv['categoria'].fillna('Outros')
                
                colunas_banco = ['item', 'local', 'valor', 'categoria']
                
                if all(c in df_csv.columns for c in colunas_banco):
                    st.write("Pré-visualização dos dados ajustados:")
                    st.dataframe(df_csv[colunas_banco])
                    
                    if st.button("Salvar CSV no Banco de Dados"):
                        dados_lote = df_csv[colunas_banco].to_dict(orient="records")
                        supabase.table("despesas").insert(dados_lote).execute()
                        st.success(f"{len(dados_lote)} registros salvos com sucesso!")
                else:
                    st.error(f"Não foi possível organizar as colunas. O arquivo possui: {', '.join(df_csv.columns)}")
            except Exception as e:
                st.error(f"Erro ao ler CSV: {e}")
        
        else:
            with st.spinner("🧠 A Inteligência Artificial está lendo o documento..."):
                dados_extraidos = None
                erro_ia = None
                
                if tipo in ['png', 'jpg', 'jpeg']:
                    img = Image.open(arquivo_upload)
                    st.image(img, width=300)
                    dados_extraidos, erro_ia = extrair_dados_com_ia(img, "imagem")
                
                elif tipo == 'pdf':
                    texto_pdf = ""
                    with pdfplumber.open(arquivo_upload) as pdf:
                        for page in pdf.pages:
                            texto_pdf += page.extract_text() + "\n"
                    dados_extraidos, erro_ia = extrair_dados_com_ia(texto_pdf, "texto")
                
                if dados_extraidos:
                    st.success("Leitura concluída!")
                    with st.form("form_ia"):
                        st.write("Revise os dados encontrados pela IA:")
                        novo_item = st.text_input("Item", dados_extraidos.get("item", ""))
                        novo_local = st.text_input("Local", dados_extraidos.get("local", ""))
                        novo_valor = st.number_input("Valor", value=float(dados_extraidos.get("valor", 0.0)))
                        nova_cat = st.text_input("Categoria", dados_extraidos.get("categoria", "Outros"))
                        
                        if st.form_submit_button("Confirmar e Salvar"):
                            dados_finais = {"item": novo_item, "local": novo_local, "valor": float(novo_valor), "categoria": nova_cat}
                            try:
                                supabase.table("despesas").insert(dados_finais).execute()
                                st.success("Registro salvo no banco de dados!")
                            except Exception as db_erro:
                                st.error(f"Erro ao salvar no banco: {db_erro}")
                else:
                    st.error(f"Erro da Inteligência Artificial: {erro_ia}")

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
