import os
import httpx

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def ask_llama(prompt: str, contexto: str = "") -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Unifica o contexto obtido das APIs com a pergunta do usuário
    prompt_completo = f"Contexto Econômico Atual:\n{contexto}\n\nPergunta do Usuário: {prompt}" if contexto else prompt

    payload = {
        "model": "llama-3.1-8b-instant",
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