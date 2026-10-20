import httpx
import xml.etree.ElementTree as ET
import re
import pandas as pd
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class IndicadorEconomico(BaseModel):
    nome: str
    valor: float
    data: str

class Noticia(BaseModel):
    titulo: str
    link: str
    resumo: Optional[str] = "Sem resumo disponível."
    data_publicacao: Optional[str] = None
    fonte: Optional[str] = None

def limpar_html(texto: str) -> str:
    if not texto:
        return "Sem resumo disponível."
    texto_limpo = re.sub(r'<[^>]+>', '', texto)
    return texto_limpo.strip()

async def obter_selic_atual() -> Optional[IndicadorEconomico]:
    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1178/dados/ultimos/1?formato=json"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()[0]
                return IndicadorEconomico(
                    nome="Taxa Selic",
                    valor=float(data["valor"]),
                    data=data["data"]
                )
        except Exception as e:
            print(f"Erro ao obter Selic atual: {e}")
    return None

async def obter_historico_selic(ultimos_n: int = 12) -> Optional[pd.DataFrame]:
    """Busca os últimos N registros da taxa Selic no SGS/BCB."""
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.1178/dados/ultimos/{ultimos_n}?formato=json"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                df = pd.DataFrame(response.json())
                df["valor"] = df["valor"].astype(float)
                df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
                df = df.sort_values("data")
                return df
        except Exception as e:
            print(f"Erro ao buscar histórico Selic: {e}")
    return None

async def obter_noticias_financeiras(limite: int = 6) -> List[Noticia]:
    # Usando User-Agent realista para evitar bloqueios de scraping em RSS
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    feeds = [
        ("Google News - Economia Brasil", "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=pt-BR&gl=BR&ceid=BR:pt-419"),
        ("InfoMoney - Mercado", "https://www.infomoney.com.br/mercados/feed/"),
        ("Valor Econômico", "https://valor.globo.com/rss/financas/")
    ]
    
    palavras_chave = [
        "ações", "bolsa", "ibovespa", "dólar", "selic", "juros", "inflação", "ipca",
        "lucro", "balanço", "mercado", "banco", "fed", "tesouro", "fundo", "invest"
    ]
    
    noticias = []
    
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=10.0) as client:
        for nome_fonte, url in feeds:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    for item in root.findall(".//item"):
                        titulo = item.find("title").text if item.find("title") is not None else ""
                        link = item.find("link").text if item.find("link") is not None else "#"
                        pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                        
                        desc_elem = item.find("description")
                        raw_desc = desc_elem.text if desc_elem is not None else ""
                        resumo_limpo = limpar_html(raw_desc)

                        texto_analise = f"{titulo} {resumo_limpo}".lower()
                        if any(palavra in texto_analise for palavra in palavras_chave) or "google" in nome_fonte.lower():
                            noticias.append(
                                Noticia(
                                    titulo=titulo,
                                    link=link,
                                    resumo=resumo_limpo if resumo_limpo else "Clique no link para ler a matéria completa.",
                                    data_publicacao=pub_date[:16] if pub_date else "Recente",
                                    fonte=nome_fonte
                                )
                            )
                        if len(noticias) >= limite:
                            break
            except Exception as e:
                print(f"Erro ao carregar feed {nome_fonte}: {e}")
                
            if len(noticias) >= limite:
                break
                
    return noticias