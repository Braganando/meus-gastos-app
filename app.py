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
st.write("A base é o seu banco (Mobilis). As notas detalham as compras!")

# Função segura para conectar ao banco
@st.cache_resource
def get_engine():
    if "SUPABASE_URL" in st.secrets:
        return create_engine(st.secrets["SUPABASE_URL"])
    return None

# Criação das 4 abas
aba1, aba2, aba3, aba4 = st.tabs(["📸 Tirar Foto", "📁 Foto da Galeria", "📊 Subir Planilha (Mobilis)", "📈 Dashboard Consolidado"])

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
            
            # PROMPT ATUALIZADO: Proibido usar categorias genéricas
            prompt = """
            Analise esta imagem (recibo ou nota fiscal).
            Extraia CADA ITEM listado na nota e também o VALOR TOTAL pago na nota.
            
            Para cada item, crie um dicionário com:
            1. "Data": Data da compra (DD/MM/AAAA).
            2. "Item": Nome do produto.
            3. "Valor_Item": Preço daquele item (só número, ex: 15.50).
            4. "Categoria": Categoria lógica do item. REGRA: NÃO use categorias genéricas como 'Alimentação', 'Supermercado' ou 'Compras'. Seja super específico (ex: Açougue, Padaria, Hortifruti, Limpeza, Higiene, Bebidas, Laticínios, etc).
            5. "Valor_Total_Nota": O valor total final da nota inteira.
            
            Retorne EXCLUSIVAMENTE um formato JSON válido (uma lista de dicionários).
            Exemplo:
            [{"Data": "30/08/2026", "Item": "Contra Filé", "Valor_Item": "45.90", "Categoria": "Açougue", "Valor_Total_Nota": "157.00"}]
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
                    st.success("Itens salvos no Supabase com sucesso!")
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
    st.header("📈 Dashboard Consolidado (Mobilis + Notas)")
    engine = get_engine()
    
    if engine:
        tem_notas = False
        try:
            df_notas = pd.read_sql_table('gastos_itens', engine)
            if not df_notas.empty:
                df_notas['Data'] = pd.to_datetime(df_notas['Data'], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y')
                tem_notas = True
        except ValueError:
            pass 
            
        tem_mobilis = False
        try:
            df_mobilis = pd.read_sql_table('gastos_bancarios', engine)
            if not df_mobilis.empty:
                
                # Identifica as colunas do Mobilis
                col_val = [c for c in df_mobilis.columns if 'valor' in c.lower() or 'amount' in c.lower() or 'saída' in c.lower()][0]
                col_cat = [c for c in df_mobilis.columns if 'categoria' in c.lower()]
                col_cat = col_cat[0] if col_cat else 'Categoria'
                col_desc = [c for c in df_mobilis.columns if 'descri' in c.lower()]
                col_desc = col_desc[0] if col_desc else 'Descrição'
                col_tipo = [c for c in df_mobilis.columns if 'tipo' in c.lower()]
                
                df_mobilis['Valor_Original'] = pd.to_numeric(df_mobilis[col_val], errors='coerce')
                
                # 1. FILTRO: APENAS DESPESAS
                if col_tipo:
                    # Se tiver a coluna Tipo, filtra apenas "Despesa"
                    df_mobilis = df_mobilis[df_mobilis[col_tipo[0]].astype(str).str.contains('despesa|saída', case=False, na=True)]
                else:
                    # Se não tiver coluna Tipo, assume que despesas são valores negativos e remove as receitas (positivos)
                    df_mobilis = df_mobilis[df_mobilis['Valor_Original'] < 0]
                
                # Transforma tudo em positivo para o gráfico
                df_mobilis['Valor_Num'] = df_mobilis['Valor_Original'].abs()
                
                # 2. FILTRO: REMOVER PAGAMENTO DE CARTÃO DE CRÉDITO
                termos_fatura = ['pagamento de cartão', 'pagamento de fatura', 'fatura do cartão', 'cartão de crédito']
                mascara_fatura = df_mobilis[col_cat].astype(str).str.lower().str.contains('|'.join(termos_fatura), na=False) | \
                                 df_mobilis[col_desc].astype(str).str.lower().str.contains('pagamento de fatura|pagamento de cartão', na=False)
                df_mobilis = df_mobilis[~mascara_fatura]

                df_mobilis['Data_str'] = pd.to_datetime(df_mobilis['Data'], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y')
                tem_mobilis = True
        except ValueError:
            pass

        # LÓGICA DE CRUZAMENTO (MATCH)
        if tem_mobilis:
            master_records = []
            notas_usadas = set()
            
            if tem_notas:
                notas_agrupadas = df_notas.groupby(['Data', 'Valor_Total_Nota'])
            else:
                notas_agrupadas = []

            for idx, row in df_mobilis.iterrows():
                data_mob = row['Data_str']
                val_mob = row['Valor_Num']
                match_encontrado = False
                
                if pd.notna(data_mob) and pd.notna(val_mob) and tem_notas:
                    for (g_date, g_val), group in notas_agrupadas:
                        if g_date == data_mob and abs(g_val - val_mob) < 0.50:
                            if (g_date, g_val) not in notas_usadas:
                                for _, item_row in group.iterrows():
                                    master_records.append({
                                        'Data': g_date,
                                        'Descrição': item_row['Item'],
                                        'Categoria': item_row['Categoria'],
                                        'Valor': item_row['Valor_Item']
                                    })
                                notas_usadas.add((g_date, g_val))
                                match_encontrado = True
                                break
                
                if not match_encontrado:
                    master_records.append({
                        'Data': data_mob,
                        'Descrição': row[col_desc],
                        'Categoria': row[col_cat],
                        'Valor': val_mob
                    })
            
            if tem_notas:
                for (g_date, g_val), group in notas_agrupadas:
                    if (g_date, g_val) not in notas_usadas:
                        for _, item_row in group.iterrows():
                            master_records.append({
                                'Data': g_date,
                                'Descrição': item_row['Item'],
                                'Categoria': item_row['Categoria'],
                                'Valor': item_row['Valor_Item']
                            })
            
            df_master = pd.DataFrame(master_records)
            
            # 3. LUPA (DESTRINCHAR) CATEGORIAS GENÉRICAS
            def destrinchar(row):
                cat = str(row['Categoria']).strip()
                desc = str(row['Descrição']).strip()
                categorias_genericas = ['outros', 'compras', 'serviços', 'servicos', 'supermercado', 'alimentação', 'alimentacao']
                
                # Se a categoria for genérica, o nome vira "Categoria: Descrição do Item"
                if cat.lower() in categorias_genericas:
                    return f"{cat}: {desc}"
                return cat
            
            df_master['Categoria'] = df_master.apply(destrinchar, axis=1)
            
            # ----------------------------------------------------
            
            # Filtro por Período
            datas_unicas = df_master['Data'].dropna().unique().tolist()
            datas_selecionadas = st.multiselect("Filtrar por Data", datas_unicas, default=datas_unicas)
            df_master_filtrado = df_master[df_master['Data'].isin(datas_selecionadas)]
            
            if not df_master_filtrado.empty:
                st.write("---")
                st.subheader("Despesas 100% Detalhadas")
                
                df_cat = df_master_filtrado.groupby('Categoria')['Valor'].sum().reset_index()
                df_cat = df_cat.sort_values(by='Valor', ascending=True)
                
                fig_bar = px.bar(
                    df_cat, 
                    x='Valor', 
                    y='Categoria', 
                    orientation='h', 
                    text_auto='R$ %.2f',
                    color='Categoria'
                )
                
                # Deixei o gráfico com altura dinâmica para caber todas as categorias perfeitamente
                altura = max(400, len(df_cat) * 35)
                fig_bar.update_layout(height=altura, showlegend=False, xaxis_title="Valor Gasto (R$)", yaxis_title="")
                st.plotly_chart(fig_bar, use_container_width=True)
                
                st.write("---")
                st.subheader("Extrato Consolidado (Mobilis + Itens)")
                st.dataframe(df_master_filtrado, use_container_width=True)
                
        else:
            st.info("Faça o upload da planilha do Mobilis na Aba 3 para gerar o painel consolidado.")
