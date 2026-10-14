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

# Função auxiliar para limpar tags HTML do resumo
def limpar_html(texto: str) -> str:
    if not texto:
        return "Sem resumo disponível."
    # Remove tags HTML como <p>, <img>, <a>, etc.
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

async def obter_noticias_financeiras(limite: int = 10) -> List[Noticia]:
    url = "https://g1.globo.com/rss/g1/economia/"
    noticias = []
    
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code == 200:
                root = ET.fromstring(response.text)
                for item in root.findall(".//item")[:limite]:
                    titulo = item.find("title").text if item.find("title") is not None else "Sem título"
                    link = item.find("link").text if item.find("link") is not None else "#"
                    pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                    
                    # Captura o resumo/descrição da notícia
                    desc_elem = item.find("description")
                    raw_desc = desc_elem.text if desc_elem is not None else ""
                    resumo_limpo = limpar_html(raw_desc)

                    noticias.append(
                        Noticia(
                            titulo=titulo,
                            link=link,
                            resumo=resumo_limpo,
                            data_publicacao=pub_date,
                            fonte="G1 Economia"
                        )
                    )
    except Exception as e:
        print(f"Erro ao buscar notícias: {e}")
        
    return noticias