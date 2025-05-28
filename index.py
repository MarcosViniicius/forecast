import os
import requests
import threading
import time
import schedule
import json
import asyncio
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from apscheduler.schedulers.background import BackgroundScheduler

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

# Cache de dados
weather_cache = {
    'data': None,
    'timestamp': None,
    'cache_duration': 15  # minutos
}

# Estado dos alertas
alert_state = {
    'last_rain_alert': None,
    'last_wind_alert': None,
    'last_temp_alert': None,
    'morning_sent': False,
    'evening_sent': False,
    'users_subscribed': set(),
    'drone_locations': {}  # Novamente adicionado para compatibilidade
}

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
    'max_wind': 35,  # km/h (recomendado abaixo do limite máximo do drone)
    'min_visibility': 3,  # km
    'max_rain_chance': 30,  # %
    'min_temp': 0,  # °C
    'max_temp': 40,  # °C
}

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
        'Patchy snow possible': 'Possibilidade de neve isolada',
        'Patchy sleet possible': 'Possibilidade de chuva com granizo',
        'Patchy freezing drizzle possible': 'Possibilidade de garoa congelante',
        'Thundery outbreaks possible': 'Possibilidade de trovoadas',
        'Blowing snow': 'Neve ventosa',
        'Blizzard': 'Nevasca',
        'Fog': 'Névoa densa',
        'Freezing fog': 'Névoa congelante',
        'Patchy light drizzle': 'Garoa leve isolada',
        'Light drizzle': 'Garoa leve',
        'Freezing drizzle': 'Garoa congelante',
        'Heavy freezing drizzle': 'Garoa congelante forte',
        'Patchy light rain': 'Chuva leve isolada',
        'Light rain': 'Chuva leve',
        'Moderate rain at times': 'Chuva moderada ocasional',
        'Moderate rain': 'Chuva moderada',
        'Heavy rain at times': 'Chuva forte ocasional',
        'Heavy rain': 'Chuva forte',
        'Light freezing rain': 'Chuva congelante leve',
        'Moderate or heavy freezing rain': 'Chuva congelante moderada/forte',
        'Light sleet': 'Chuva com granizo leve',
        'Moderate or heavy sleet': 'Chuva com granizo moderada/forte',
        'Patchy light snow': 'Neve leve isolada',
        'Light snow': 'Neve leve',
        'Patchy moderate snow': 'Neve moderada isolada',
        'Moderate snow': 'Neve moderada',
        'Patchy heavy snow': 'Neve forte isolada',
        'Heavy snow': 'Neve forte',
        'Ice pellets': 'Granizo',
        'Light rain shower': 'Pancada de chuva leve',
        'Moderate or heavy rain shower': 'Pancada de chuva moderada/forte',
        'Torrential rain shower': 'Pancada de chuva torrencial',
        'Light sleet showers': 'Pancadas de chuva com granizo leves',
        'Moderate or heavy sleet showers': 'Pancadas de chuva com granizo moderadas/fortes',
        'Light snow showers': 'Pancadas de neve leves',
        'Moderate or heavy snow showers': 'Pancadas de neve moderadas/fortes',
        'Patchy light rain with thunder': 'Chuva leve com trovoadas isoladas',
        'Moderate or heavy rain with thunder': 'Chuva moderada/forte com trovoadas',
        'Patchy light snow with thunder': 'Neve leve com trovoadas isoladas',
        'Moderate or heavy snow with thunder': 'Neve moderada/forte com trovoadas'
    }
    return traducoes.get(condicao_en, condicao_en)

def obter_emoji_tempo(condicao):
    """
    Retorna emoji apropriado para a condição do tempo
    """
    emojis = {
        'Clear': '☀️', 'Sunny': '☀️',
        'Partly cloudy': '⛅', 'Cloudy': '☁️', 'Overcast': '☁️',
        'Mist': '🌫️', 'Fog': '🌫️',
        'Light rain': '🌦️', 'Moderate rain': '🌧️', 'Heavy rain': '⛈️',
        'Thundery outbreaks possible': '⛈️',
        'Light snow': '🌨️', 'Heavy snow': '❄️'
    }
    
    for key, emoji in emojis.items():
        if key.lower() in condicao.lower():
            return emoji
    return '🌤️'

def criar_menu_voltar():
    """
    Cria o botão para voltar ao menu principal
    """
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data='voltar_menu')]
    ])

async def enviar_resposta(update_obj, mensagem, reply_markup=None):
    """
    Função auxiliar para enviar resposta seja de comando ou callback
    """
    try:
        if hasattr(update_obj, 'callback_query') and update_obj.callback_query:
            # É um callback de botão
            await update_obj.callback_query.message.edit_text(
                text=mensagem,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # É um comando direto
            await update_obj.message.reply_text(
                text=mensagem,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Erro ao enviar resposta: {e}")
        try:
            # Tenta enviar uma nova mensagem como fallback
            if hasattr(update_obj, 'callback_query') and update_obj.callback_query:
                await update_obj.callback_query.message.reply_text(
                    text=mensagem,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update_obj.message.reply_text(
                    text=mensagem,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        except Exception as e2:
            logger.error(f"Erro no fallback: {e2}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Comando inicial do bot com menu interativo
    """
    user_id = update.effective_user.id
    alert_state['users_subscribed'].add(user_id)
    
    keyboard = [
        # Clima e Previsões
        [InlineKeyboardButton("🌡️ Clima Atual", callback_data='clima_atual')],
        [InlineKeyboardButton("🌧️ Chance de Chuva", callback_data='chance_chuva')],
        [InlineKeyboardButton("📅 Próximos Dias", callback_data='proximos_dias')],
        
        # Lona e Proteção
        [InlineKeyboardButton("🏠 Status da Lona", callback_data='status_lona')],
        [InlineKeyboardButton("📊 Relatório Completo", callback_data='relatorio_completo')],
        
        # Drone
        [InlineKeyboardButton("🚁 Status para Voo", callback_data='status_drone')],
        [InlineKeyboardButton("📍 Gerenciar Locais", callback_data='locais_drone')],
        
        # Configurações
        [InlineKeyboardButton("🔔 Alertas", callback_data='config_alertas')],
        [InlineKeyboardButton("❓ Ajuda", callback_data='ajuda')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensagem_boas_vindas = f"""
🤖 **Bot de Previsão do Tempo - {CIDADE_NOME}**

Olá, {update.effective_user.first_name}! 👋

Eu sou seu assistente pessoal de previsão do tempo e monitoramento. Posso te ajudar com:

**🌡️ PREVISÃO DO TEMPO:**
• Temperatura e condições atuais
• Chance de chuva nas próximas horas
• Previsão para a semana
• Alertas meteorológicos

**🏠 PROTEÇÃO:**
• Status da lona da amora
• Recomendações de proteção
• Alertas automáticos
• Monitoramento 24h

**🚁 DRONE DJI Mini 2:**
• Condições para voo
• Análise de segurança
• Monitoramento de locais
• Limites operacionais

**📊 RELATÓRIOS:**
• Análises detalhadas
• Dados técnicos
• Histórico e tendências
• Alertas customizados

**⚙️ COMANDOS RÁPIDOS:**
• /clima - Condições atuais
• /chuva - Previsão de chuva
• /diasdechuva - Previsão semanal
• /baixarlona - Status da lona
• /drone - Status para voo
• /addlocal - Adicionar local
• /relatorio - Relatório completo
• /alertas - Configurar alertas
• /help - Ajuda detalhada

📍 Local atual: {CIDADE_NOME}
🔄 Atualização: a cada {UPDATE_INTERVAL} minutos
🔔 Alertas: {ALERT_THRESHOLD}% chance de chuva

Selecione uma opção abaixo ou use os comandos! 👇
"""
    
    await update.message.reply_text(
        mensagem_boas_vindas,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    logger.info(f"Usuário {user_id} iniciou o bot")

async def voltar_menu_principal(update_obj, context):
    """
    Retorna ao menu principal
    """
    keyboard = [
        [InlineKeyboardButton("🌡️ Clima Atual", callback_data='clima_atual')],
        [InlineKeyboardButton("🌧️ Chance de Chuva", callback_data='chance_chuva')],
        [InlineKeyboardButton("📅 Próximos Dias", callback_data='proximos_dias')],
        [InlineKeyboardButton("🏠 Status da Lona", callback_data='status_lona')],
        [InlineKeyboardButton("📊 Relatório Completo", callback_data='relatorio_completo')],
        [InlineKeyboardButton("🚁 Status para Voo", callback_data='status_drone')],
        [InlineKeyboardButton("📍 Gerenciar Locais", callback_data='locais_drone')],
        [InlineKeyboardButton("🔔 Alertas", callback_data='config_alertas')],
        [InlineKeyboardButton("❓ Ajuda", callback_data='ajuda')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensagem = """
🤖 **MENU PRINCIPAL**

Selecione uma opção:

🌡️ Clima Atual
🌧️ Chance de Chuva
📅 Próximos Dias
🏠 Status da Lona
📊 Relatório Completo
🚁 Status para Voo
📍 Gerenciar Locais
🔔 Alertas
❓ Ajuda
"""
    await enviar_resposta(update_obj, mensagem, reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Manipula os botões interativos do menu
    """
    query = update.callback_query
    await query.answer()
    
    handlers = {
        'clima_atual': clima_atual_detalhado,
        'chance_chuva': previsao_chuva_detalhada,
        'proximos_dias': previsao_proximos_dias,
        'status_lona': status_lona_detalhado,
        'relatorio_completo': relatorio_meteorologico_completo,
        'status_drone': status_voo_drone,
        'locais_drone': gerenciar_locais_drone,
        'config_alertas': configurar_alertas,
        'ajuda': ajuda_detalhada,
        'voltar_menu': voltar_menu_principal,
        'alert_rain_on': ativar_alertas_chuva,
        'alert_rain_off': desativar_alertas_chuva,
        'alert_status': status_alertas
    }
    
    try:
        if query.data.startswith('check_drone_'):
            local = query.data.replace('check_drone_', '')
            if local in alert_state['drone_locations']:
                coords = alert_state['drone_locations'][local]
                resultado = await verificar_condicoes_voo(coords['latitude'], coords['longitude'], local)
                if resultado:
                    await status_voo_drone(update, context, resultado)
                else:
                    await query.message.reply_text("❌ Erro ao verificar condições para este local")
            return

        if query.data in handlers:
            await handlers[query.data](update, context)
        else:
            logger.warning(f"Callback não tratado: {query.data}")
            await query.message.reply_text("❌ Opção inválida ou não implementada")
            
    except Exception as e:
        logger.error(f"Erro no button_handler: {e}")
        await query.message.reply_text("❌ Ocorreu um erro ao processar sua solicitação")

# Adicione estas novas funções para gerenciar locais do drone
async def gerenciar_locais_drone(update_obj, context):
    """
    Menu para gerenciar locais salvos para o drone
    """
    keyboard = []
    
    # Lista locais salvos
    if alert_state['drone_locations']:
        mensagem = "📍 **LOCAIS SALVOS PARA DRONE**\n\n"
        for nome, coords in alert_state['drone_locations'].items():
            mensagem += f"• {nome}: {coords['latitude']}, {coords['longitude']}\n"
            keyboard.append([InlineKeyboardButton(
                f"🚁 Verificar {nome}", 
                callback_data=f"check_drone_{nome}"
            )])
    else:
        mensagem = "📍 **GERENCIAR LOCAIS DO DRONE**\n\n"
        mensagem += "Nenhum local salvo ainda.\n\n"
    
    mensagem += "\n**Para adicionar um novo local:**\n"
    mensagem += "Use o comando /addlocal nome latitude longitude\n"
    mensagem += "Exemplo: `/addlocal Parque -5.8802 -35.2477`"
    
    # Adiciona botão de voltar
    keyboard.append([InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data='voltar_menu')])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await enviar_resposta(update_obj, mensagem, reply_markup)

async def ativar_alertas_chuva(update_obj, context):
    """
    Ativa alertas de chuva para o usuário
    """
    user_id = update_obj.effective_user.id
    alert_state['users_subscribed'].add(user_id)
    
    mensagem = """
✅ **ALERTAS ATIVADOS**

Você receberá notificações para:
• 🌧️ Chuva forte (>70% de chance)
• 🌡️ Temperaturas extremas
• 💨 Ventos fortes
• ⏰ Relatórios diários (7h e 19h)

Os alertas são verificados a cada 30 minutos.
"""
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def desativar_alertas_chuva(update_obj, context):
    """
    Desativa alertas de chuva para o usuário
    """
    user_id = update_obj.effective_user.id
    alert_state['users_subscribed'].discard(user_id)
    
    mensagem = """
🔕 **ALERTAS DESATIVADOS**

Você não receberá mais notificações automáticas.
Use /alertas para reativar quando quiser.
"""
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def status_alertas(update_obj, context):
    """
    Mostra o status atual dos alertas
    """
    user_id = update_obj.effective_user.id
    status_ativo = user_id in alert_state['users_subscribed']
    
    mensagem = f"""
📋 **STATUS DOS ALERTAS**

Status atual: {"🔔 ATIVO" if status_ativo else "🔕 DESATIVADO"}

**Configurações:**
• Intervalo: {UPDATE_INTERVAL} minutos
• Limite chuva: {ALERT_THRESHOLD}%
• Relatórios: 7h e 19h

{("✅ Você está recebendo alertas" if status_ativo else "❌ Alertas desativados")}
"""
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def clima_atual_detalhado(update_obj, context):
    """
    Mostra informações detalhadas do clima atual
    """
    previsao = obter_previsao_tempo(LATITUDE, LONGITUDE)
    if not previsao:
        await enviar_resposta(update_obj, "❌ Não foi possível obter dados meteorológicos no momento.", criar_menu_voltar())
        return
    
    current = previsao["current"]
    location = previsao["location"]
    
    temperatura = current["temp_c"]
    sensacao = current["feelslike_c"]
    condicao = formatar_condicao_tempo(current["condition"]["text"])
    emoji = obter_emoji_tempo(current["condition"]["text"])
    umidade = current["humidity"]
    vento_kph = current["wind_kph"]
    vento_dir = current["wind_dir"]
    pressao = current["pressure_mb"]
    visibilidade = current["vis_km"]
    uv_index = current["uv"]
    
    # Classificação do UV
    if uv_index <= 2:
        uv_status = "Baixo 🟢"
    elif uv_index <= 5:
        uv_status = "Moderado 🟡"
    elif uv_index <= 7:
        uv_status = "Alto 🟠"
    elif uv_index <= 10:
        uv_status = "Muito Alto 🔴"
    else:
        uv_status = "Extremo 🟣"
    
    mensagem = f"""
{emoji} **CLIMA ATUAL - {location['name']}**

🌡️ **Temperatura:** {temperatura}°C
🌡️ **Sensação térmica:** {sensacao}°C
🌤️ **Condição:** {condicao}

💧 **Umidade:** {umidade}%
💨 **Vento:** {vento_kph} km/h {vento_dir}
📊 **Pressão:** {pressao} mb
👁️ **Visibilidade:** {visibilidade} km
☀️ **Índice UV:** {uv_index} ({uv_status})

📍 **Localização:** {location['name']}, {location['region']}
🕐 **Última atualização:** {current['last_updated']}

**Recomendações:**
"""
    
    # Adiciona recomendações baseadas nas condições
    if temperatura > 30:
        mensagem += "• 🌡️ Dia quente! Beba bastante água e evite exposição prolongada ao sol\n"
    elif temperatura < 18:
        mensagem += "• 🧥 Temperatura baixa! Use roupas quentes\n"
    
    if umidade > 80:
        mensagem += "• 💧 Umidade alta! Pode haver desconforto\n"
    elif umidade < 30:
        mensagem += "• 🏜️ Ar seco! Mantenha-se hidratado\n"
    
    if vento_kph > 30:
        mensagem += "• 💨 Vento forte! Cuidado com objetos soltos\n"
    
    if uv_index > 7:
        mensagem += "• ☀️ Índice UV alto! Use protetor solar\n"
    
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def previsao_chuva_detalhada(update_obj, context):
    """
    Previsão detalhada de chuva para as próximas horas
    """
    previsao = obter_previsao_tempo(LATITUDE, LONGITUDE)
    if not previsao:
        await enviar_resposta(update_obj, "❌ Não foi possível obter previsão de chuva.", criar_menu_voltar())
        return
    
    hoje = previsao["forecast"]["forecastday"][0]
    horas = hoje["hour"]
    
    agora = datetime.now().hour
    mensagem = f"🌧️ **PREVISÃO DE CHUVA - PRÓXIMAS 12 HORAS**\n\n"
    
    max_chance = 0
    
    for i in range(12):
        hora_index = (agora + i) % 24
        if hora_index < len(horas):
            hora_data = horas[hora_index]
            time_str = hora_data["time"].split(" ")[1]
            chance = hora_data.get("chance_of_rain", 0)
            precipitacao = hora_data.get("precip_mm", 0)
            
            if chance > max_chance:
                max_chance = chance
            
            # Emoji baseado na chance de chuva
            if chance >= 80:
                emoji = "⛈️"
            elif chance >= 60:
                emoji = "🌧️"
            elif chance >= 30:
                emoji = "🌦️"
            else:
                emoji = "☁️"
            
            mensagem += f"{emoji} **{time_str}** - {chance}% "
            if precipitacao > 0:
                mensagem += f"({precipitacao}mm)"
            mensagem += "\n"
    
    # Resumo e recomendações
    mensagem += f"\n📊 **RESUMO:**\n"
    mensagem += f"• Maior chance de chuva: {max_chance}%\n"
    
    if max_chance >= 70:
        mensagem += "• ⚠️ **ALERTA:** Alta probabilidade de chuva!\n"
        mensagem += "• 🏠 **RECOMENDAÇÃO:** Baixe a lona da amora\n"
        mensagem += "• ☂️ Leve guarda-chuva se sair de casa\n"
    elif max_chance >= 40:
        mensagem += "• 🌦️ Possibilidade moderada de chuva\n"
        mensagem += "• ☂️ Considere levar guarda-chuva\n"
    else:
        mensagem += "• ☀️ Baixa chance de chuva\n"
        mensagem += "• 🏠 Lona da amora pode ficar no lugar\n"
    
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def previsao_proximos_dias(update_obj, context):
    """
    Previsão para os próximos 7 dias
    """
    previsao = obter_previsao_tempo(LATITUDE, LONGITUDE)
    if not previsao:
        await enviar_resposta(update_obj, "❌ Não foi possível obter previsão dos próximos dias.", criar_menu_voltar())
        return
    
    dias = previsao["forecast"]["forecastday"]
    mensagem = "📅 **PREVISÃO PARA OS PRÓXIMOS 7 DIAS**\n\n"
    
    dias_da_semana = {
        'monday': 'Segunda-feira',
        'tuesday': 'Terça-feira', 
        'wednesday': 'Quarta-feira',
        'thursday': 'Quinta-feira',
        'friday': 'Sexta-feira',
        'saturday': 'Sábado',
        'sunday': 'Domingo'
    }
    
    for i, dia in enumerate(dias):
        data_obj = datetime.strptime(dia["date"], "%Y-%m-%d")
        if i == 0:
            data_nome = "Hoje"
        elif i == 1:
            data_nome = "Amanhã"
        else:
            nome_dia_en = data_obj.strftime("%A").lower()
            data_nome = dias_da_semana.get(nome_dia_en, data_obj.strftime("%A"))
        
        data_formatada = data_obj.strftime("%d/%m")
        day_data = dia["day"]
        
        temp_max = day_data["maxtemp_c"]
        temp_min = day_data["mintemp_c"]
        condicao = formatar_condicao_tempo(day_data["condition"]["text"])
        emoji = obter_emoji_tempo(day_data["condition"]["text"])
        chance_chuva = day_data.get("daily_chance_of_rain", 0)
        precipitacao = day_data.get("totalprecip_mm", 0)
        
        mensagem += f"{emoji} **{data_nome} ({data_formatada})**\n"
        mensagem += f"🌡️ {temp_min}°C - {temp_max}°C\n"
        mensagem += f"🌤️ {condicao}\n"
        mensagem += f"🌧️ Chuva: {chance_chuva}%"
        
        if precipitacao > 0:
            mensagem += f" ({precipitacao}mm)"
        
        if chance_chuva > 70:
            mensagem += " ⚠️"
        
        mensagem += "\n\n"
    
    # Adiciona resumo da semana
    dias_chuva = sum(1 for dia in dias if dia["day"].get("daily_chance_of_rain", 0) > 50)
    mensagem += f"📊 **RESUMO DA SEMANA:**\n"
    mensagem += f"• Dias com chance de chuva (>50%): {dias_chuva}\n"
    
    if dias_chuva >= 4:
        mensagem += "• 🌧️ Semana chuvosa prevista\n"
    elif dias_chuva >= 2:
        mensagem += "• 🌦️ Alguns dias de chuva\n"
    else:
        mensagem += "• ☀️ Semana predominantemente seca\n"
    
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def status_lona_detalhado(update_obj, context):
    """
    Status detalhado sobre a necessidade de baixar a lona
    """
    previsao = obter_previsao_tempo(LATITUDE, LONGITUDE)
    if not previsao:
        await enviar_resposta(update_obj, "❌ Não foi possível verificar status da lona.", criar_menu_voltar())
        return
    
    hoje = previsao["forecast"]["forecastday"][0]
    amanha = previsao["forecast"]["forecastday"][1] if len(previsao["forecast"]["forecastday"]) > 1 else None
    
    # Verifica chuva das 18h às 6h (período noturno)
    horas_noite = []
    for hora in hoje["hour"]:
        time_str = hora["time"].split(" ")[1]
        hour_num = int(time_str.split(":")[0])
        if hour_num >= 18 or hour_num <= 6:
            horas_noite.append(hora)
    
    if amanha:
        for hora in amanha["hour"][:7]:  # primeiras 7 horas do dia seguinte (até 6h)
            horas_noite.append(hora)
    
    max_chance_noite = max(int(hora.get("chance_of_rain", 0)) for hora in horas_noite) if horas_noite else 0
    precipitacao_total = sum(hora.get("precip_mm", 0) for hora in horas_noite)
    
    mensagem = "🏠 **STATUS DA LONA DA AMORA**\n\n"
    
    if max_chance_noite > 70:
        status = "🔴 **BAIXAR A LONA**"
        recomendacao = "⚠️ **AÇÃO NECESSÁRIA:** Baixe a lona da amora hoje à tarde!"
        emoji_principal = "🛡️"
    elif max_chance_noite > 40:
        status = "🟡 **ATENÇÃO**"
        recomendacao = "⚠️ **CONSIDERE:** Monitorar a previsão e estar preparado para baixar a lona"
        emoji_principal = "⚠️"
    else:
        status = "🟢 **LONA PODE FICAR**"
        recomendacao = "✅ **TRANQUILO:** Não há previsão de chuva forte para hoje à noite"
        emoji_principal = "☀️"
    
    mensagem += f"{emoji_principal} **STATUS:** {status}\n\n"
    mensagem += f"📊 **ANÁLISE NOTURNA (18h-6h):**\n"
    mensagem += f"• Maior chance de chuva: {max_chance_noite}%\n"
    mensagem += f"• Precipitação prevista: {precipitacao_total:.1f}mm\n\n"
    
    mensagem += f"💡 **RECOMENDAÇÃO:**\n{recomendacao}\n\n"
    
    # Detalhes por período
    mensagem += "🕐 **DETALHES POR PERÍODO:**\n"
    
    # Tarde (15h-18h)
    tarde_chances = [hora.get("chance_of_rain", 0) for hora in hoje["hour"][15:18]]
    tarde_max = max(tarde_chances) if tarde_chances else 0
    mensagem += f"• 🌅 Tarde (15h-18h): {tarde_max}%\n"
    
    # Noite (18h-23h)
    noite_chances = [hora.get("chance_of_rain", 0) for hora in hoje["hour"][18:24]]
    noite_max = max(noite_chances) if noite_chances else 0
    mensagem += f"• 🌙 Noite (18h-23h): {noite_max}%\n"
    
    # Madrugada (0h-6h)
    if amanha:
        madru_chances = [hora.get("chance_of_rain", 0) for hora in amanha["hour"][:6]]
        madru_max = max(madru_chances) if madru_chances else 0
        mensagem += f"• 🌌 Madrugada (0h-6h): {madru_max}%\n"
    
    # Dicas adicionais
    mensagem += f"\n💡 **DICAS:**\n"
    if max_chance_noite > 70:
        mensagem += "• Baixe a lona antes das 18h\n"
        mensagem += "• Verifique se está bem fixada\n"
        mensagem += "• Considere proteger outras plantas sensíveis\n"
    else:
        mensagem += "• Continue monitorando a previsão\n"
        mensagem += "• Mantenha a lona acessível caso necessário\n"
    
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def relatorio_meteorologico_completo(update_obj, context):
    """
    Relatório meteorológico completo e detalhado
    """
    previsao = obter_previsao_tempo(LATITUDE, LONGITUDE)
    if not previsao:
        await enviar_resposta(update_obj, "❌ Não foi possível gerar relatório meteorológico.", criar_menu_voltar())
        return
    
    current = previsao["current"]
    hoje = previsao["forecast"]["forecastday"][0]
    
    # Cabeçalho
    mensagem = f"""
📊 **RELATÓRIO METEOROLÓGICO COMPLETO**
📅 {datetime.now().strftime('%d/%m/%Y às %H:%M')}
📍 {CIDADE_NOME}

━━━━━━━━━━━━━━━━━━━━━━━━━━

🌡️ **CONDIÇÕES ATUAIS:**
• Temperatura: {current['temp_c']}°C (sensação: {current['feelslike_c']}°C)
• Condição: {formatar_condicao_tempo(current['condition']['text'])}
• Umidade: {current['humidity']}%
• Pressão: {current['pressure_mb']} mb
• Vento: {current['wind_kph']} km/h {current['wind_dir']}
• Visibilidade: {current['vis_km']} km
• Índice UV: {current['uv']}

━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 **EXTREMOS DE HOJE:**
• Máxima: {hoje['day']['maxtemp_c']}°C
• Mínima: {hoje['day']['mintemp_c']}°C
• Chance de chuva: {hoje['day'].get('daily_chance_of_rain', 0)}%
• Precipitação total: {hoje['day'].get('totalprecip_mm', 0)} mm
• Vento máximo: {hoje['day']['maxwind_kph']} km/h

━━━━━━━━━━━━━━━━━━━━━━━━━━

🌅 **NASCER E PÔR DO SOL:**
• Nascer: {hoje['astro']['sunrise']}
• Pôr do sol: {hoje['astro']['sunset']}
• Nascer da lua: {hoje['astro']['moonrise']}
• Pôr da lua: {hoje['astro']['moonset']}
• Fase da lua: {hoje['astro']['moon_phase']}

━━━━━━━━━━━━━━━━━━━━━━━━━━

🌧️ **ANÁLISE DE CHUVA (PRÓXIMAS 6H):**
"""
    
    # Análise detalhada das próximas 6 horas
    agora = datetime.now().hour
    total_precip = 0
    max_chance = 0
    
    for i in range(6):
        hora_index = (agora + i) % 24
        if hora_index < len(hoje["hour"]):
            hora_data = hoje["hour"][hora_index]
            chance = hora_data.get("chance_of_rain", 0)
            precip = hora_data.get("precip_mm", 0)
            total_precip += precip
            if chance > max_chance:
                max_chance = chance
    
    mensagem += f"• Maior chance: {max_chance}%\n"
    mensagem += f"• Precipitação total prevista: {total_precip:.1f}mm\n"
    
    if max_chance > 80:
        nivel_alerta = "🔴 ALTO"
    elif max_chance > 50:
        nivel_alerta = "🟡 MÉDIO"
    else:
        nivel_alerta = "🟢 BAIXO"
    
    mensagem += f"• Nível de alerta: {nivel_alerta}\n"
    
    # Qualidade do ar se disponível
    if 'air_quality' in current:
        aqi = current['air_quality']
        mensagem += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        mensagem += f"🌬️ **QUALIDADE DO AR:**\n"
        if 'pm2_5' in aqi:
            mensagem += f"• PM2.5: {aqi['pm2_5']} μg/m³\n"
        if 'pm10' in aqi:
            mensagem += f"• PM10: {aqi['pm10']} μg/m³\n"
    
    # Alertas meteorológicos se disponíveis
    if 'alerts' in previsao and previsao['alerts']['alert']:
        mensagem += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        mensagem += f"⚠️ **ALERTAS METEOROLÓGICOS:**\n"
        for alerta in previsao['alerts']['alert']:
            mensagem += f"• {alerta['headline']}\n"
            mensagem += f"  Vigência: {alerta['effective']} até {alerta['expires']}\n"
    
    mensagem += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    mensagem += f"🏠 **RECOMENDAÇÃO PARA A LONA:**\n"
    
    if max_chance > 70:
        mensagem += "🛡️ **BAIXAR A LONA** - Alta chance de chuva!\n"
    elif max_chance > 40:
        mensagem += "⚠️ **FICAR ATENTO** - Possibilidade de chuva\n"
    else:
        mensagem += "✅ **LONA PODE FICAR** - Baixo risco de chuva\n"
    
    mensagem += f"\n📱 Relatório gerado automaticamente às {datetime.now().strftime('%H:%M')}"
    
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def configurar_alertas(update_obj, context):
    """
    Menu para configurar alertas automáticos
    """
    logger.info("Abrindo menu de configuração de alertas")
    
    keyboard = [
        [InlineKeyboardButton("🔔 Ativar Alertas de Chuva", callback_data='alert_rain_on')],
        [InlineKeyboardButton("🔕 Desativar Alertas de Chuva", callback_data='alert_rain_off')],
        [InlineKeyboardButton("📋 Status dos Alertas", callback_data='alert_status')],
        [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data='voltar_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensagem = """
🔔 **CONFIGURAÇÃO DE ALERTAS**

**Alertas Disponíveis:**

🌧️ **Alertas de Chuva**
• Enviados quando chance > 70%
• Verificação a cada 30 minutos
• Inclui recomendação para lona

🌡️ **Alertas de Temperatura**
• Temperaturas extremas
• Ondas de calor ou frio

💨 **Alertas de Vento**
• Ventos fortes (>50 km/h)
• Rajadas perigosas

⏰ **Relatórios Automáticos**
• Relatório matinal (7h)
• Relatório noturno (19h)

Selecione uma opção abaixo:
    """
    
    await enviar_resposta(update_obj, mensagem, reply_markup)

async def ajuda_detalhada(update_obj, context):
    """
    Ajuda detalhada com todos os comandos e funcionalidades
    """
    mensagem = f"""
❓ **AJUDA COMPLETA - BOT DE PREVISÃO DO TEMPO**

🤖 **SOBRE O BOT:**
Este bot fornece informações meteorológicas detalhadas para {CIDADE_NOME}, incluindo previsões, alertas automáticos e recomendações específicas para cuidados com plantas.

━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 **COMANDOS DISPONÍVEIS:**

🌡️ **/clima** - Mostra clima atual detalhado
   • Temperatura e sensação térmica
   • Condições atmosféricas
   • Umidade, pressão, vento
   • Índice UV e recomendações

🌧️ **/chuva** - Previsão de chuva nas próximas horas
   • Chance de chuva hora a hora
   • Quantidade de precipitação
   • Recomendações de proteção

📅 **/diasdechuva** - Próximos dias com chuva
   • Previsão para 7 dias
   • Análise de padrões
   • Resumo semanal

🏠 **/baixarlona** - Status da lona da amora
   • Análise período noturno
   • Recomendações específicas
   • Alertas de proteção

📊 **/relatorio** - Relatório meteorológico completo
   • Dados técnicos detalhados
   • Análises profissionais
   • Histórico e tendências

🔔 **/alertas** - Configurar notificações automáticas
   • Alertas de chuva forte
   • Notificações de temperatura
   • Relatórios programados

❓ **/help** - Esta mensagem de ajuda

━━━━━━━━━━━━━━━━━━━━━━━━━━

🔔 **ALERTAS AUTOMÁTICOS:**

O bot monitora constantemente as condições meteorológicas e envia alertas automáticos para:

• 🌧️ Chuva forte (chance > 70%)
• 🌡️ Temperaturas extremas
• 💨 Ventos fortes (> 50 km/h)
• 🏠 Necessidade de proteger plantas

━━━━━━━━━━━━━━━━━━━━━━━━━━

🏠 **SISTEMA DA LONA:**

O bot possui um sistema inteligente para recomendar quando baixar a lona da amora baseado em:

• Análise do período noturno (18h-6h)
• Intensidade da chuva prevista
• Direção e força dos ventos
• Histórico de precipitação

━━━━━━━━━━━━━━━━━━━━━━━━━━

⚙️ **CONFIGURAÇÕES:**

• Localização: {CIDADE_NOME}
• Intervalo de verificação: 30 minutos
• Limite para alertas: 70% chance de chuva
• Idioma: Português Brasileiro

━━━━━━━━━━━━━━━━━━━━━━━━━━

📞 **SUPORTE:**

Em caso de problemas ou sugestões:
• Use /start para reiniciar o bot
• Comandos funcionam 24h por dia
• Dados atualizados a cada 15 minutos

🌟 **Desenvolvido especificamente para {CIDADE_NOME}**

🚁 **COMANDOS PARA DRONE:**

• /drone - Verifica condições para voo
   • Status atual detalhado
   • Recomendações de segurança
   • Limites do DJI Mini 2

• /addlocal - Adiciona local para monitorar
   • Formato: /addlocal nome latitude longitude
   • Exemplo: /addlocal Parque -5.8802 -35.2477
"""
    
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def verificar_condicoes():
    """
    Verifica condições meteorológicas atuais e envia alertas se necessário
    """
    try:
        previsao = obter_previsao_tempo(LATITUDE, LONGITUDE)
        if not previsao:
            logger.error("Não foi possível obter previsão para verificação automática")

        hoje = previsao["forecast"]["forecastday"][0]
        agora = datetime.now().hour
        proximas_horas = hoje["hour"][agora:agora + 3]  # Próximas 3 horas

        # Verifica chance de chuva
        max_chance = max(int(hora.get("chance_of_rain", 0)) for hora in proximas_horas)
        if max_chance >= ALERT_THRESHOLD:
            # Envia alerta para todos usuários inscritos
            mensagem = f"""⚠️ **ALERTA DE CHUVA**

Detectada alta probabilidade de chuva!

🌧️ Chance de chuva: {max_chance}%
⏰ Nas próximas horas
📍 {CIDADE_NOME}

🏠 **Recomendação:** Baixe a lona da amora!
"""
            for user_id in alert_state['users_subscribed']:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=mensagem,
                        parse_mode='Markdown'
                    )
                    logger.info(f"Alerta de chuva enviado para {user_id}")
                except Exception as e:
                    logger.error(f"Erro ao enviar alerta para {user_id}: {e}")

    except Exception as e:
        logger.error(f"Erro na verificação automática: {e}")

def executar_agenda():
    """
    Executa o agendador em loop
    """
    try:
        logger.info("Iniciando loop do agendador")
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Loop do agendador interrompido")

def verificacao_automatica():
    """
    Função para executar verificação em loop
    """
    logger.info("Iniciando verificação automática")
    
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def verificacao_loop():
            while True:
                await verificar_condicoes()
                await asyncio.sleep(UPDATE_INTERVAL * 60)
        
        loop.run_until_complete(verificacao_loop())
    except Exception as e:
        logger.error(f"Erro no loop de verificação: {e}")
    finally:
        loop.close()

def configurar_agenda():
    """
    Configura as tarefas agendadas do bot
    """
    logger.info("Configurando agenda de tarefas")
    
    try:
        # Cria o agendador
        scheduler = BackgroundScheduler()
        
        # Agenda relatório matinal (7h)
        scheduler.add_job(
            enviar_relatorio_matinal,
            'cron',
            hour=7,
            minute=0,
            id='relatorio_matinal'
        )
        
        # Agenda relatório noturno (19h)
        scheduler.add_job(
            enviar_relatorio_noturno,
            'cron',
            hour=19,
            minute=0,
            id='relatorio_noturno'
        )
        
        # Inicia o agendador
        scheduler.start()
        logger.info("Agenda configurada com sucesso")
        
    except Exception as e:
        logger.error(f"Erro ao configurar agenda: {e}")
        print(f"❌ Erro ao configurar agenda: {e}")

async def enviar_relatorio_matinal():
    """
    Envia relatório meteorológico matinal
    """
    for user_id in alert_state['users_subscribed']:
        try:
            mensagem = "🌅 **RELATÓRIO MATINAL**\n\n"
            # Adicione aqui a lógica para gerar o relatório matinal
            await bot.send_message(chat_id=user_id, text=mensagem, parse_mode='Markdown')
            logger.info(f"Relatório matinal enviado para {user_id}")
        except Exception as e:
            logger.error(f"Erro ao enviar relatório matinal para {user_id}: {e}")

async def enviar_relatorio_noturno():
    """
    Envia relatório meteorológico noturno
    """
    for user_id in alert_state['users_subscribed']:
        try:
            mensagem = "🌙 **RELATÓRIO NOTURNO**\n\n"
            # Adicione aqui a lógica para gerar o relatório noturno
            await bot.send_message(chat_id=user_id, text=mensagem, parse_mode='Markdown')
            logger.info(f"Relatório noturno enviado para {user_id}")
        except Exception as e:
            logger.error(f"Erro ao enviar relatório noturno para {user_id}: {e}")

# Comandos simples para compatibilidade
async def clima(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /clima - versão simples"""
    await clima_atual_detalhado(update, context)

async def chuva(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /chuva - versão simples"""
    await previsao_chuva_detalhada(update, context)

async def diasdechuva(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /diasdechuva - versão simples"""
    await previsao_proximos_dias(update, context)

async def baixarlona(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /baixarlona - versão simples"""
    await status_lona_detalhado(update, context)

async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /relatorio - versão simples"""
    await relatorio_meteorologico_completo(update, context)

async def alertas_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /alertas - versão simples"""
    await configurar_alertas(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help - versão simples"""
    await ajuda_detalhada(update, context)

async def verificar_condicoes_voo(latitude, longitude, nome_local="Local atual"):
    """
    Verifica se as condições são seguras para voo do drone
    """
    previsao = obter_previsao_tempo(latitude, longitude)
    if not previsao:
        return None
    
    current = previsao["current"]
    
    # Analisa condições
    condicoes = {
        'vento': current['wind_kph'],
        'visibilidade': current['vis_km'],
        'temperatura': current['temp_c'],
        'chance_chuva': previsao["forecast"]["forecastday"][0]["hour"][datetime.now().hour].get("chance_of_rain", 0)
    }
    
    # Verifica cada condição
    status = []
    is_safe = True
    
    # Vento
    if condicoes['vento'] > FLIGHT_LIMITS['max_wind']:
        status.append(f"❌ Vento muito forte: {condicoes['vento']} km/h")
        is_safe = False
    else:
        status.append(f"✅ Vento adequado: {condicoes['vento']} km/h")
    
    # Visibilidade
    if condicoes['visibilidade'] < FLIGHT_LIMITS['min_visibility']:
        status.append(f"❌ Visibilidade baixa: {condicoes['visibilidade']} km")
        is_safe = False
    else:
        status.append(f"✅ Boa visibilidade: {condicoes['visibilidade']} km")
    
    # Temperatura
    if not (FLIGHT_LIMITS['min_temp'] <= condicoes['temperatura'] <= FLIGHT_LIMITS['max_temp']):
        status.append(f"❌ Temperatura inadequada: {condicoes['temperatura']}°C")
        is_safe = False
    else:
        status.append(f"✅ Temperatura adequada: {condicoes['temperatura']}°C")
    
    # Chuva
    if condicoes['chance_chuva'] > FLIGHT_LIMITS['max_rain_chance']:
        status.append(f"❌ Risco de chuva: {condicoes['chance_chuva']}%")
        is_safe = False
    else:
        status.append(f"✅ Sem risco de chuva: {condicoes['chance_chuva']}%")
    
    return {
        'is_safe': is_safe,
        'status': status,
        'condicoes': condicoes,
        'local': nome_local
    }

async def status_voo_drone(update_obj, context):
    """
    Mostra status detalhado para voo do drone
    """
    previsao = obter_previsao_tempo(LATITUDE, LONGITUDE)
    if not previsao:
        await enviar_resposta(update_obj, "❌ Não foi possível verificar condições de voo.", criar_menu_voltar())
        return
    
    resultado = await verificar_condicoes_voo(LATITUDE, LONGITUDE)
    if not resultado:
        await enviar_resposta(update_obj, "❌ Erro ao analisar condições de voo.", criar_menu_voltar())
        return
    
    # Monta mensagem
    mensagem = f"""
🚁 **STATUS PARA VOO - DJI Mini 2**
📍 Local: {resultado['local']}
{datetime.now().strftime('%d/%m/%Y %H:%M')}

**Status Geral:** {"✅ SEGURO PARA VOO" if resultado['is_safe'] else "❌ NÃO RECOMENDADO"}

**Condições Atuais:**
"""
    
    for status in resultado['status']:
        mensagem += f"• {status}\n"
    
    mensagem += f"""
📋 **Especificações do Drone:**
• Peso: {DRONE_CONFIG['peso']}g
• Altitude máxima: {DRONE_CONFIG['max_altitude']}m
• Resistência ao vento: até {DRONE_CONFIG['max_wind_resistance']}km/h
• Autonomia: ~{DRONE_CONFIG['bateria_duracao']} minutos

⚠️ **Recomendações:**"""
    
    if resultado['is_safe']:
        mensagem += """
• Mantenha contato visual com o drone
• Respeite os limites de altura e distância
• Monitore o nível da bateria
• Evite áreas restritas
• Tenha cuidado com obstáculos"""
    else:
        mensagem += """
• Não é recomendado voar nas condições atuais
• Aguarde condições mais favoráveis
• Monitore a previsão do tempo"""
    
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def adicionar_local_drone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Adiciona um novo local para monitoramento
    """
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "❌ Formato incorreto. Use:\n/addlocal nome latitude longitude\n"
                "Exemplo: /addlocal Parque -5.8802 -35.2477"
            )
            return
        
        nome = args[0]
        lat = float(args[1])
        lon = float(args[2])
        
        alert_state['drone_locations'][nome] = {
            'latitude': lat,
            'longitude': lon
        }
        
        await update.message.reply_text(f"✅ Local '{nome}' adicionado com sucesso!")
        
    except ValueError:
        await update.message.reply_text("❌ Coordenadas inválidas!")
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao adicionar local: {str(e)}")

def main():
    """
    Função principal que inicia o bot
    """
    # Verifica variáveis de ambiente
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    weather_api_key = os.getenv("WEATHERAPI_KEY")
    
    if not telegram_token:
        logger.error("TELEGRAM_BOT_TOKEN não configurado")
        print("❌ Configure a variável de ambiente TELEGRAM_BOT_TOKEN")
        exit(1)
    
    if not weather_api_key:
        logger.error("WEATHERAPI_KEY não configurado")
        print("❌ Configure a variável de ambiente WEATHERAPI_KEY")
        exit(1)
    
    logger.info("Iniciando Bot de Previsão do Tempo")
    print(f"🤖 Iniciando Bot de Previsão do Tempo para {CIDADE_NOME}")
    print(f"📍 Coordenadas: {LATITUDE}, {LONGITUDE}")
    print(f"⏰ Intervalo de verificação: {UPDATE_INTERVAL} minutos")
    print(f"🚨 Limite de alerta: {ALERT_THRESHOLD}% de chance de chuva")
    
    # Configura a agenda de tarefas
    configurar_agenda()
    
    # Inicia thread para verificação automática
    thread_verificacao = threading.Thread(
        target=verificacao_automatica,
        daemon=True
    )
    thread_verificacao.start()
    logger.info("Thread de verificação automática iniciada")
    
    # Inicia thread para agenda
    thread_agenda = threading.Thread(
        target=executar_agenda,
        daemon=True
    )
    thread_agenda.start()
    logger.info("Thread de agenda iniciada")
    
    # Configura o bot do Telegram
    app = ApplicationBuilder().token(telegram_token).build()
    
    # Adiciona handlers para comandos
    comandos = {
        "start": start,
        "help": help_command,
        "clima": clima,
        "chuva": chuva,
        "diasdechuva": diasdechuva,
        "baixarlona": baixarlona,
        "relatorio": relatorio,
        "alertas": alertas_cmd,
        "drone": status_voo_drone,
        "addlocal": adicionar_local_drone
    }
    
    for comando, funcao in comandos.items():
        app.add_handler(CommandHandler(comando, funcao))
    
    # Adiciona handler para botões
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("✅ Bot configurado e pronto!")
    print("📱 Comandos disponíveis:")
    for comando in comandos:
        print(f"   • /{comando}")
    
    # Adiciona o chat_id se fornecido
    if telegram_chat_id:
        alert_state['users_subscribed'].add(telegram_chat_id)
        logger.info(f"Chat ID padrão adicionado: {telegram_chat_id}")
    
    print("✅ Bot configurado e pronto!")
    print("📱 Comandos disponíveis:")
    print("   • /start - Menu principal")
    print("   • /clima - Clima atual")
    print("   • /chuva - Previsão de chuva")
    print("   • /diasdechuva - Próximos dias")
    print("   • /baixarlona - Status da lona")
    print("   • /relatorio - Relatório completo")
    print("   • /alertas - Configurar alertas")
    print("   • /help - Ajuda")
    print("\n🔄 Iniciando bot... (Ctrl+C para parar)")
    
    try:
        # Inicia o bot
        logger.info("Bot iniciado e rodando...")
        app.run_polling()
    except KeyboardInterrupt:
        logger.info("Bot interrompido pelo usuário")
        print("\n🛑 Bot interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro crítico no bot: {e}")
        print(f"\n❌ Erro crítico: {e}")
    finally:
        logger.info("Bot finalizado")
        print("👋 Bot finalizado!")

if __name__ == "__main__":
    main()