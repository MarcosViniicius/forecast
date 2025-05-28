import os
import threading
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import logger, UPDATE_INTERVAL, ALERT_THRESHOLD
from handlers import available_commands, available_callbacks
from user_config import user_config

def main():
    """
    Função principal que inicia o bot
    """
    # Verifica variáveis de ambiente
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    weather_api_key = os.getenv("WEATHERAPI_KEY")
    
    if not telegram_token:
        logger.error("TELEGRAM_BOT_TOKEN não configurado")
        print("❌ Configure a variável de ambiente TELEGRAM_BOT_TOKEN")
        exit(1)
    
    if not weather_api_key:
        logger.error("WEATHERAPI_KEY não configurado")
        print("❌ Configure a variável de ambiente WEATHERAPI_KEY")
        exit(1)
    
    # Carrega configurações do usuário
    location = user_config.get_location()
    
    logger.info("Iniciando Bot de Previsão do Tempo")
    print(f"🤖 Iniciando Bot de Previsão do Tempo")
    print(f"📍 Local padrão: {location['cidade']}/{location['estado']}")
    print(f"⏰ Intervalo de verificação: {UPDATE_INTERVAL} minutos")
    print(f"🚨 Limite de alerta: {ALERT_THRESHOLD}% de chance de chuva")
    
    # Configura o bot do Telegram
    app = ApplicationBuilder().token(telegram_token).build()
    
    # Registra os comandos
    for comando, handler in available_commands.items():
        app.add_handler(CommandHandler(comando, handler))
        logger.info(f"Comando /{comando} registrado")
    
    # Adiciona handler para botões
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("\n✅ Bot configurado e pronto!")
    print("📱 Comandos disponíveis:")
    for comando in available_commands:
        print(f"   • /{comando}")
    
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

async def button_handler(update, context):
    """
    Manipula os botões interativos do menu
    """
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data in available_callbacks:
            await available_callbacks[query.data](update, context)
        else:
            logger.warning(f"Callback não tratado: {query.data}")
            if query.message:
                await query.message.edit_text(
                    "❌ Opção inválida ou não implementada",
                    parse_mode='Markdown'
                )
            
    except Exception as e:
        logger.error(f"Erro no button_handler: {e}")
        if query.message:
            await query.message.edit_text(
                "❌ Ocorreu um erro ao processar sua solicitação. Tente novamente.",
                parse_mode='Markdown'
            )

if __name__ == "__main__":
    main() 