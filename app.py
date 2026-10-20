import streamlit as st
import asyncio
from api_client import obter_selic_atual, obter_historico_indicador, obter_noticias_financeiras
from llm_client import ask_llama

st.set_page_config(page_title="Assistente Econômico & Painel Financeiro", page_icon="📈", layout="wide")
st.title("📈 Assistente Econômico & Painel Financeiro")

col_painel, col_chat = st.columns([1, 1], gap="large")

# Identifica qual indicador carregar com base na última mensagem do utilizador
indicador_codigo = 1178 # Padrão: Selic
indicador_nome = "Taxa Selic"

if "messages" in st.session_state and st.session_state.messages:
    ultima_msg = st.session_state.messages[-1]["content"].lower()
    if "dólar" in ultima_msg or "dolar" in ultima_msg:
        indicador_codigo = 10813
        indicador_nome = "Dólar (PTAX)"
    elif "ipca" in ultima_msg or "inflação" in ultima_msg or "inflacao" in ultima_msg:
        indicador_codigo = 433
        indicador_nome = "IPCA Mensal (%)"
    elif "poupança" in ultima_msg or "poupanca" in ultima_msg:
        indicador_codigo = 195
        indicador_nome = "Rendimento Poupança (%)"

with col_painel:
    tab_relatorio, tab_noticias = st.tabs(["📊 Relatório Dinâmico", "📰 Últimas Notícias"])
    
    with tab_relatorio:
        st.subheader(f"📋 Painel de Indicadores — {indicador_nome}")
        
        try:
            selic_atual = asyncio.run(obter_selic_atual())
            df_indicador = asyncio.run(obter_historico_indicador(indicador_codigo, ultimos_n=12))
        except Exception:
            selic_atual = None
            df_indicador = None

        if selic_atual:
            c1, c2 = st.columns(2)
            c1.metric(label="Taxa Selic Atual", value=f"{selic_atual.valor}%")
            c2.metric(label="Última Atualização", value=selic_atual.data)
        
        st.markdown("---")
        
        if df_indicador is not None and not df_indicador.empty:
            st.markdown(f"### 📈 Histórico Recente: {indicador_nome}")
            st.line_chart(df_indicador.set_index("data")["valor"], height=250)
            st.caption("Fonte: Banco Central do Brasil (SGS)")
        else:
            st.info("Carregando histórico do indicador...")

        if "ultimo_resumo" in st.session_state:
            st.markdown("---")
            st.markdown("### 📝 Destaque do Relatório")
            st.info(st.session_state.ultimo_resumo)

    with tab_noticias:
        # Conteúdo das Notícias...
        pass