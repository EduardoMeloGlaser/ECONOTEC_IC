import asyncio
import re
import time
from datetime import date, timedelta

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
    "selic":    {"codigo": 1178,  "nome": "Taxa Selic (% a.a.)",     "pre": "",    "suf": "%"},
    "dolar":    {"codigo": 10813, "nome": "Dólar (compra)",          "pre": "R$ ", "suf": ""},
    "ipca":     {"codigo": 433,   "nome": "IPCA Mensal (%)",         "pre": "",    "suf": "%"},
    "poupanca": {"codigo": 195,   "nome": "Rendimento Poupança (%)", "pre": "",    "suf": "%"},
}

# Séries com taxa POR PERÍODO, próprias para acumular na simulação de R$ 10.000
SIMULACAO = {
    "selic": {"codigo": 11,  "nome": "Selic (taxa diária)"},
    "ipca":  {"codigo": 433, "nome": "IPCA (inflação acumulada)"},
}


# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================
def calcular_acumulado_investimento(df: pd.DataFrame, valor_inicial: float = 10000.0) -> pd.DataFrame:
    df_calc = df.copy()
    df_calc["fator"] = 1 + (df_calc["valor"] / 100)
    df_calc["Saldo (R$)"] = valor_inicial * df_calc["fator"].cumprod()
    return df_calc


def resumir(texto: str, limite: int = 300) -> str:
    limpo = re.sub(r"[*_#`>]", "", texto)
    limpo = re.sub(r"^\s*[-•◦]\s*", "", limpo, flags=re.MULTILINE)
    limpo = re.sub(r"\s+", " ", limpo).strip()
    if len(limpo) <= limite:
        return limpo
    return limpo[:limite].rsplit(" ", 1)[0] + "..."


def ultima_msg_usuario() -> str:
    for m in reversed(st.session_state.get("messages", [])):
        if m["role"] == "user":
            return m["content"].lower()
    return ""


def tentar(func, *args):
    try:
        return func(*args), None
    except Exception as e:
        return None, str(e)


def detectar_periodo(msg: str):
    """Lê o período pedido na pergunta. Retorna (inicio, fim, limitado_a_10_anos)."""
    hoje = date.today()
    fim = hoje
    inicio = date(hoje.year - 5, hoje.month, 1)  # padrão: últimos 5 anos

    m = re.search(r"\b(19[89]\d|20\d{2})\s*(?:a|até|ate|-|–|e)\s*(19[89]\d|20\d{2})\b", msg)
    if m:
        a, b = sorted((int(m.group(1)), int(m.group(2))))
        inicio, fim = date(a, 1, 1), min(date(b, 12, 31), hoje)
    else:
        m = re.search(r"desde\s+(?:o\s+ano\s+de\s+|o\s+ano\s+|janeiro\s+de\s+)?(19[89]\d|20\d{2})", msg)
        if m:
            inicio = date(int(m.group(1)), 1, 1)
        else:
            m = re.search(r"(\d+)\s*anos?", msg)
            if m:
                inicio = date(hoje.year - min(int(m.group(1)), 30), hoje.month, 1)
            else:
                m = re.search(r"(\d+)\s*mes(?:es)?", msg)
                if m:
                    inicio = hoje - timedelta(days=30 * int(m.group(1)))

    inicio = max(inicio, date(1995, 1, 1))
    if inicio >= fim:
        inicio, fim = date(hoje.year - 5, hoje.month, 1), hoje

    # A API do BCB limita séries diárias a janelas de 10 anos
    limite = date(fim.year - 10, fim.month, 1)
    limitado = inicio < limite
    if limitado:
        inicio = limite
    return inicio, fim, limitado


# ==========================================
# BUSCA DE DADOS (COM CACHE)
# Sem try/except nas funções cacheadas: erro => nada é guardado em cache.
# ==========================================
def _buscar_bcb(codigo: int, ini: str, fim: str, tentativas: int = 3):
    base = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    urls = [
        f"{base}?formato=json&dataInicial={ini}&dataFinal={fim}",  # principal: intervalo de datas
        f"{base}/ultimos/120?formato=json",                         # alternativa
    ]
    ultimo_erro = "sem resposta"
    for i in range(tentativas):
        for url in urls:
            try:
                r = httpx.get(url, headers=HEADERS, timeout=25.0, follow_redirects=True)
                if r.status_code == 200:
                    dados = r.json()
                    if dados:
                        return dados
                    ultimo_erro = "a série retornou vazia para esse período"
                else:
                    ultimo_erro = f"HTTP {r.status_code}: {r.text[:200]}"
            except Exception as e:
                ultimo_erro = f"{type(e).__name__}: {e}"
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"Série {codigo} do BCB — {ultimo_erro}")


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_selic_atual():
    hoje = date.today()
    d = _buscar_bcb(1178, (hoje - timedelta(days=30)).strftime("%d/%m/%Y"), hoje.strftime("%d/%m/%Y"))[-1]
    return float(d["valor"]), d["data"]


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_historico_indicador(codigo_serie: int, ini: str, fim: str) -> pd.DataFrame:
    df = pd.DataFrame(_buscar_bcb(codigo_serie, ini, fim))
    df["valor"] = df["valor"].astype(float)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df = df.sort_values("data")
    d_ini, d_fim = pd.to_datetime(ini, format="%d/%m/%Y"), pd.to_datetime(fim, format="%d/%m/%Y")
    df = df[(df["data"] >= d_ini) & (df["data"] <= d_fim)]
    if df.empty:
        raise RuntimeError(f"Sem dados da série {codigo_serie} entre {ini} e {fim}.")
    return df


@st.cache_data(ttl=900, show_spinner=False)
def carregar_noticias(limite: int = 6):
    noticias = asyncio.run(obter_noticias_financeiras(limite=limite))
    if not noticias:
        raise RuntimeError("Nenhuma notícia retornada pelos feeds.")
    return noticias


def montar_contexto(chave: str, df, inicio: date, fim: date, selic) -> str:
    """Resume os dados do painel para a IA responder com os MESMOS números do gráfico."""
    cfg = INDICADORES[chave]
    linhas = [f"Indicador exibido no painel: {cfg['nome']}.",
              f"Período: {inicio.strftime('%d/%m/%Y')} a {fim.strftime('%d/%m/%Y')}."]
    if selic:
        linhas.append(f"Selic atual: {selic[0]}% a.a. em {selic[1]}.")

    if df is None or df.empty:
        linhas.append("Os dados do indicador estão indisponíveis agora: não cite números exatos.")
        return "\n".join(linhas)

    p, u = df.iloc[0], df.iloc[-1]
    linhas.append(f"Primeiro valor: {p['valor']:.4f} ({p['data']:%d/%m/%Y}). Último valor: {u['valor']:.4f} ({u['data']:%d/%m/%Y}).")
    imin, imax = df["valor"].idxmin(), df["valor"].idxmax()
    linhas.append(f"Mínimo: {df.loc[imin, 'valor']:.4f} ({df.loc[imin, 'data']:%m/%Y}). "
                  f"Máximo: {df.loc[imax, 'valor']:.4f} ({df.loc[imax, 'data']:%m/%Y}).")

    anos = df.groupby(df["data"].dt.year)["valor"]
    if chave == "ipca":
        por_ano = anos.apply(lambda s: ((1 + s / 100).prod() - 1) * 100)
        linhas.append("IPCA acumulado por ano (%; anos incompletos são parciais): "
                      + "; ".join(f"{a}: {v:.2f}" for a, v in por_ano.items()))
    else:
        por_ano = anos.last()
        linhas.append("Último valor de cada ano: " + "; ".join(f"{a}: {v:.4f}" for a, v in por_ano.items()))

    linhas.append("Use SOMENTE esses números para dados do indicador; não invente valores.")
    return "\n".join(linhas)


# ==========================================
# INDICADOR E PERÍODO ESCOLHIDOS PELA ÚLTIMA PERGUNTA DO USUÁRIO
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
inicio, fim, limitado = detectar_periodo(ultima_msg)
quer_simular = bool(re.search(r"r\$\s*\d|10\.?000|renderia|simul|rendimento", ultima_msg))
fmt = lambda d: d.strftime("%d/%m/%Y")

# ==========================================
# LAYOUT EM 2 COLUNAS
# ==========================================
col_painel, col_chat = st.columns([1, 1], gap="large")

df = None  # dados exibidos no painel (também enviados à IA)

with col_painel:
    tab_relatorio, tab_noticias = st.tabs(["📊 Relatório Dinâmico", "📰 Últimas Notícias"])

    with tab_relatorio:
        st.subheader(f"📋 Painel de Indicadores — {cfg['nome']}")
        st.caption(f"Período analisado: {fmt(inicio)} a {fmt(fim)}")
        if limitado:
            st.caption("⚠️ Período limitado a 10 anos, que é o máximo da API do Banco Central.")

        selic, erro_selic = tentar(carregar_selic_atual)

        simulando = quer_simular and chave in SIMULACAO
        if quer_simular and not simulando:
            st.info("A simulação de R$ 10.000 está disponível para Selic e IPCA. Mostrando o histórico.")

        codigo_grafico = SIMULACAO[chave]["codigo"] if simulando else cfg["codigo"]
        df, erro = tentar(carregar_historico_indicador, codigo_grafico, fmt(inicio), fmt(fim))

        if df is not None:
            # --- Métricas do indicador escolhido ---
            if simulando:
                sim = calcular_acumulado_investimento(df, 10000.0)
                final = sim["Saldo (R$)"].iloc[-1]
                c1, c2, c3 = st.columns(3)
                c1.metric("Investido", "R$ 10.000,00")
                c2.metric("Saldo estimado", f"R$ {final:,.2f}")
                c3.metric("Rendimento", f"{(final / 10000 - 1) * 100:.2f}%")
                st.markdown(f"### 📈 Simulação: R$ 10.000,00 — {SIMULACAO[chave]['nome']}")
                st.line_chart(sim.set_index("data")["Saldo (R$)"], height=280)
                st.caption("Acúmulo das taxas do Banco Central (SGS), sem impostos ou taxas.")
            else:
                ult, pri = df.iloc[-1], df.iloc[0]
                if chave == "dolar":
                    delta = f"{(ult['valor'] / pri['valor'] - 1) * 100:+.2f}% no período"
                else:
                    delta = f"{ult['valor'] - pri['valor']:+.2f} p.p. no período"
                c1, c2 = st.columns(2)
                c1.metric(f"{cfg['nome']} — atual", f"{cfg['pre']}{ult['valor']:.2f}{cfg['suf']}", delta)
                c2.metric("Última atualização", f"{ult['data']:%d/%m/%Y}")
                st.markdown(f"### 📈 Histórico: {cfg['nome']}")
                st.line_chart(df.set_index("data")["valor"], height=250)
                st.caption("Fonte: Banco Central do Brasil (SGS)")
        else:
            st.info("Histórico indisponível no momento.")
            with st.expander("Detalhes do erro", expanded=True):
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

    if prompt := st.chat_input("Ex: Como o IPCA evoluiu desde 2020?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.rerun()

    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        prompt_atual = st.session_state.messages[-1]["content"]

        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Consultando IA e gerando resposta..."):
                    contexto = montar_contexto(chave, df, inicio, fim, selic)
                    resposta = ask_llama(prompt_atual, contexto)
                    st.markdown(resposta)

                    st.session_state.messages.append({"role": "assistant", "content": resposta})
                    st.session_state.ultimo_resumo = resumir(resposta, 300)
                    st.rerun()
