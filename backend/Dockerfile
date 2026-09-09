# Use a imagem oficial do Python como base
FROM python:3.12-slim

# Define o diretório de trabalho no container
WORKDIR /app

# Instala o uv (gerenciador de dependências hiper rápido)
RUN pip install uv

# Copia todos os arquivos do projeto para o container
COPY . .

# Cria o ambiente e instala as dependências
RUN uv sync

# Expõe a porta que o FastAPI vai usar
EXPOSE 8000

# Comando para rodar a aplicação
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
