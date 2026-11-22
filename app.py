import asyncio
import re
import time

import httpx
import pandas as pd
import streamlit as st

from api_client import obter_noticias_financeiras
from llm_client import ask_llama

# ==========================================
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="ECONOTEC", page_icon="📈", layout="wide")
st.title("📈 Assistente Econômico & Painel Financeiro")

# ==========================================
# CONSTANTES
# ==========================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Accept": "application/json",
}

INDICADORES = {
    "selic":    {"codigo": 1178,  "nome": "Taxa Selic (% a.a.)"},
    "dolar":    {"codigo": 10813, "nome": "Dólar (compra)"},
    "ipca":     {"codigo": 433,   "nome": "IPCA Mensal (%)"},
    "poupanca": {"codigo": 195,   "nome": "Rendimento Poupança (%)"},
}

# Séries usadas na simulação de R$ 10.000 (taxas por período, próprias para acumular)
SIMULACAO = {
    "selic": {"codigo": 11,  "n": 252, "nome": "Selic (taxa diária)"},
    "ipca":  {"codigo": 433, "n": 120, "nome": "IPCA (inflação acumulada)"},
}


# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def calcular_acumulado_investimento(df: pd.DataFrame, valor_inicial: float = 10000.0) -> pd.DataFrame:
    """Aplica o produto acumulado das taxas (%) sobre o montante inicial."""
    df_calc = df.copy()
    df_calc["fator"] = 1 + (df_calc["valor"] / 100)
    df_calc["Saldo (R$)"] = valor_inicial * df_calc["fator"].cumprod()
    return df_calc


def resumir(texto: str, limite: int = 300) -> str:
    """Remove marcações Markdown e corta o texto sem quebrar palavras."""
    limpo = re.sub(r"[*_#`>]", "", texto)
    limpo = re.sub(r"^\s*[-•◦]\s*", "", limpo, flags=re.MULTILINE)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    if len(limpo) <= limite:
        return limpo
    return limpo[:limite].rsplit(" ", 1)[0] + "..."


def ultima_msg_usuario() -> str:
    """Última mensagem DO USUÁRIO (não a do assistente)."""
    for m in reversed(st.session_state.get("messages", [])):
        if m["role"] == "user":
            return m["content"].lower()
    return ""


def tentar(func, *args):
    """Executa func e retorna (resultado, erro) sem esconder o motivo da falha."""
    try:
        return func(*args), None
    except Exception as e:
        return None, str(e)


# ==========================================
# BUSCA DE DADOS (COM CACHE)
# Sem try/except dentro das funções cacheadas: se der erro,
# a exceção sobe e NADA é guardado em cache.
# ==========================================
def _buscar_bcb(codigo: int, ultimos_n: int, tentativas: int = 3):
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados/ultimos/{ultimos_n}?formato=json"
    ultimo_erro = None
    for i in range(tentativas):
        try:
            r = httpx.get(url, headers=HEADERS, timeout=20.0, follow_redirects=True)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            ultimo_erro = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"Falha ao consultar a série {codigo} do BCB: {ultimo_erro}")


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_selic_atual():
    d = _buscar_bcb(1178, 1)[0]
    return float(d["valor"]), d["data"]


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_historico_indicador(codigo_serie: int, ultimos_n: int = 120) -> pd.DataFrame:
    df = pd.DataFrame(_buscar_bcb(codigo_serie, ultimos_n))
    df["valor"] = df["valor"].astype(float)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    return df.sort_values("data")


@st.cache_data(ttl=900, show_spinner=False)
def carregar_noticias(limite: int = 6):
    noticias = asyncio.run(obter_noticias_financeiras(limite=limite))
    if not noticias:
        raise RuntimeError("Nenhuma notícia retornada pelos feeds.")
    return noticias


# ==========================================
# INDICADOR ESCOLHIDO COM BASE NA ÚLTIMA PERGUNTA DO USUÁRIO
# ==========================================
ultima_msg = ultima_msg_usuario()

if re.search(r"d[óo]lar", ultima_msg):
    chave = "dolar"
elif re.search(r"ipca|infla[çc][ãa]o", ultima_msg):
    chave = "ipca"
elif re.search(r"poupan[çc]a", ultima_msg):
    chave = "poupanca"
else:
    chave = "selic"

cfg = INDICADORES[chave]
quer_simular = bool(re.search(r"r\$\s*\d|10\.?000|renderia|simul|rendimento", ultima_msg))

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
        st.subheader(f"📋 Painel de Indicadores — {cfg['nome']}")

        # --- Selic atual ---
        selic, erro_selic = tentar(carregar_selic_atual)
        valor_selic, data_selic = selic if selic else (None, None)

        if valor_selic is not None:
            c1, c2 = st.columns(2)
            c1.metric("Taxa Selic Atual", f"{valor_selic}%")
            c2.metric("Última Atualização", data_selic)
        else:
            st.warning("Não foi possível carregar a Selic atual do Banco Central.")
            with st.expander("Detalhes do erro"):
                st.code(erro_selic)

        st.markdown("---")

        # --- Gráfico ---
        df, erro = None, None
        if quer_simular and chave in SIMULACAO:
            sim_cfg = SIMULACAO[chave]
            df, erro = tentar(carregar_historico_indicador, sim_cfg["codigo"], sim_cfg["n"])
            if df is not None:
                sim = calcular_acumulado_investimento(df, 10000.0)
                st.markdown(f"### 📈 Simulação: R$ 10.000,00 — {sim_cfg['nome']}")
                st.line_chart(sim.set_index("data")["Saldo (R$)"], height=280)
                final = sim["Saldo (R$)"].iloc[-1]
                st.caption(
                    f"Saldo final estimado: R$ {final:,.2f}. "
                    "Cálculo baseado no acúmulo das taxas do Banco Central (SGS), sem impostos."
                )
        else:
            if quer_simular:
                st.info("A simulação de R$ 10.000 está disponível para Selic e IPCA. Mostrando o histórico.")
            df, erro = tentar(carregar_historico_indicador, cfg["codigo"], 120)
            if df is not None:
                st.markdown(f"### 📈 Histórico Recente: {cfg['nome']}")
                st.line_chart(df.set_index("data")["valor"], height=250)
                st.caption("Fonte: Banco Central do Brasil (SGS)")

        if df is None:
            st.info("Histórico indisponível no momento.")
            with st.expander("Detalhes do erro"):
                st.code(erro)
            if st.button("🔄 Tentar novamente"):
                st.cache_data.clear()
                st.rerun()

        if "ultimo_resumo" in st.session_state:
            st.markdown("---")
            st.markdown("### 📝 Destaque do Relatório")
            st.info(st.session_state.ultimo_resumo)

    with tab_noticias:
        st.subheader("📰 Manchetes Financeiras")
        noticias, erro_noticias = tentar(carregar_noticias, 6)

        with st.container(height=500):
            if noticias:
                for item in noticias:
                    with st.expander(f"📌 {item.titulo}", expanded=False):
                        st.caption(f"Fonte: {item.fonte} | {item.data_publicacao}")
                        st.write(item.resumo)
                        st.markdown(f"[🔗 Ler matéria completa]({item.link})")
            else:
                st.warning("Não foi possível carregar as notícias no momento.")
                if erro_noticias:
                    with st.expander("Detalhes do erro"):
                        st.code(erro_noticias)

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
                    contexto = (
                        f"Selic Atual: {valor_selic}% a.a. na data {data_selic}"
                        if valor_selic is not None
                        else "Dados da Selic indisponíveis temporariamente."
                    )
                    resposta = ask_llama(prompt_atual, contexto)
                    st.markdown(resposta)

                    st.session_state.messages.append({"role": "assistant", "content": resposta})
                    st.session_state.ultimo_resumo = resumir(resposta, 300)
                    st.rerun()
