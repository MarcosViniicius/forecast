from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from config import CIDADE_NOME, alert_state, LATITUDE, LONGITUDE, DRONE_CONFIG, FLIGHT_LIMITS
from weather import obter_previsao_tempo, formatar_condicao_tempo, obter_emoji_tempo
from utils import enviar_resposta, criar_menu_voltar, criar_menu_principal
from user_config import user_config

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    user_id = update.effective_user.id
    alert_state['users_subscribed'].add(user_id)
    await show_main_menu(update.message)

async def show_main_menu(message_obj):
    """Mostra o menu principal"""
    location = user_config.get_location()
    
    mensagem = f"""
🤖 **Bot de Previsão do Tempo - {location['cidade']}/{location['estado']}**

**COMANDOS DISPONÍVEIS:**
• `/clima` - Condições atuais
• `/chuva` - Previsão de chuva
• `/diasdechuva` - Previsão semanal
• `/baixarlona` - Status da lona
• `/drone` - Status para voo
• `/relatorio` - Relatório completo
• `/alertas` - Configurar alertas
• `/config` - Configurar localização
• `/cep` - Atualizar CEP
• `/help` - Ajuda detalhada

📍 Local atual: {location['cidade']}/{location['estado']}
🏷️ CEP: {location['cep']}

Selecione uma opção abaixo! 👇
"""
    
    keyboard = [
        [InlineKeyboardButton("🌡️ Clima Atual", callback_data='clima_atual'),
         InlineKeyboardButton("🌧️ Chance de Chuva", callback_data='chance_chuva')],
        [InlineKeyboardButton("📅 Próximos Dias", callback_data='proximos_dias'),
         InlineKeyboardButton("🏠 Status da Lona", callback_data='status_lona')],
        [InlineKeyboardButton("🚁 Status para Voo", callback_data='status_drone'),
         InlineKeyboardButton("📊 Relatório", callback_data='relatorio')],
        [InlineKeyboardButton("⚙️ Configurações", callback_data='config'),
         InlineKeyboardButton("🔔 Alertas", callback_data='alertas_config')],
        [InlineKeyboardButton("❓ Ajuda", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message_obj.reply_text(mensagem, reply_markup=reply_markup, parse_mode='Markdown')

async def chance_chuva_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para chance de chuva"""
    location = user_config.get_location()
    previsao = obter_previsao_tempo(location['latitude'], location['longitude'])
    
    if not previsao:
        await enviar_resposta(update, "❌ Não foi possível obter previsão de chuva.", criar_menu_voltar())
        return
    
    hoje = previsao["forecast"]["forecastday"][0]
    horas = hoje["hour"]
    agora = datetime.now().hour
    
    mensagem = f"🌧️ **PREVISÃO DE CHUVA - PRÓXIMAS 6 HORAS**\n\n"
    
    for i in range(6):
        hora_index = (agora + i) % 24
        if hora_index < len(horas):
            hora_data = horas[hora_index]
            time_str = hora_data["time"].split(" ")[1]
            chance = hora_data.get("chance_of_rain", 0)
            precipitacao = hora_data.get("precip_mm", 0)
            
            emoji = "⛈️" if chance >= 70 else "🌧️" if chance >= 30 else "☁️"
            mensagem += f"{emoji} **{time_str}** - {chance}% "
            if precipitacao > 0:
                mensagem += f"({precipitacao}mm)"
            mensagem += "\n"
    
    await enviar_resposta(update, mensagem, criar_menu_voltar())

async def proximos_dias_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para próximos dias"""
    location = user_config.get_location()
    previsao = obter_previsao_tempo(location['latitude'], location['longitude'])
    
    if not previsao:
        await enviar_resposta(update, "❌ Não foi possível obter previsão dos próximos dias.", criar_menu_voltar())
        return
    
    dias = previsao["forecast"]["forecastday"]
    mensagem = f"📅 **PREVISÃO PARA OS PRÓXIMOS DIAS - {location['cidade']}/{location['estado']}**\n\n"
    
    for i, dia in enumerate(dias[:3]):  # Mostra apenas 3 dias
        data = datetime.strptime(dia["date"], "%Y-%m-%d")
        nome_dia = "Hoje" if i == 0 else "Amanhã" if i == 1 else data.strftime("%A")
        
        day = dia["day"]
        condicao = formatar_condicao_tempo(day["condition"]["text"])
        emoji = obter_emoji_tempo(day["condition"]["text"])
        
        mensagem += f"{emoji} **{nome_dia}**\n"
        mensagem += f"🌡️ {day['mintemp_c']}°C - {day['maxtemp_c']}°C\n"
        mensagem += f"🌧️ Chuva: {day.get('daily_chance_of_rain', 0)}%\n"
        mensagem += f"💨 Vento: {day['maxwind_kph']} km/h\n\n"
    
    await enviar_resposta(update, mensagem, criar_menu_voltar())

async def status_lona_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para status da lona"""
    location = user_config.get_location()
    previsao = obter_previsao_tempo(location['latitude'], location['longitude'])
    
    if not previsao:
        await enviar_resposta(update, "❌ Não foi possível verificar status da lona.", criar_menu_voltar())
        return
    
    hoje = previsao["forecast"]["forecastday"][0]
    proximas_horas = hoje["hour"][datetime.now().hour:]
    max_chance = max(hora.get("chance_of_rain", 0) for hora in proximas_horas)
    
    mensagem = f"""
🏠 **STATUS DA LONA - {location['cidade']}/{location['estado']}**

{'🔴 ALERTA: Recomendado baixar a lona!' if max_chance >= 70 else '🟢 Lona pode ficar no lugar'}

**Previsão:**
• Chance máxima de chuva: {max_chance}%
• Período: Próximas {len(proximas_horas)} horas

**Recomendação:**
{'⚠️ Baixe a lona para evitar danos!' if max_chance >= 70 else '✅ Não há necessidade de baixar a lona no momento.'}
"""
    
    await enviar_resposta(update, mensagem, criar_menu_voltar())

async def clima_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /clima"""
    await clima_atual_detalhado(update, context)

async def clima_atual_detalhado(update_obj, context):
    """Mostra informações detalhadas do clima atual"""
    location = user_config.get_location()
    previsao = obter_previsao_tempo(location['latitude'], location['longitude'])
    
    if not previsao:
        await enviar_resposta(update_obj, "❌ Não foi possível obter dados meteorológicos no momento.", criar_menu_voltar())
        return
    
    current = previsao["current"]
    
    temperatura = current["temp_c"]
    sensacao = current["feelslike_c"]
    condicao = formatar_condicao_tempo(current["condition"]["text"])
    emoji = obter_emoji_tempo(current["condition"]["text"])
    
    mensagem = f"""
{emoji} **CLIMA ATUAL - {location['cidade']}/{location['estado']}**

🌡️ **Temperatura:** {temperatura}°C
🌡️ **Sensação térmica:** {sensacao}°C
🌤️ **Condição:** {condicao}

💧 **Umidade:** {current['humidity']}%
💨 **Vento:** {current['wind_kph']} km/h {current['wind_dir']}
👁️ **Visibilidade:** {current['vis_km']} km

📍 **Localização:** {location['cidade']}, {location['estado']}
🕐 **Última atualização:** {current['last_updated']}
"""
    
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def drone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /drone"""
    await status_voo_drone(update, context)

async def status_voo_drone(update_obj, context):
    """Status para voo do drone"""
    location = user_config.get_location()
    previsao = obter_previsao_tempo(location['latitude'], location['longitude'])
    
    if not previsao:
        await enviar_resposta(update_obj, "❌ Não foi possível verificar condições de voo.", criar_menu_voltar())
        return
    
    current = previsao["current"]
    
    vento_ok = current['wind_kph'] <= FLIGHT_LIMITS['max_wind']
    visibilidade_ok = current['vis_km'] >= FLIGHT_LIMITS['min_visibility']
    temp_ok = FLIGHT_LIMITS['min_temp'] <= current['temp_c'] <= FLIGHT_LIMITS['max_temp']
    
    is_safe = vento_ok and visibilidade_ok and temp_ok
    
    mensagem = f"""
🚁 **STATUS PARA VOO - DJI Mini 2**
📍 Local: {location['cidade']}/{location['estado']}
{datetime.now().strftime('%d/%m/%Y %H:%M')}

**Status Geral:** {"✅ SEGURO PARA VOO" if is_safe else "❌ NÃO RECOMENDADO"}

**Condições Atuais:**
• {"✅" if vento_ok else "❌"} Vento: {current['wind_kph']} km/h
• {"✅" if visibilidade_ok else "❌"} Visibilidade: {current['vis_km']} km
• {"✅" if temp_ok else "❌"} Temperatura: {current['temp_c']}°C

📋 **Especificações do Drone:**
• Peso: {DRONE_CONFIG['peso']}g
• Altitude máxima: {DRONE_CONFIG['max_altitude']}m
• Autonomia: ~{DRONE_CONFIG['bateria_duracao']} minutos
"""
    
    await enviar_resposta(update_obj, mensagem, criar_menu_voltar())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    mensagem = """
❓ **AJUDA - BOT DE PREVISÃO DO TEMPO**

**COMANDOS DISPONÍVEIS:**

🌡️ **/clima**
• Temperatura atual
• Sensação térmica
• Condições do tempo

🌧️ **/chuva**
• Previsão de chuva
• Próximas horas
• Recomendações

📅 **/diasdechuva**
• Previsão semanal
• Análise de chuvas
• Tendências

🏠 **/baixarlona**
• Status da lona
• Recomendações
• Alertas

🚁 **/drone**
• Condições para voo
• Status do clima
• Recomendações

🔔 **/alertas**
• Configurar notificações
• Gerenciar avisos
• Preferências

❓ **/help**
• Esta mensagem
• Lista de comandos
• Instruções
"""
    
    await enviar_resposta(update, mensagem, criar_menu_voltar())

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /config"""
    location = user_config.get_location()
    
    keyboard = [
        [InlineKeyboardButton("🔄 Atualizar CEP", callback_data='update_cep')],
        [InlineKeyboardButton("📍 Ver Localização Atual", callback_data='show_location')],
        [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data='voltar_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensagem = f"""
⚙️ **CONFIGURAÇÕES DE LOCALIZAÇÃO**

📍 **Local Atual:**
• Cidade: {location['cidade']}
• Estado: {location['estado']}
• CEP: {location['cep']}
• Latitude: {location['latitude']}
• Longitude: {location['longitude']}

Para atualizar sua localização, use:
`/cep 12345-678`
(Substitua pelo seu CEP)

Ou selecione uma opção abaixo:
"""
    
    await enviar_resposta(update, mensagem, reply_markup)

async def cep_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /cep"""
    try:
        if not context.args:
            await update.message.reply_text(
                "❌ Por favor, forneça um CEP.\nExemplo: `/cep 12345-678`",
                parse_mode='Markdown'
            )
            return
        
        cep = context.args[0]
        success, message = user_config.update_location(cep)
        
        if success:
            location = user_config.get_location()
            mensagem = f"""
✅ **Localização atualizada!**

📍 **Novo local:**
• Cidade: {location['cidade']}
• Estado: {location['estado']}
• CEP: {location['cep']}
• Latitude: {location['latitude']}
• Longitude: {location['longitude']}

Use /clima para ver a previsão do tempo para sua nova localização!
"""
        else:
            mensagem = f"❌ {message}"
        
        await update.message.reply_text(mensagem, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(
            f"❌ Erro ao atualizar CEP: {str(e)}",
            parse_mode='Markdown'
        )

async def show_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra a localização atual configurada"""
    location = user_config.get_location()
    
    mensagem = f"""
📍 **LOCALIZAÇÃO ATUAL**

• Cidade: {location['cidade']}
• Estado: {location['estado']}
• CEP: {location['cep']}
• Latitude: {location['latitude']}
• Longitude: {location['longitude']}

Para atualizar sua localização, use:
`/cep 12345-678`
(Substitua pelo seu CEP)
"""
    
    await enviar_resposta(update, mensagem, criar_menu_voltar())

async def voltar_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para voltar ao menu principal"""
    if update.callback_query and update.callback_query.message:
        await show_main_menu(update.callback_query.message)

async def dias_chuva_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /diasdechuva"""
    await proximos_dias_callback(update, context)

async def alertas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /alertas - Configuração de alertas"""
    user_id = update.effective_user.id
    is_subscribed = user_id in alert_state['users_subscribed']
    
    keyboard = [
        [InlineKeyboardButton(
            "🔕 Desativar Alertas" if is_subscribed else "🔔 Ativar Alertas",
            callback_data='toggle_alertas'
        )],
        [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data='voltar_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensagem = f"""
🔔 **CONFIGURAÇÃO DE ALERTAS**

Status atual: {'🟢 Ativado' if is_subscribed else '🔴 Desativado'}

**Você será notificado sobre:**
• ⛈️ Previsão de tempestades
• 🌧️ Alta probabilidade de chuva (>70%)
• 💨 Ventos fortes (>40km/h)
• ⚠️ Alertas meteorológicos

Alertas são enviados:
• 📅 Diariamente às 7h
• ⚡ Em tempo real para eventos críticos
"""
    
    await enviar_resposta(update, mensagem, reply_markup)

async def toggle_alertas_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para ativar/desativar alertas"""
    user_id = update.effective_user.id
    
    if user_id in alert_state['users_subscribed']:
        alert_state['users_subscribed'].remove(user_id)
        status = "desativados"
    else:
        alert_state['users_subscribed'].add(user_id)
        status = "ativados"
    
    await alertas_command(update, context)

async def relatorio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /relatorio - Relatório completo"""
    location = user_config.get_location()
    previsao = obter_previsao_tempo(location['latitude'], location['longitude'])
    
    if not previsao:
        await enviar_resposta(update, "❌ Não foi possível obter os dados meteorológicos.", criar_menu_voltar())
        return
    
    current = previsao["current"]
    forecast = previsao["forecast"]["forecastday"][0]
    
    # Condições atuais
    temp_atual = current["temp_c"]
    sensacao = current["feelslike_c"]
    umidade = current["humidity"]
    vento = current["wind_kph"]
    direcao_vento = current["wind_dir"]
    condicao = formatar_condicao_tempo(current["condition"]["text"])
    emoji = obter_emoji_tempo(current["condition"]["text"])
    
    # Previsão para hoje
    max_temp = forecast["day"]["maxtemp_c"]
    min_temp = forecast["day"]["mintemp_c"]
    chance_chuva = forecast["day"]["daily_chance_of_rain"]
    precipitacao = forecast["day"]["totalprecip_mm"]
    
    mensagem = f"""
📊 **RELATÓRIO METEOROLÓGICO COMPLETO**
📍 {location['cidade']}/{location['estado']}
🕐 {current['last_updated']}

{emoji} **CONDIÇÕES ATUAIS:**
• 🌡️ Temperatura: {temp_atual}°C
• 🌡️ Sensação: {sensacao}°C
• ☁️ Condição: {condicao}
• 💧 Umidade: {umidade}%
• 💨 Vento: {vento}km/h {direcao_vento}

📅 **PREVISÃO PARA HOJE:**
• 🌡️ Máxima: {max_temp}°C
• 🌡️ Mínima: {min_temp}°C
• 🌧️ Chance de Chuva: {chance_chuva}%
• 💧 Precipitação: {precipitacao}mm

🚁 **STATUS PARA VOO:**
• {'✅ Condições favoráveis' if vento <= 40 and chance_chuva < 50 else '❌ Condições desfavoráveis'}

🏠 **STATUS DA LONA:**
• {'🔴 Recomendado baixar' if chance_chuva >= 70 or vento > 40 else '🟢 Pode manter'}
"""
    
    await enviar_resposta(update, mensagem, criar_menu_voltar())

async def baixar_lona_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /baixarlona"""
    await status_lona_callback(update, context)

async def alertas_config_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback para configuração de alertas"""
    await alertas_command(update, context)

# Dicionário com todos os comandos e callbacks disponíveis
available_commands = {
    'start': start_command,
    'help': help_command,
    'clima': clima_command,
    'chuva': chance_chuva_callback,
    'drone': drone_command,
    'config': config_command,
    'cep': cep_command,
    'diasdechuva': dias_chuva_command,
    'alertas': alertas_command,
    'relatorio': relatorio_command,
    'baixarlona': baixar_lona_command
}

# Dicionário com todos os callbacks disponíveis
available_callbacks = {
    'clima_atual': clima_command,
    'chance_chuva': chance_chuva_callback,
    'proximos_dias': proximos_dias_callback,
    'status_lona': status_lona_callback,
    'status_drone': drone_command,
    'config': config_command,
    'help': help_command,
    'voltar_menu': voltar_menu_callback,
    'show_location': show_location,
    'update_cep': config_command,
    'toggle_alertas': toggle_alertas_callback,
    'baixar_lona': baixar_lona_command,
    'alertas_config': alertas_config_callback,
    'relatorio': relatorio_command
} 