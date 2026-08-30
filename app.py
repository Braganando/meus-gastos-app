import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
import datetime
import re
from PIL import Image
from sqlalchemy import create_engine
import plotly.express as px

# Configuração visual da página
st.set_page_config(page_title="Meus Gastos", page_icon="📸", layout="wide")

st.title("📸 Leitor de Notas e Dashboard Financeiro")
st.write("Controle financeiro categorizado por grupos específicos e refinados.")

@st.cache_resource
def get_engine():
    if "SUPABASE_URL" in st.secrets:
        return create_engine(st.secrets["SUPABASE_URL"])
    return None

aba1, aba2, aba3, aba4 = st.tabs(["📸 Tirar Foto", "📁 Foto da Galeria", "📊 Subir Planilha (Mobilis)", "📈 Dashboard Consolidado"])

imagem_selecionada = None

# A NOVA LISTA OFICIAL COM "PLANO DE SAÚDE" SEPARADO
CATEGORIAS_VALIDAS = [
    "Açougue / Carnes", "Hortifruti", "Padaria e Confeitaria", "Laticínios e Frios",
    "Mercearia / Alimentos Básicos", "Bebidas (Depósitos e Cervejarias)", "Restaurantes e Delivery",
    "Produtos de Limpeza", "Produtos de Higiene Pessoal", "Farmácia e Saúde", 
    "Plano de Saúde", "Terapias", "Pet Shop", "Utilidades Domésticas", "Papelaria", 
    "Vestuário / Calçados", "E-commerce e Marketplaces", "Casa, Móveis e Decoração", 
    "Eletrônicos e Informática", "Beleza e Cosméticos", "Combustível e Outros Gastos", 
    "Honda Fit", "Transporte", "Contas Fixas e Telecom", "Assinaturas e Serviços Digitais", 
    "Seguros", "Impostos, Taxas e Tarifas Bancárias", "Educação"
]

def mapear_categoria_mobilis(descricao, categoria_antiga):
    texto = f"{descricao} {categoria_antiga}".lower()
    
    regras = {
        "Açougue / Carnes": ['acougue', 'açougue', 'carne', 'todero', 'daliza', 'sinha', 'swift', 'frango', 'peixaria', 'suino', 'bovino'],
        "Hortifruti": ['hortifruti', 'quitanda', 'sacolao', 'fruta', 'verdura', 'legume', 'quitandalopes'],
        "Padaria e Confeitaria": ['padaria', 'panificadora', 'pao', 'bolo', 'amara', 'malaquias', 'doce', 'confeitaria', 'don raffaelo'],
        "Laticínios e Frios": ['laticinio', 'frios', 'queijo', 'presunto', 'mussarela', 'leite'],
        "Mercearia / Alimentos Básicos": ['mercearia', 'arroz', 'feijao', 'macarrao', 'oleo', 'acucar', 'cafe'],
        "Bebidas (Depósitos e Cervejarias)": ['bebida', 'adega', 'ze delivery', 'cerveja', 'vinho', 'depositomarcondes', 'deposito de bebidas', 'cervejaria sp'],
        "Restaurantes e Delivery": ['restaurante', 'ifood', 'ifd*', 'mcdonalds', 'burger king', 'pizza', 'lanche', 'domlanchonete', 'jakaburger', 'sorveteria', 'panela velha', 'kasasushi', 'spasso sabores', 'fino sabor', 'ciadosalgados', 'sao cristov', 'guloseima', 'snack'],
        "Produtos de Limpeza": ['limpeza', 'sabao', 'detergente', 'desinfetante', 'amaciante', 'vassoura', 'lava louca'],
        "Produtos de Higiene Pessoal": ['higiene', 'sabonete', 'shampoo', 'creme dental', 'desodorante'],
        # Farmácia e Saúde (removido o plano de saúde daqui)
        "Farmácia e Saúde": ['farmacia', 'droga', 'pague menos', 'raia', 'drogasil', 'rdsaude', 'montouro', 'farmasite', 'drogalsaojoao', 'medico', 'dentista', 'clinica', 'hospital', 'exame', 'laboratorio', 'otica visao', 'fisioterapia', 'odontologia', 'clara borato', 'isabel cristina', 'htm*r kos', 'remedio', 'remédio'],
        # NOVA CATEGORIA
        "Plano de Saúde": ['unimed', 'presbiterio', 'presbitério', 'plano de saude', 'plano de saúde', 'sulamerica', 'bradesco saude'],
        "Terapias": ['terapia', 'psicologo', 'psiquiatra', 'psicanalista', 'francisco de assis martin'],
        "Pet Shop": ['pet', 'racao', 'veterinario', 'latidos e miados'],
        "Utilidades Domésticas": ['utilidade', 'casa', 'panela', 'pote', 'embalagem', 'flavio embalagens'],
        "Papelaria": ['papelaria', 'caderno', 'lapis', 'caneta', 'sulfite', 'akiten'],
        "Vestuário / Calçados": ['roupa', 'vestuario', 'camisa', 'calca', 'sapato', 'tenis', 'renner', 'c&a', 'zara', 'riachuelo', 'sapataria wilson', 'lojas karze', 'cada passinho'],
        "E-commerce e Marketplaces": ['mercado livre', 'mercadolivre', 'shopee', 'shpp', 'magalu', 'aliexpress', 'amazonmktplc', 'lojas americanas'],
        "Casa, Móveis e Decoração": ['moveis', 'decoracao', 'shop lar', 'ideal home'],
        "Eletrônicos e Informática": ['eletronico', 'informatica', 'computador', 'celular aparelho'],
        "Beleza e Cosméticos": ['beleza', 'cosmetico', 'perfume', 'boticario', 'natura', 'salao', 'cabeleireiro', 'manicure', 'estetica', 'depilacao'],
        "Combustível e Outros Gastos": ['posto', 'gasolina', 'etanol', 'combustivel', 'ipiranga', 'shell', 'petrobras', 'baesso', '14 de julho', 'posto sao joao', 'auto posto', 'pedagio', 'sem parar', 'veloe', 'renovias', 'estacionamento', 'zona azul', 'zul 10', 'zul 2', 'zul', 'pedagio', 'pedágio'],
        "Honda Fit": ['oficina', 'mecanico', 'mecanica', 'autopecas', 'autopeças', 'cidoautopecas', 'ipva', 'licenciamento', 'seguro auto'],
        "Transporte": ['uber', '99', 'blablacar', 'passagem', 'onibus', 'viagem', 'azul', 'gol', 'latam', 'buser', 'taxi', 'transporte', 'mobilidade'],
        "Contas Fixas e Telecom": ['celular', 'vivo', 'claro', 'tim', 'oi', 'internet', 'fibra', 'alares', 'corujatelecomunic', 'claro movel', 'telefone', 'conta de celular', 'plano celular'],
        "Assinaturas e Serviços Digitais": ['netflix', 'spotify', 'amazon prime', 'prime canais', 'hbo', 'disney', 'apple', 'google workspace', 'software', 'assinatura', 'streaming', 'apple com/bill'],
        "Seguros": ['seguro', 'allianz', 'porto seguro', 'seguradora'],
        "Impostos, Taxas e Tarifas Bancárias": ['taxa', 'tarifa', 'iof', 'imposto', 'iptu', 'darf', 'simples', 'juros', 'multa', 'anuidade', 'ted', 'doc', 'tributo', 'das', 'gps', 'manutencao', 'zoop', 'cheque esp', 'banco'],
        "Educação": ['educacao', 'escola', 'faculdade', 'curso', 'univesp', 'cpet', 'ibm', 'getulio vargas', 'gran educacao', 'mensalidade', 'treinamento']
    }

    for cat_oficial, palavras in regras.items():
        if any(palavra in texto for palavra in palavras):
            return cat_oficial
            
    return "Outros"

def limpar_descricao(desc):
    desc = str(desc).upper()
    desc = re.sub(r'COMPRA CARTAO DEB MC \d{2}/\d{2} ', 'Débito: ', desc)
    desc = re.sub(r'COMPRA CARTAO DEB MC ', 'Débito: ', desc)
    desc = re.sub(r'PIX ENVIADO PARA ', 'Pix: ', desc)
    desc = re.sub(r'PIX ENVIADO ', 'Pix: ', desc)
    return desc.title()

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
            3. "Valor_Item": Preço (só número, ex: 15.50).
            4. "Categoria": É OBRIGATÓRIO escolher UMA E APENAS UMA categoria desta lista EXATA: {CATEGORIAS_VALIDAS}. Se o item não for de nenhuma dessas, classifique como "Outros".
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
                                        cat_item = str(item_row['Categoria']).strip()
                                        if cat_item not in CATEGORIAS_VALIDAS: cat_item = "Outros"
                                        
                                        master_records.append({
                                            'Data_Obj': data_mob,
                                            'Descrição': str(item_row['Item']).title(),
                                            'Categoria': cat_item,
                                            'Valor': item_row['Valor_Item']
                                        })
                                    notas_usadas.add((g_date, g_val))
                                    match_encontrado = True
                                    break
                
                if not match_encontrado:
                    desc_banco_limpa = limpar_descricao(row[col_desc])
                    cat_banco = str(row[col_cat]).title()
                    
                    cat_traduzida = mapear_categoria_mobilis(desc_banco_limpa, cat_banco)
                    
                    master_records.append({
                        'Data_Obj': data_mob,
                        'Descrição': desc_banco_limpa,
                        'Categoria': cat_traduzida,
                        'Valor': val_mob
                    })
            
            df_master = pd.DataFrame(master_records)
            df_master = df_master.dropna(subset=['Data_Obj'])
            
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
                
                st.write("---")
                st.subheader("🔍 Auditoria da Categoria 'Outros'")
                df_outros = df_master_filtrado[df_master_filtrado['Categoria'] == 'Outros']
                if not df_outros.empty:
                    st.write("Gastos não reconhecidos. Agora os nomes dos Débitos estão muito mais limpos para você identificar:")
                    df_outros_display = df_outros.copy()
                    df_outros_display['Data'] = df_outros_display['Data_Obj'].dt.strftime('%d/%m/%Y')
                    df_outros_display = df_outros_display[['Data', 'Descrição', 'Valor']]
                    df_outros_display['Valor'] = df_outros_display['Valor'].apply(lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                    st.dataframe(df_outros_display, use_container_width=True)
                else:
                    st.success("Perfeito! Não há nenhum gasto perdido na categoria 'Outros'.")
                
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
