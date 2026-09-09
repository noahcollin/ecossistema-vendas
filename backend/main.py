from fastapi import FastAPI

app = FastAPI(
    title="Ecossistema de Vendas Autônomo API",
    description="Core Backend para gerenciamento da máquina de estados de leads",
    version="1.0.0"
)

@app.get("/")
async def root():
    return {"message": "API do Ecossistema de Vendas operante!"}
