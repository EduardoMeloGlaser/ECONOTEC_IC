import streamlit as st
import asyncio
from api_client import obter_selic_atual, obter_historico_selic, obter_noticias_financeiras
from llm_client import ask_llama

st.set_page_config(page_title="Assistente Econômico & Relatórios", page_icon="📈", layout="wide")

st.title("📈 Assistente Econômico & Painel Financeiro")

# Criando 2 colunas principais
col_painel, col_chat = st.columns([1, 1], gap="large")

# ==========================================
# COLUNA DA ESQUERDA: Relatório & Indicadores / Notícias
# ==========================================
with col_painel:
    tab_relatorio, tab_noticias = st.tabs(["📊 Relatório Dinâmico", "📰 Últimas Notícias"])
    
    with tab_relatorio:
        st.subheader("📋 Painel de Indicadores")
        
        # Carregamento dos dados da Selic para o relatório
        try:
            selic_atual = asyncio.run(obter_selic_atual())
            df_selic = asyncio.run(obter_historico_selic(ultimos_n=12))
        except Exception:
            selic_atual = None
            df_selic = None

        if selic_atual:
            c1, c2 = st.columns(2)
            c1.metric(label="Taxa Selic Atual", value=f"{selic_atual.valor}%")
            c2.metric(label="Última Atualização", value=selic_atual.data)
        
        st.markdown("---")
        
        # Exibição do Gráfico Histórico
        if df_selic is not None and not df_selic.empty:
            st.markdown("### 📈 Histórico Recente da Taxa Selic")
            st.line_chart(df_selic.set_index("data")["valor"], height=250)
            st.caption("Fonte: Banco Central do Brasil (SGS - Série 1178)")
        else:
            st.info("Carregando histórico do Banco Central...")

        # Área reservada para destaques da última análise da IA
        if "ultimo_resumo" in st.session_state:
            st.markdown("---")
            st.markdown("### 📝 Destaque da Análise do Assistente")
            st.info(st.session_state.ultimo_resumo)

    with tab_noticias:
        st.subheader("📰 Manchetes Financeiras")
        with st.spinner("Carregando notícias..."):
            try:
                noticias = asyncio.run(obter_noticias_financeiras(limite=6))
            except Exception:
                noticias = []
        
        with st.container(height=500):
            if noticias:
                for item in noticias:
                    with st.expander(f"📌 {item.titulo}", expanded=False):
                        st.caption(f"Fonte: {item.fonte} | {item.data_publicacao}")
                        st.write(item.resumo)
                        st.markdown(f"[🔗 Ler matéria completa]({item.link})")
            else:
                st.warning("Não foi possível carregar as notícias no momento.")

# ==========================================
# COLUNA DA DIREITA: Chatbot com IA
# ==========================================
with col_chat:
    st.header("💬 Chat de Inteligência Financeira")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    chat_container = st.container(height=500)

    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    if prompt := st.chat_input("Ex: Qual é a Selic hoje e qual o impacto nos investimentos?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        prompt_atual = st.session_state.messages[-1]["content"]
        
        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Consultando dados oficiais e processando resposta..."):
                    try:
                        dados_selic = asyncio.run(obter_selic_atual())
                        contexto = f"Selic Atual: {dados_selic.valor}% na data {dados_selic.data}" if dados_selic else "Dados da Selic indisponíveis."
                    except Exception:
                        contexto = "Dados da Selic indisponíveis no momento."

                    resposta = ask_llama(prompt_atual, contexto)
                    st.markdown(resposta)
                    
                    # Salva no histórico do chat e guarda um trecho para o relatório dinâmico
                    st.session_state.messages.append({"role": "assistant", "content": resposta})
                    st.session_state.ultimo_resumo = resposta[:300] + "..." if len(resposta) > 300 else resposta