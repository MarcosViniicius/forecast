from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from config import logger

def criar_menu_voltar():
    """
    Cria o botão para voltar ao menu principal
    """
    keyboard = [[InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data='voltar_menu')]]
    return InlineKeyboardMarkup(keyboard)

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

def criar_menu_principal():
    """Cria o menu principal"""
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
    return InlineKeyboardMarkup(keyboard) 