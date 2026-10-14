import httpx
import xml.etree.ElementTree as ET
import re
from pydantic import BaseModel
from typing import Optional, List

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
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            data = response.json()[0]
            return IndicadorEconomico(
                nome="Taxa Selic",
                valor=float(data["valor"]),
                data=data["data"]
            )
    return None

async def obter_noticias_financeiras(limite: int = 8) -> List[Noticia]:
    # Feeds especializados em mercado e finanças
    feeds = [
        ("InfoMoney - Mercado", "https://www.infomoney.com.br/mercados/feed/"),
        ("InfoMoney - Economia", "https://www.infomoney.com.br/economia/feed/"),
        ("Valor Econômico", "https://valor.globo.com/rss/financas/")
    ]
    
    # Palavras-chave para descartar notícias que não tenham impacto financeiro/econômico direto
    palavras_chave_financeiras = [
        "açõ", "bolsa", "ibovespa", "dólar", "selic", "juros", "inflaçõ", "ipca",
        "lucro", "balanço", "mercado", "banco", "fed", "tesouro", "fundo", "invest"
    ]
    
    noticias = []
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=10.0) as client:
        for nome_fonte, url in feeds:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    root = ET.fromstring(response.text)
                    for item in root.findall(".//item"):
                        titulo = item.find("title").text if item.find("title") is not None else ""
                        link = item.find("link").text if item.find("link") is not None else "#"
                        pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                        
                        desc_elem = item.find("description")
                        raw_desc = desc_elem.text if desc_elem is not None else ""
                        resumo_limpo = limpar_html(raw_desc)

                        # Filtra apenas notícias relevantes ao mercado/investimentos
                        texto_analise = f"{titulo} {resumo_limpo}".lower()
                        if any(palavra in texto_analise for palavra in palavras_chave_financeiras):
                            noticias.append(
                                Noticia(
                                    titulo=titulo,
                                    link=link,
                                    resumo=resumo_limpo if resumo_limpo else "Clique no link para ler a notícia completa.",
                                    data_publicacao=pub_date[:16] if pub_date else "Recente",
                                    fonte=nome_fonte
                                )
                            )
                        if len(noticias) >= limite:
                            break
            except Exception as e:
                print(f"Erro ao buscar feed {nome_fonte}: {e}")
                
            if len(noticias) >= limite:
                break
                
    return noticias