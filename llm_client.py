import os
import re
import httpx
import streamlit as st

# Confirme o ID do modelo no console da Groq (console.groq.com/docs/models)
MODELO = "qwen/qwen3.8-27b"


def get_groq_api_key():
    try:
        if "GROQ_API_KEY" in st.secrets:
            return st.secrets["GROQ_API_KEY"]
    except Exception:
        # Sem arquivo secrets.toml (execução local): cai para a variável de ambiente
        pass
    return os.getenv("GROQ_API_KEY")


def ask_llama(prompt: str, contexto: str = "") -> str:
    api_key = get_groq_api_key()

    if not api_key:
        return "⚠️ Erro: A chave GROQ_API_KEY não foi encontrada nas Secrets do Streamlit ou nas variáveis de ambiente."

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }

    prompt_completo = (
        f"Contexto Econômico Atual:\n{contexto}\n\nPergunta do Usuário: {prompt}" if contexto else prompt
    )

    payload = {
        "model": MODELO,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Você é um especialista em macroeconomia e mercado financeiro brasileiro. "
                    "Seja extremamente objetivo, direto ao ponto e didático. "
                    "Evite introduções longas ou fórmulas matemáticas extensas para não cortar a resposta. "
                    "Apresente os resultados e comparações de forma sintética com tópicos claros."
                ),
            },
            {"role": "user", "content": prompt_completo},
        ],
        "temperature": 0.4,
        "max_tokens": 1200,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)

            try:
                data = response.json()
            except ValueError:
                return f"⚠️ Resposta inválida da Groq (status {response.status_code})."

            if response.status_code != 200:
                msg_erro = data.get("error", {}).get("message", "Erro desconhecido na API da Groq.")
                return f"⚠️ Erro ao consultar a Groq ({response.status_code}): {msg_erro}"

            texto = data["choices"][0]["message"]["content"] or ""
            # Alguns modelos de raciocínio devolvem o "pensamento" entre <think>...</think>
            texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL).strip()
            return texto or "⚠️ A IA retornou uma resposta vazia. Tente reformular a pergunta."
    except Exception as e:
        return f"⚠️ Erro de conexão com a API da Groq: {str(e)}"
