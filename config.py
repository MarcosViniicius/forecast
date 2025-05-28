import os
import logging

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot_weather.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configurações principais
LATITUDE = -5.880287730015802
LONGITUDE = -35.24775350308109
CIDADE_NOME = "Natal, RN"
UPDATE_INTERVAL = 30  # minutos para verificar previsão
ALERT_THRESHOLD = 70  # % de chance de chuva para alertas

# Configurações do Drone
DRONE_CONFIG = {
    'modelo': 'DJI Mini 2',
    'peso': 249,  # gramas
    'max_altitude': 120,  # metros
    'max_wind_resistance': 38,  # km/h
    'min_temp_operation': 0,  # °C
    'max_temp_operation': 40,  # °C
    'max_distance': 10000,  # metros
    'bateria_duracao': 31  # minutos
}

# Limites de segurança para voo
FLIGHT_LIMITS = {
    'max_wind': 35,  # km/h
    'min_visibility': 3,  # km
    'max_rain_chance': 30,  # %
    'min_temp': 0,  # °C
    'max_temp': 40,  # °C
}

# Estado dos alertas
alert_state = {
    'last_rain_alert': None,
    'last_wind_alert': None,
    'last_temp_alert': None,
    'morning_sent': False,
    'evening_sent': False,
    'users_subscribed': set(),
    'drone_locations': {}
}

# Cache de dados
weather_cache = {
    'data': None,
    'timestamp': None,
    'cache_duration': 15  # minutos
} 