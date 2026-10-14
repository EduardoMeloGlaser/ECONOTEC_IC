import httpx
import feedparser
from pydantic import BaseModel, Field
from typing import Optional, List

# 1. Validação com Pydantic
class IndicadorEconomico(BaseModel):
    nome: str
    valor: float
    data: str

class Noticia(BaseModel):
    titulo: str
    link: str
    data_publicacao: Optional[str] = None
    fonte: Optional[str] = None

# 2. Função para buscar a Taxa Selic no SGS / Banco Central
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

# 3. Função para buscar notícias financeiras reais via RSS
def obter_noticias_financeiras(limite: int = 10) -> List[Noticia]:
    # Exemplo utilizando o Feed RSS de Economia do G1 / InfoMoney
    rss_url = "https://g1.globo.com/rss/g1/economia/"
    feed = feedparser.parse(rss_url)
    
    noticias = []
    for entry in feed.entries[:limite]:
        noticias.append(
            Noticia(
                titulo=entry.title,
                link=entry.link,
                data_publicacao=getattr(entry, 'published', 'Data recente'),
                fonte="G1 Economia"
            )
        )
    return noticias