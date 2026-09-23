import streamlit as st
import asyncio
from api_client import obter_selic_atual
from llm_client import ask_llama

st.set_page_config(page_title="Assistente Econômico", page_icon="📈")
st.title("📈 Assistente Econômico Inteligente")
st.write("Consulte dados em tempo real do Banco Central, Ipeadata e Tesouro Nacional.")

# Inicializar histórico do Chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Exibir histórico na tela
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Capturar entrada do usuário
if prompt := st.chat_input("Ex: Qual é a taxa Selic atual e o que ela significa?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Buscando dados das APIs e consultando Llama 3.2..."):
            # 1. Busca os dados reais das APIs
            try:
                dados_selic = asyncio.run(obter_selic_atual())
                contexto = f"Selic Atual: {dados_selic.valor}% na data {dados_selic.data}" if dados_selic else "Dados indisponíveis."
            except Exception as e:
                contexto = "Dados da Selic indisponíveis no momento."

            # 2. Envia a pergunta e o contexto para o LLM (chamada direta síncrona)
            resposta = ask_llama(prompt, contexto)
            
            st.markdown(resposta)
            st.session_state.messages.append({"role": "assistant", "content": resposta})