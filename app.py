import os
import logging
import requests
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
    TELEGRAM_TOKEN = "DUMMY_TOKEN_FOR_TESTING"  # Fallback for testing

EXCHANGE_RATE_API_KEY = os.environ.get('EXCHANGE_RATE_API_KEY')
if not EXCHANGE_RATE_API_KEY:
    logger.error("EXCHANGE_RATE_API_KEY environment variable not set")
    EXCHANGE_RATE_API_KEY = "DUMMY_KEY_FOR_TESTING"  # Fallback for testing

EXCHANGE_RATE_URL = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/"

# --- Create Flask App (CRITICAL: This MUST exist) ---
app = Flask(__name__)

# --- Create Telegram Bot Application ---
bot_app = Application.builder().token(TELEGRAM_TOKEN).build()

# --- Bot Command Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when /start is issued."""
    welcome_message = (
        "🌟 **Welcome to Currency32 Converter Bot!** 🌟\n\n"
        "I'm your reliable currency converter with live exchange rates.\n\n"
        "**Available Commands:**\n"
        "• `/convert 100 USD EUR` - Convert currencies\n"
        "• `/currencies` - List all supported currencies\n"
        "• `/help` - Show this help message\n\n"
        "**Quick Usage Examples:**\n"
        "• `/convert 50 USD JPY` - US Dollars to Japanese Yen\n"
        "• `/convert 1000 EUR GBP` - Euros to British Pounds"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Quick Convert", callback_data="quick_convert")],
        [InlineKeyboardButton("📊 View All Currencies", callback_data="view_currencies")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send help message when /help is issued."""
    help_text = (
        "📖 **Help & Usage Guide**\n\n"
        "**Convert Currencies:**\n"
        "Use `/convert` followed by amount, source, and target currencies.\n\n"
        "**Examples:**\n"
        "• `/convert 100 USD EUR`\n"
        "• `/convert 2500 JPY USD`\n\n"
        "**Supported Currencies:**\n"
        "Use `/currencies` to see the full list."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def convert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /convert command."""
    try:
        args = context.args
        if len(args) != 3:
            await update.message.reply_text(
                "❌ **Please provide:**\n\n"
                "`/convert <amount> <from_currency> <to_currency>`\n\n"
                "**Example:** `/convert 100 USD EUR`",
                parse_mode='Markdown'
            )
            return

        try:
            amount = float(args[0])
        except ValueError:
            await update.message.reply_text(
                "❌ **Invalid amount!**\n\n"
                "Please enter a valid number.\n\n"
                "**Example:** `/convert 100.50 USD EUR`",
                parse_mode='Markdown'
            )
            return

        from_currency = args[1].upper()
        to_currency = args[2].upper()

        # Send processing message
        processing_msg = await update.message.reply_text(
            "⏳ Fetching live exchange rates...",
            parse_mode='Markdown'
        )

        # Check if API key is valid
        if EXCHANGE_RATE_API_KEY == "DUMMY_KEY_FOR_TESTING":
            await processing_msg.edit_text(
                "❌ **API Key Missing!**\n\n"
                "Please set the EXCHANGE_RATE_API_KEY environment variable.",
                parse_mode='Markdown'
            )
            return

        # Fetch exchange rates
        response = requests.get(f"{EXCHANGE_RATE_URL}{from_currency}")
        if response.status_code != 200:
            await processing_msg.edit_text(
                "❌ Sorry, I couldn't fetch the latest rates. Please try again later.",
                parse_mode='Markdown'
            )
            return

        data = response.json()
        if data.get('result') != 'success':
            await processing_msg.edit_text(
                "❌ Currency conversion service is temporarily unavailable.",
                parse_mode='Markdown'
            )
            return

        rates = data.get('conversion_rates', {})
        if to_currency not in rates:
            await processing_msg.edit_text(
                f"❌ Currency '{to_currency}' is not supported.\n\n"
                "Use `/currencies` to see all supported codes.",
                parse_mode='Markdown'
            )
            return

        rate = rates[to_currency]
        converted_amount = amount * rate

        result = (
            f"💱 **Currency Conversion Result**\n\n"
            f"💰 {amount:.2f} {from_currency}\n"
            f"⬇️ {converted_amount:.2f} {to_currency}\n\n"
            f"📊 **Rate**: 1 {from_currency} = {rate:.4f} {to_currency}"
        )
        await processing_msg.edit_text(result, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Convert command error: {e}")
        await update.message.reply_text(
            f"❌ An error occurred: {str(e)}",
            parse_mode='Markdown'
        )

async def currencies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display all supported currencies."""
    try:
        # Common currencies (hardcoded for reliability)
        currency_codes = ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'INR', 'BRL', 
                         'ZAR', 'NZD', 'KRW', 'SGD', 'HKD', 'SEK', 'NOK', 'DKK', 'PLN', 'TRY',
                         'RUB', 'MXN', 'PHP', 'IDR', 'AED', 'SAR', 'THB', 'VND', 'MYR', 'NGN']
        
        message = "🌍 **Supported Currencies** 🌍\n\n"
        # Split into rows of 5
        for i in range(0, len(currency_codes), 5):
            row = currency_codes[i:i+5]
            message += "• " + " | ".join(row) + "\n"
        message += f"\n✅ **Total**: {len(currency_codes)} currencies supported"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Currencies command error: {e}")
        await update.message.reply_text(
            "❌ Error fetching currencies list. Please try again later.",
            parse_mode='Markdown'
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "quick_convert":
        await query.edit_message_text(
            "🔄 **Quick Conversion**\n\n"
            "Send a message like:\n"
            "`100 USD EUR`\n\n"
            "Or use the command:\n"
            "`/convert 100 USD EUR`\n\n"
            "**Examples:**\n"
            "• `50 USD JPY`\n"
            "• `1000 EUR GBP`",
            parse_mode='Markdown'
        )
    elif query.data == "view_currencies":
        # Send the currencies list
        await currencies(update, context)

# --- Register Handlers ---
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(CommandHandler("convert", convert))
bot_app.add_handler(CommandHandler("currencies", currencies))
bot_app.add_handler(CallbackQueryHandler(handle_callback))

# --- Flask Routes ---

@app.route('/')
def index():
    """Root endpoint for health checks."""
    return jsonify({
        "status": "running",
        "bot": "@currency32converterbot",
        "version": "1.0.0",
        "telegram_token_set": bool(TELEGRAM_TOKEN and TELEGRAM_TOKEN != "DUMMY_TOKEN_FOR_TESTING"),
        "api_key_set": bool(EXCHANGE_RATE_API_KEY and EXCHANGE_RATE_API_KEY != "DUMMY_KEY_FOR_TESTING")
    })

@app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Telegram updates via webhook."""
    try:
        if TELEGRAM_TOKEN == "DUMMY_TOKEN_FOR_TESTING":
            return jsonify({"error": "Bot token not configured"}), 500
            
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        bot_app.process_update(update)
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/setwebhook', methods=['GET'])
def set_webhook():
    """Set the webhook URL for the bot."""
    try:
        if TELEGRAM_TOKEN == "DUMMY_TOKEN_FOR_TESTING":
            return jsonify({"error": "Bot token not configured"}), 500
            
        webhook_url = f"{request.base_url.replace('/setwebhook', '')}/webhook"
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
            json={"url": webhook_url}
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Main Entry Point ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting bot on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
