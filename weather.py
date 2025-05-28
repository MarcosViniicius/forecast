import requests
from datetime import datetime, timedelta
from config import weather_cache, logger
import os

def obter_previsao_tempo(latitude, longitude):
    """
    Obtém a previsão do tempo com cache para evitar muitas requisições
    """
    try:
        # Verifica se há dados em cache válidos
        if (weather_cache['data'] and weather_cache['timestamp'] and 
            datetime.now() - weather_cache['timestamp'] < timedelta(minutes=weather_cache['cache_duration'])):
            logger.info("Usando dados do cache")
            return weather_cache['data']
        
        api_key = os.getenv("WEATHERAPI_KEY")
        if not api_key:
            logger.error("Chave da API do WeatherAPI não configurada")
            return None
        
        url = f"http://api.weatherapi.com/v1/forecast.json?key={api_key}&q={latitude},{longitude}&days=7&aqi=yes&alerts=yes"
        
        logger.info(f"Fazendo requisição para API do tempo: {url}")
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Erro na API: {response.status_code} - {response.text}")
            return None
        
        data = response.json()
        
        # Atualiza o cache
        weather_cache['data'] = data
        weather_cache['timestamp'] = datetime.now()
        
        logger.info("Dados de previsão atualizados com sucesso")
        return data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexão com a API: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao obter previsão: {e}")
        return None

def formatar_condicao_tempo(condicao_en):
    """
    Traduz condições do tempo para português
    """
    traducoes = {
        'Clear': 'Céu limpo',
        'Sunny': 'Ensolarado',
        'Partly cloudy': 'Parcialmente nublado',
        'Cloudy': 'Nublado',
        'Overcast': 'Encoberto',
        'Mist': 'Névoa',
        'Patchy rain possible': 'Possibilidade de chuva isolada',
        'Light rain': 'Chuva leve',
        'Moderate rain': 'Chuva moderada',
        'Heavy rain': 'Chuva forte',
        'Thundery outbreaks possible': 'Possibilidade de trovoadas',
        'Fog': 'Névoa densa'
    }
    return traducoes.get(condicao_en, condicao_en)

def obter_emoji_tempo(condicao):
    """
    Retorna emoji apropriado para a condição do tempo
    """
    emojis = {
        'Clear': '☀️', 'Sunny': '☀️',
        'Partly cloudy': '⛅', 'Cloudy': '☁️',
        'Overcast': '☁️', 'Mist': '🌫️',
        'Fog': '🌫️', 'Light rain': '🌦️',
        'Moderate rain': '🌧️', 'Heavy rain': '⛈️',
        'Thundery outbreaks possible': '⛈️'
    }
    
    for key, emoji in emojis.items():
        if key.lower() in condicao.lower():
            return emoji
    return '🌤️' 