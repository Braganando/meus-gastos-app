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
            # Conecta com a chave da API (que vamos configurar no próximo passo)
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
            if texto_limpo.startswith("
```json"):
                texto_limpo = texto_limpo.replace("
```json", "", 1)
            if texto_limpo.endswith("
```"):
                texto_limpo = texto_limpo[::-1].replace("
http://googleusercontent.com/immersive_entry_chip/0

5. Role até o final da página e clique no botão verde **"Commit changes..."** (e confirme no botão verde da janelinha).

*(Nota: Deixei a parte do "salvar no Banco de Dados" de fora desse código por enquanto, para o aplicativo não dar erro caso o banco não exista ainda. Vamos adicionar isso depois que o básico estiver funcionando).*

Quando terminar, **me responda com um "Ok" para irmos para a Tarefa 4 (Pegar a chave do Gemini).**
