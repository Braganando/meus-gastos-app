import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import datetime
from PIL import Image
from sqlalchemy import create_engine
import plotly.express as px

# Configuração visual da página
st.set_page_config(page_title="Meus Gastos", page_icon="📸", layout="wide")

st.title("📸 Leitor de Notas e Dashboard Financeiro")
st.write("Controle financeiro categorizado por grupos específicos.")

# Função segura para conectar ao banco
@st.cache_resource
def get_engine():
    if "SUPABASE_URL" in st.secrets:
        return create_engine(st.secrets["SUPABASE_URL"])
    return None

# Criação das 4 abas
aba1, aba2, aba3, aba4 = st.tabs(["📸 Tirar Foto", "📁 Foto da Galeria", "📊 Subir Planilha (Mobilis)", "📈 Dashboard Consolidado"])

imagem_selecionada = None

# Lista oficial de categorias permitidas
CATEGORIAS_VALIDAS = [
    "Educação",
    "Farmácia",
    "Açougue",
    "Bebidas",
    "Carro",
    "Transporte",
    "Roupas",
    "Estética",
    "Produtos de Higiene",
    "Produtos de Limpeza",
    "Assinaturas",
    "Taxas, Impostos e Tarifas Bancárias",
    "Celular",
    "Internet",
    "Saúde",
    "Superfluos de Mercado"
]

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
            
            prompt = f"""
            Analise esta imagem (recibo ou nota fiscal).
            Extraia CADA ITEM listado na nota e também o VALOR TOTAL pago na nota.
            
            Para cada item, crie um dicionário com:
            1. "Data": Data da compra (DD/MM/AAAA).
            2. "Item": Nome do produto.
            3. "Valor_Item": Preço daquele item (só número, ex: 15.50).
            4. "Categoria": Você DEVIDAMENTE OBRIGADO a escolher uma e apenas uma categoria desta lista exata: {CATEGORIAS_VALIDAS}. Se o item não se encaixar em nenhuma delas, classifique estritamente como "Outros".
            5. "Valor_Total_Nota": O valor total final da nota inteira.
            
            Retorne EXCLUSIVAMENTE um formato JSON válido (lista de dicionários).
            """
            response = model.generate_content([prompt, image])
            texto_limpo = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            
            df_itens = pd.DataFrame(json.loads(texto_limpo))
            df_itens['Valor_Item'] = pd.to_numeric(df_itens['Valor_Item'], errors='coerce')
            df_itens['Valor_Total_Nota'] = pd.to_numeric(df_itens['Valor_Total_Nota'], errors='coerce')
            
            st.success("Itens extraídos com sucesso!")
            st.dataframe(df_itens)
            
            engine = get_engine()
            if engine:
                if st.button("Salvar Itens no Banco de Dados"):
                    df_itens.to_sql('gastos_itens', engine, if_exists='append', index=False)
                    st.success("Itens salvos no Supabase!")
            else:
                st.warning("⚠️ Configure o Supabase para salvar os dados.")
                
        except Exception as e:
            st.error(f"Erro ao processar a nota: {e}")

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
                    st.success("Planilha salva no Supabase!")
        except Exception as e:
            st.error(f"Erro ao ler planilha: {e}")

# ---------------- ABA 4: DASHBOARD E CRUZAMENTO ----------------
with aba4:
    st.header("📈 Dashboard Consolidado")
    engine = get_engine()
    
    if engine:
        tem_notas = False
        try:
            df_notas = pd.read_sql_table('gastos_itens', engine)
            if not df_notas.empty:
                df_notas['Data_Obj'] = pd.to_datetime(df_notas['Data'], dayfirst=True, errors='coerce')
                tem_notas = True
        except ValueError:
            pass 
            
        tem_mobilis = False
        try:
            df_mobilis = pd.read_sql_table('gastos_bancarios', engine)
            if not df_mobilis.empty:
                col_val = [c for c in df_mobilis.columns if 'valor' in c.lower() or 'amount' in c.lower() or 'saída' in c.lower()][0]
                col_cat = [c for c in df_mobilis.columns if 'categoria' in c.lower()]
                col_cat = col_cat[0] if col_cat else 'Categoria'
                col_desc = [c for c in df_mobilis.columns if 'descri' in c.lower()]
                col_desc = col_desc[0] if col_desc else 'Descrição'
                col_tipo = [c for c in df_mobilis.columns if 'tipo' in c.lower()]
                
                df_mobilis['Valor_Original'] = pd.to_numeric(df_mobilis[col_val], errors='coerce')
                
                if col_tipo:
                    df_mobilis = df_mobilis[df_mobilis[col_tipo[0]].astype(str).str.contains('despesa|saída', case=False, na=True)]
                else:
                    df_mobilis = df_mobilis[df_mobilis['Valor_Original'] < 0]
                
                df_mobilis['Valor_Num'] = df_mobilis['Valor_Original'].abs()
                
                termos_fatura = ['pagamento de cartão', 'pagamento de fatura', 'fatura do cartão', 'cartão de crédito']
                mascara_fatura = df_mobilis[col_cat].astype(str).str.lower().str.contains('|'.join(termos_fatura), na=False) | \
                                 df_mobilis[col_desc].astype(str).str.lower().str.contains('pagamento de fatura|pagamento de cartão', na=False)
                df_mobilis = df_mobilis[~mascara_fatura]

                df_mobilis['Data_Obj'] = pd.to_datetime(df_mobilis['Data'], dayfirst=True, errors='coerce')
                tem_mobilis = True
        except ValueError:
            pass

        if tem_mobilis:
            master_records = []
            notas_usadas = set()
            
            if tem_notas:
                notas_agrupadas = df_notas.groupby(['Data_Obj', 'Valor_Total_Nota'])
            else:
                notas_agrupadas = []

            for idx, row in df_mobilis.iterrows():
                data_mob = row['Data_Obj']
                val_mob = row['Valor_Num']
                match_encontrado = False
                
                if pd.notna(data_mob) and pd.notna(val_mob) and tem_notas:
                    for (g_date, g_val), group in notas_agrupadas:
                        if pd.notna(g_date) and pd.notna(g_val):
                            if abs((g_date - data_mob).days) <= 3 and abs(g_val - val_mob) <= 2.00:
                                if (g_date, g_val) not in notas_usadas:
                                    for _, item_row in group.iterrows():
                                        master_records.append({
                                            'Data_Obj': data_mob,
                                            'Descrição': str(item_row['Item']).title(),
                                            'Categoria': str(item_row['Categoria']).title(),
                                            'Valor': item_row['Valor_Item']
                                        })
                                    notas_usadas.add((g_date, g_val))
                                    match_encontrado = True
                                    break
                
                if not match_encontrado:
                    # Tenta mapear a categoria do Mobilis para a lista oficial, se não achar vira Outros
                    cat_banco = str(row[col_cat]).strip().title()
                    cat_final = cat_banco if cat_banco in CATEGORIAS_VALIDAS else "Outros"
                    
                    master_records.append({
                        'Data_Obj': data_mob,
                        'Descrição': str(row[col_desc]).title(),
                        'Categoria': cat_final,
                        'Valor': val_mob
                    })
            
            df_master = pd.DataFrame(master_records)
            df_master = df_master.dropna(subset=['Data_Obj'])
            
            # --- FILTRO DE CALENDÁRIO ---
            min_date = df_master['Data_Obj'].min().date()
            max_date = df_master['Data_Obj'].max().date()
            
            st.write("---")
            st.subheader("📅 Escolha o Período")
            
            periodo = st.date_input(
                "Selecione a Data de Início e Fim",
                value=[min_date, max_date],
                min_value=min_date,
                max_value=max_date
            )
            
            if len(periodo) == 2:
                start_date, end_date = periodo
                df_master_filtrado = df_master[(df_master['Data_Obj'].dt.date >= start_date) & (df_master['Data_Obj'].dt.date <= end_date)]
            else:
                start_date = periodo[0]
                df_master_filtrado = df_master[df_master['Data_Obj'].dt.date == start_date]
            
            if not df_master_filtrado.empty:
                st.write("---")
                st.subheader("Gastos por Categoria Oficial")
                
                df_cat = df_master_filtrado.groupby('Categoria')['Valor'].sum().reset_index()
                df_cat = df_cat.sort_values(by='Valor', ascending=True)
                
                df_cat['Valor_Moeda'] = df_cat['Valor'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                
                fig_bar = px.bar(
                    df_cat, 
                    x='Valor', 
                    y='Categoria', 
                    orientation='h', 
                    text='Valor_Moeda', 
                    color='Categoria'
                )
                
                altura = max(400, len(df_cat) * 35)
                fig_bar.update_layout(height=altura, showlegend=False, xaxis_title="Valor Gasto (R$)", yaxis_title="")
                st.plotly_chart(fig_bar, use_container_width=True)
                
                # --- AUDITORIA DE "OUTROS" ---
                st.write("---")
                st.subheader("🔍 Auditoria da Categoria 'Outros'")
                df_outros = df_master_filtrado[df_master_filtrado['Categoria'] == 'Outros']
                if not df_outros.empty:
                    st.write("Estes lançamentos caíram em 'Outros' porque não estavam na lista oficial. Veja se deseja criar uma nova categoria para eles:")
                    df_outros_display = df_outros.copy()
                    df_outros_display['Data'] = df_outros_display['Data_Obj'].dt.strftime('%d/%m/%Y')
                    df_outros_display = df_outros_display[['Data', 'Descrição', 'Valor']]
                    df_outros_display['Valor'] = df_outros_display['Valor'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    st.dataframe(df_outros_display, use_container_width=True)
                else:
                    st.success("Perfeito! Não há nenhum gasto perdido na categoria 'Outros' no período selecionado.")
                
                st.write("---")
                st.subheader("Extrato Consolidado")
                df_display = df_master_filtrado.copy()
                df_display['Data'] = df_display['Data_Obj'].dt.strftime('%d/%m/%Y')
                df_display = df_display[['Data', 'Descrição', 'Categoria', 'Valor']]
                df_display['Valor'] = df_display['Valor'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                
                st.dataframe(df_display, use_container_width=True)
            else:
                st.info("Nenhuma despesa encontrada para o período selecionado.")
                
        else:
            st.info("Faça o upload da planilha do Mobilis na Aba 3 para gerar o painel consolidado.")
