import streamlit as st
import httpx
import pandas as pd
from api_client import obter_noticias_financeiras
from llm_client import ask_llama

# Configuração da página
st.set_page_config(page_title="Assistente Econômico & Painel Financeiro", page_icon="📈", layout="wide")
st.title("📈 Assistente Econômico & Painel Financeiro")

# ==========================================
# FUNÇÕES AUXILIARES DE CÁLCULO FINANCEIRO
# ==========================================
def calcular_acumulado_investimento(df: pd.DataFrame, valor_inicial: float = 10000.0) -> pd.DataFrame:
    """Aplica o produto acumulado sobre a taxa para simular o crescimento do montante inicial em Reais (R$)."""
    df_calc = df.copy()
    df_calc["fator"] = 1 + (df_calc["valor"] / 100)
    df_calc["Saldo (R$)"] = valor_inicial * df_calc["fator"].cumprod()
    return df_calc

# ==========================================
# FUNÇÕES DE BUSCA COM CACHE (Timeout aumentado para 15s)
# ==========================================
@st.cache_data(ttl=3600)  # Guarda o resultado em cache por 1 hora
def carregar_selic_atual():
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1178/dados/ultimos/1?formato=json"
    try:
        response = httpx.get(url, timeout=15.0)  # Aumentado para evitar falha por lentidão da API do BCB
        if response.status_code == 200:
            data = response.json()[0]
            return float(data["valor"]), data["data"]
    except Exception as e:
        print(f"Erro ao buscar Selic atual: {e}")
    return None, None

@st.cache_data(ttl=3600)
def carregar_historico_indicador(codigo_serie: int, ultimos_n: int = 120):
    # Reduzido para 120 registros para agilizar o carregamento da API do BCB
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados/ultimos/{ultimos_n}?formato=json"
    try:
        response = httpx.get(url, timeout=15.0)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            df["valor"] = df["valor"].astype(float)
            df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
            df = df.sort_values("data")
            return df
    except Exception as e:
        print(f"Erro ao buscar histórico do indicador {codigo_serie}: {e}")
    return None

# ==========================================
# DEFINIÇÃO DO INDICADOR COM BASE NO CHAT
# ==========================================
indicador_codigo = 1178  # Padrão: Selic
indicador_nome = "Taxa Selic"
ultima_msg = ""

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

# ==========================================
# LAYOUT EM 2 COLUNAS
# ==========================================
col_painel, col_chat = st.columns([1, 1], gap="large")

# ------------------------------------------
# COLUNA DA ESQUERDA: RELATÓRIO & NOTÍCIAS
# ------------------------------------------
with col_painel:
    tab_relatorio, tab_noticias = st.tabs(["📊 Relatório Dinâmico", "📰 Últimas Notícias"])
    
    with tab_relatorio:
        st.subheader(f"📋 Painel de Indicadores — {indicador_nome}")
        
        # Busca dados da Selic com cache
        valor_selic, data_selic = carregar_selic_atual()
        if valor_selic is not None:
            c1, c2 = st.columns(2)
            c1.metric(label="Taxa Selic Atual", value=f"{valor_selic}%")
            c2.metric(label="Última Atualização", value=data_selic)
        else:
            st.warning("Não foi possível carregar a Selic atual do Banco Central no momento. Tente atualizar a página.")
        
        st.markdown("---")
        
        # Busca histórico recente do indicador
        df_indicador = carregar_historico_indicador(indicador_codigo, ultimos_n=120)
        
        if df_indicador is not None and not df_indicador.empty:
            if "10" in ultima_msg or "10000" in ultima_msg or "10.000" in ultima_msg or "renderia" in ultima_msg:
                df_simulacao = calcular_acumulado_investimento(df_indicador, valor_inicial=10000.0)
                st.markdown(f"### 📈 Simulação: Rendimento de R$ 10.000,00 ({indicador_nome})")
                st.line_chart(df_simulacao.set_index("data")["Saldo (R$)"], height=280)
                st.caption("Cálculo baseado no acúmulo das taxas informadas pelo Banco Central (SGS).")
            else:
                st.markdown(f"### 📈 Histórico Recente: {indicador_nome}")
                st.line_chart(df_indicador.set_index("data")["valor"], height=250)
                st.caption("Fonte: Banco Central do Brasil (SGS)")
        else:
            st.info("Histórico indisponível no momento.")

        if "ultimo_resumo" in st.session_state:
            st.markdown("---")
            st.markdown("### 📝 Destaque do Relatório")
            st.info(st.session_state.ultimo_resumo)

    with tab_noticias:
        st.subheader("📰 Manchetes Financeiras")
        with st.spinner("Carregando notícias..."):
            try:
                import asyncio
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

# ------------------------------------------
# COLUNA DA DIREITA: CHATBOT
# ------------------------------------------
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
                with st.spinner("Consultando IA e gerando resposta..."):
                    contexto = f"Selic Atual: {valor_selic}% na data {data_selic}" if valor_selic else "Dados da Selic indisponíveis temporariamente."

                    resposta = ask_llama(prompt_atual, contexto)
                    st.markdown(resposta)
                    
                    st.session_state.messages.append({"role": "assistant", "content": resposta})
                    st.session_state.ultimo_resumo = resposta[:300] + "..." if len(resposta) > 300 else resposta
                    st.rerun()