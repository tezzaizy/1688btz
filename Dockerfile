FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy

WORKDIR /app

COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python", "-m", "bot.main"]