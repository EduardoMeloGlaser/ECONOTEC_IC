import os
import httpx
import streamlit as st

def get_groq_api_key():
    if "GROQ_API_KEY" in st.secrets:
        return st.secrets["GROQ_API_KEY"]
    return os.getenv("GROQ_API_KEY")

def ask_llama(prompt: str, contexto: str = "") -> str:
    api_key = get_groq_api_key()
    
    if not api_key:
        return "⚠️ ERRO CRÍTICO: A variável GROQ_API_KEY está VAZIA ou não foi lida das Secrets."

    # Diagnóstico: tentar listar os modelos permitidos para a sua API Key
    url_models = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    
    try:
        with httpx.Client(timeout=10.0) as client:
            res = client.get(url_models, headers=headers)
            if res.status_code == 200:
                models_data = res.json()
                model_ids = [m["id"] for m in models_data.get("data", [])]
                return f"✅ CONEXÃO COM A GROQ OK!\n\nModelos disponíveis na sua chave:\n" + "\n".join(model_ids[:5])
            else:
                return f"❌ ERRO DE AUTENTICAÇÃO/CHAVE GROQ ({res.status_code}): {res.text}"
    except Exception as e:
        return f"⚠️ Erro de conexão: {str(e)}"