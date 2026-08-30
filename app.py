import streamlit as st
import google.generativeai as genai
import pandas as pd
import json
import io
from PIL import Image

# Configuração visual da página
st.set_page_config(page_title="Meus Gastos", page_icon="📸")

st.title("📸 Leitor de Notas e Recibos")
st.write("Tire uma foto do seu comprovante para extrair os dados e gerar o Excel!")

# Componente que acessa a câmera do celular
foto = st.camera_input("Tire a foto do documento")

if foto:
    with st.spinner("A Inteligência Artificial está lendo a imagem..."):
        try:
            # Conecta com a chave da API
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            
            image = Image.open(foto)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # O comando (prompt) que enviamos para o Gemini
            prompt = """
            Analise esta imagem (que é um recibo, nota fiscal ou comprovante de gasto).
            Extraia as seguintes informações: 
            1. Estabelecimento (nome do local)
            2. Data (no formato DD/MM/AAAA)
            3. Valor_Total (apenas o número, ex: 150.50)
            4. Categoria (ex: Alimentação, Transporte, Saúde, etc.)
            
            Retorne o resultado EXCLUSIVAMENTE em um formato JSON válido, 
            exatamente como esta estrutura de exemplo: 
            [{"Estabelecimento": "Mercado X", "Data": "30/08/2026", "Valor_Total": "150.50", "Categoria": "Alimentação"}]
            Não inclua marcações markdown nem textos adicionais. Apenas o JSON puro.
            """
            
            response = model.generate_content([prompt, image])
            
            # Limpeza do texto para garantir que o computador entenda a tabela
            texto_limpo = response.text.strip()
            texto_limpo = texto_limpo.removeprefix("```json").removesuffix("```").strip()
            
            # Converte a resposta em Tabela (DataFrame)
            dados = json.loads(texto_limpo)
            df = pd.DataFrame(dados)
            
            st.success("Dados extraídos com sucesso!")
            st.dataframe(df) # Mostra a tabela na tela
            
            # Gera o arquivo Excel para baixar
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Gastos')
                
            st.download_button(
                label="⬇️ Baixar Planilha (Excel)",
                data=buffer.getvalue(),
                file_name="meus_gastos.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"Não foi possível ler esta imagem. Erro técnico: {e}")
