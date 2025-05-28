import json
import os
import requests
from config import logger

class UserConfig:
    def __init__(self):
        self.config_file = 'user_settings.json'
        self.default_settings = {
            'cidade': 'Natal',
            'estado': 'RN',
            'latitude': -5.880287730015802,
            'longitude': -35.24775350308109,
            'cep': '59000-000'
        }
        self.settings = self.load_settings()
    
    def load_settings(self):
        """Carrega as configurações do arquivo"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return self.default_settings
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {e}")
            return self.default_settings
    
    def save_settings(self):
        """Salva as configurações no arquivo"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
            return False
    
    def update_location(self, cep):
        """Atualiza localização baseado no CEP"""
        try:
            # Busca informações do CEP usando a API ViaCEP
            response = requests.get(f"https://viacep.com.br/ws/{cep}/json/")
            if response.status_code == 200:
                data = response.json()
                if 'erro' not in data:
                    # Atualiza cidade e estado
                    self.settings['cidade'] = data['localidade']
                    self.settings['estado'] = data['uf']
                    self.settings['cep'] = cep
                    
                    # Busca coordenadas usando Nominatim (OpenStreetMap)
                    geocode_url = f"https://nominatim.openstreetmap.org/search?city={data['localidade']}&state={data['uf']}&country=Brazil&format=json"
                    headers = {'User-Agent': 'WeatherBot/1.0'}
                    
                    geo_response = requests.get(geocode_url, headers=headers)
                    if geo_response.status_code == 200:
                        geo_data = geo_response.json()
                        if geo_data:
                            self.settings['latitude'] = float(geo_data[0]['lat'])
                            self.settings['longitude'] = float(geo_data[0]['lon'])
                    
                    self.save_settings()
                    return True, "Localização atualizada com sucesso!"
                return False, "CEP não encontrado"
            return False, "Erro ao buscar CEP"
        except Exception as e:
            logger.error(f"Erro ao atualizar localização: {e}")
            return False, f"Erro ao atualizar localização: {str(e)}"
    
    def get_location(self):
        """Retorna as informações de localização atual"""
        return {
            'cidade': self.settings['cidade'],
            'estado': self.settings['estado'],
            'latitude': self.settings['latitude'],
            'longitude': self.settings['longitude'],
            'cep': self.settings['cep']
        }

# Instância global para configurações do usuário
user_config = UserConfig() 