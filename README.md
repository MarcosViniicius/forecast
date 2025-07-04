# 🌤️ Bot de Previsão do Tempo

Bot do Telegram para previsão do tempo com funcionalidades especiais para monitoramento de condições para voo de drone e proteção de lona.

## 🚀 Funcionalidades

- 🌡️ Previsão do tempo atual
- 🌧️ Previsão de chuva para próximas horas
- 📅 Previsão para próximos dias
- 🚁 Status para voo de drone
- 🏠 Monitoramento de condições para lona
- 🔔 Sistema de alertas personalizáveis
- 📊 Relatório meteorológico completo

## 📋 Pré-requisitos

- Python 3.8+
- Token do Bot do Telegram
- Chave da API WeatherAPI
- Conexão com internet

## 🛠️ Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/forecast-bot.git
cd forecast-bot
```

2. Crie um ambiente virtual e ative-o:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
Crie um arquivo `.env` com:
```
TELEGRAM_TOKEN=seu_token_aqui
WEATHER_API_KEY=sua_chave_aqui
```

## 🚀 Uso

1. Inicie o bot:
```bash
python bot.py
```

2. No Telegram, procure por seu bot e inicie uma conversa.
3. Use o comando `/start` para ver o menu principal.

## 📝 Comandos Disponíveis

- `/start` - Inicia o bot e mostra o menu principal
- `/clima` - Mostra condições atuais
- `/chuva` - Previsão de chuva para próximas horas
- `/diasdechuva` - Previsão para próximos dias
- `/baixarlona` - Status da lona
- `/drone` - Status para voo
- `/relatorio` - Relatório meteorológico completo
- `/alertas` - Configurar alertas
- `/config` - Configurar localização
- `/cep` - Atualizar CEP
- `/help` - Ajuda detalhada

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor, sinta-se à vontade para enviar um Pull Request.

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 📞 Suporte

Se precisar de ajuda:
1. Verifique a documentação
2. Use o comando `/help` no bot
3. Abra uma issue no GitHub