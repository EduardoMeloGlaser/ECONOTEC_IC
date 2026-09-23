import httpx
from pydantic import BaseModel, Field
from typing import Optional

# 1. Validação com Pydantic
class IndicadorEconomico(BaseModel):
    nome: str
    valor: float
    data: str

# 2. Função para buscar a Taxa Selic no SGS / Banco Central
async def obter_selic_atual() -> Optional[IndicadorEconomico]:
    # Código 1178 é o código da Selic diária anualizada no SGS
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