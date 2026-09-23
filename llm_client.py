import os
import httpx
import streamlit as st

# Tenta buscar a chave tanto das Secrets do Streamlit quanto das variáveis de ambiente
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))

def ask_llama(prompt: str, contexto: str = "") -> str:
    if not GROQ_API_KEY:
        return "⚠️ Erro: A chave GROQ_API_KEY não foi encontrada nas Secrets do Streamlit Cloud."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt_completo = f"Contexto Econômico Atual:\n{contexto}\n\nPergunta do Usuário: {prompt}" if contexto else prompt

    payload = {
        "model": "llama3-8b-8192",
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
                return f"⚠️ Erro na Groq ({response.status_code}): {msg_erro}"
                
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"⚠️ Erro de conexão com a API da Groq: {str(e)}"