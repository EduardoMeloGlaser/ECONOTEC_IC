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
        return "⚠️ Erro: A chave GROQ_API_KEY não foi encontrada nas Secrets do Streamlit."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }
    
    prompt_completo = f"Contexto Econômico Atual:\n{contexto}\n\nPergunta do Usuário: {prompt}" if contexto else prompt

    payload = {
        "model": "qwen/qwen3.8-27b",
        "messages": [
            {"role": "user", "content": prompt_completo}
        ]
    }
    
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            data = response.json()
            
            if response.status_code != 200:
                msg_erro = data.get('error', {}).get('message', 'Erro desconhecido na API.')
                return f"⚠️ Erro ao consultar a Groq ({response.status_code}): {msg_erro}"
                
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Erro de conexão com a API da Groq: {str(e)}"