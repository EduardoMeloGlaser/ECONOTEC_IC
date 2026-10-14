import streamlit as st
import asyncio
from api_client import obter_selic_atual, obter_noticias_financeiras
from llm_client import ask_llama

# Configuração da página para ocupar a largura inteira (wide)
st.set_page_config(page_title="Assistente Econômico", page_icon="📈", layout="wide")

st.title("📈 Assistente Econômico & Notícias Financeiras")

# Criando 2 colunas principais conforme a imagem
col_noticias, col_chat = st.columns([1, 1], gap="large")

# ==========================================
# COLUNA DA ESQUERDA: Últimas Notícias Financeiras
# ==========================================
with col_noticias:
    st.header("📰 Últimas Notícias Financeiras")
    st.write("Acompanhe as principais manchetes em tempo real:")
    
    with st.spinner("Carregando notícias..."):
        noticias = obter_noticias_financeiras(limite=6)
    
    # Exibe as notícias em um container com rolagem (scrollable container)
    with st.container(height=550):
        if noticias:
            for item in noticias:
                with st.expander(f"📌 {item.titulo}", expanded=False):
                    st.caption(f"Fonte: {item.fonte} | {item.data_publicacao}")
                    st.markdown(f"[🔗 Ler matéria completa]({item.link})")
        else:
            st.info("Nenhuma notícia encontrada no momento.")

# ==========================================
# COLUNA DA DIREITA: Chat IA que já existe
# ==========================================
with col_chat:
    st.header("💬 Chat de Inteligência Financeira")
    
    # Inicializar histórico do Chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Container scrollável para o chat
    chat_container = st.container(height=450)

    # Exibir histórico na tela dentro do container
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Capturar entrada do usuário
    if prompt := st.chat_input("Ex: Qual é a taxa Selic atual e o que ela significa?"):
        # Salva e exibe mensagem do usuário
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Rerenderiza para exibir imediatamente
        st.rerun()

    # Processamento da resposta da IA (se a última mensagem for do usuário)
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        prompt_atual = st.session_state.messages[-1]["content"]
        
        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Buscando dados das APIs e consultando LLM..."):
                    try:
                        dados_selic = asyncio.run(obter_selic_atual())
                        contexto = f"Selic Atual: {dados_selic.valor}% na data {dados_selic.data}" if dados_selic else "Dados indisponíveis."
                    except Exception as e:
                        contexto = "Dados da Selic indisponíveis no momento."

                    resposta = ask_llama(prompt_atual, contexto)
                    st.markdown(resposta)
                    st.session_state.messages.append({"role": "assistant", "content": resposta})