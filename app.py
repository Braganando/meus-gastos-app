import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
from PIL import Image

# Configuração visual da página
st.set_page_config(page_title="Meus Gastos", page_icon="📸")

st.title("📸 Leitor de Notas e Recibos")
st.write("Envie um comprovante para extrair os dados e gerar o Excel!")

# Criação de abas para organizar as opções
aba1, aba2 = st.tabs(["📸 Tirar Foto", "📁 Escolher da Galeria"])

imagem_selecionada = None

# Opção 1: Câmera
with aba1:
    foto_camera = st.camera_input("Tire a foto do documento")
    if foto_camera:
        imagem_selecionada = foto_camera

# Opção 2: Upload de arquivo (Fototeca)
with aba2:
    foto_arquivo = st.file_uploader("Escolha uma imagem da sua galeria", type=['jpg', 'jpeg', 'png'])
    if foto_arquivo:
        imagem_selecionada = foto_arquivo

# Se alguma imagem foi inserida (seja pela câmera ou upload), executa o código
if imagem_selecionada:
    with st.spinner("A Inteligência Artificial está lendo os itens da imagem..."):
        try:
            # Conecta com a chave da API
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            image = Image.open(imagem_selecionada)
            model = genai.GenerativeModel('gemini-3.6-flash')
            
            # NOVO COMANDO (PROMPT): Instruindo a IA a pegar item por item
            prompt = """
            Analise esta imagem (que é um recibo ou nota fiscal).
            Você precisa extrair CADA ITEM comprado individualmente listado na nota.
            
            Para CADA ITEM, extraia as seguintes informações:
            1. Data: A data da compra (no formato DD/MM/AAAA). Repita a mesma data para todos os itens desta nota.
            2. Item: O nome ou descrição do produto comprado.
            3. Valor: O preço final daquele item específico (apenas o número, ex: 15.50).
            4. Categoria: Classifique o item em uma categoria lógica (ex: Alimentação, Limpeza, Higiene, Eletrônico, Bebida, etc.).
            
            Retorne o resultado EXCLUSIVAMENTE em um formato JSON válido, 
            que deve ser uma lista contendo um dicionário para cada item lido.
            
            Exemplo EXATO de como deve ser a estrutura da sua resposta: 
            [
              {"Data": "30/08/2026", "Item": "Arroz Branco 5kg", "Valor": "25.90", "Categoria": "Alimentação"},
              {"Data": "30/08/2026", "Item": "Detergente Líquido", "Valor": "2.50", "Categoria": "Limpeza"}
            ]
            Não inclua marcações markdown nem textos adicionais. Apenas o JSON puro.
            """
            
            response = model.generate_content([prompt, image])
            
            # Limpeza do texto para garantir que o computador entenda a tabela
            texto_limpo = response.text.strip()
            texto_limpo = texto_limpo.removeprefix("```json").removesuffix("```").strip()
            
            # Converte a resposta em Tabela (DataFrame)
            dados = json.loads(texto_limpo)
            df = pd.DataFrame(dados)
            
            st.success("Itens extraídos com sucesso!")
            st.dataframe(df) # Mostra a tabela na tela
            
            # Gera o arquivo Excel para baixar
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Itens')
                
            st.download_button(
                label="⬇️ Baixar Planilha (Excel)",
                data=buffer.getvalue(),
                file_name="itens_comprados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"Não foi possível processar. O Gemini pode ter se confundido com a nota. Erro técnico: {e}")
