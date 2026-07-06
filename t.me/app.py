import os
import logging
import requests
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
import json

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Get environment variables from Railway
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")

EXCHANGE_RATE_API_KEY = os.environ.get('EXCHANGE_RATE_API_KEY')
if not EXCHANGE_RATE_API_KEY:
    raise ValueError("EXCHANGE_RATE_API_KEY environment variable not set")

# API endpoints
EXCHANGE_RATE_URL = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/latest/"
SUPPORTED_CURRENCIES_URL = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/codes"

# --- Flask App (for Railway) ---
flask_app = Flask(__name__)

# --- Telegram Bot Application ---
bot_app = Application.builder().token(TELEGRAM_TOKEN).build()

# --- Helper Functions ---

def get_supported_currencies():
    """Fetch the list of supported currencies from the API."""
    try:
        response = requests.get(SUPPORTED_CURRENCIES_URL)
        if response.status_code == 200:
            data = response.json()
            if data.get('result') == 'success':
                # Return list of currency codes
                return [code for code, name in data.get('supported_codes', [])]
    except Exception as e:
        logger.error(f"Error fetching supported currencies: {e}")
    # Fallback to common currencies if API fails
    return ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'CAD', 'CHF', 'CNY', 'INR', 'BRL', 'ZAR', 'NZD']

def format_currency(amount):
    """Format currency with thousands separator and 2 decimal places."""
    return f"{amount:,.2f}"

async def convert_currency(amount, from_currency, to_currency):
    """Convert currency using ExchangeRate-API."""
    try:
        # Fetch exchange rates
        response = requests.get(f"{EXCHANGE_RATE_URL}{from_currency}")
        if response.status_code != 200:
            return None, "API service unavailable. Please try again later."
        
        data = response.json()
        if data.get('result') != 'success':
            error_msg = data.get('error-type', 'Unknown error')
            return None, f"API error: {error_msg}"
        
        # Check if target currency exists
        rates = data.get('conversion_rates', {})
        if to_currency not in rates:
            return None, f"Currency '{to_currency}' is not supported. Use /currencies to see all supported codes."
        
        rate = rates[to_currency]
        converted_amount = amount * rate
        
        # Format the response
        from_symbol = get_currency_symbol(from_currency)
        to_symbol = get_currency_symbol(to_currency)
        
        result = (
            f"💱 **Currency Conversion Result**\n\n"
            f"{from_symbol} {format_currency(amount)} {from_currency}\n"
            f"⬇️ {to_symbol} {format_currency(converted_amount)} {to_currency}\n\n"
            f"📊 **Exchange Rate**: 1 {from_currency} = {rate:.4f} {to_currency}"
        )
        return result, None
        
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        return None, f"An unexpected error occurred: {str(e)}"

def get_currency_symbol(currency_code):
    """Return common currency symbols."""
    symbols = {
        'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 
        'AUD': 'A$', 'CAD': 'C$', 'CHF': 'Fr', 'CNY': '¥',
        'INR': '₹', 'BRL': 'R$', 'ZAR': 'R', 'NZD': 'NZ$',
        'KRW': '₩', 'SGD': 'S$', 'HKD': 'HK$', 'SEK': 'kr',
        'NOK': 'kr', 'DKK': 'kr', 'PLN': 'zł', 'TRY': '₺',
        'RUB': '₽', 'MXN': 'Mex$', 'PHP': '₱', 'IDR': 'Rp'
    }
    return symbols.get(currency_code, '')

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
        "• `/convert 50 USD JPY` - Convert US Dollars to Japanese Yen\n"
        "• `/convert 1000 EUR GBP` - Convert Euros to British Pounds\n\n"
        "💡 **Tip**: You can also click the buttons below to start a conversion!"
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
        "Use the `/convert` command followed by amount, source, and target currencies.\n\n"
        "**Examples:**\n"
        "• `/convert 100 USD EUR`\n"
        "• `/convert 2500 JPY USD`\n"
        "• `/convert 1 BTC USD` (for Bitcoin support)\n\n"
        "**Supported Currencies:**\n"
        "Use `/currencies` to see the full list of supported currencies.\n\n"
        "**Need Help?**\n"
        "Contact the bot developer for support."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def convert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /convert command."""
    try:
        args = context.args
        if len(args) != 3:
            await update.message.reply_text(
                "❌ **Please provide exactly 3 arguments:**\n\n"
                "`/convert <amount> <from_currency> <to_currency>`\n\n"
                "**Example:** `/convert 100 USD EUR`",
                parse_mode='Markdown'
            )
            return

        # Parse the amount
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

        # Validate currency codes (must be exactly 3 characters)
        if len(from_currency) != 3 or len(to_currency) != 3:
            await update.message.reply_text(
                "❌ **Invalid currency code!**\n\n"
                "Currency codes must be exactly 3 letters.\n\n"
                "**Example:** `/convert 100 USD EUR`",
                parse_mode='Markdown'
            )
            return

        # Send a "processing" message
        processing_msg = await update.message.reply_text(
            "⏳ Fetching live exchange rates...",
            parse_mode='Markdown'
        )

        # Perform the conversion
        result, error = await convert_currency(amount, from_currency, to_currency)
        
        if error:
            await processing_msg.edit_text(f"❌ **Error:** {error}", parse_mode='Markdown')
        else:
            await processing_msg.edit_text(result, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Convert command error: {e}")
        await update.message.reply_text(
            f"❌ **An unexpected error occurred:** {str(e)}\n\n"
            "Please try again later.",
            parse_mode='Markdown'
        )

async def currencies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display all supported currencies."""
    try:
        currency_codes = get_supported_currencies()
        
        # Split currencies into chunks for better display
        chunks = [currency_codes[i:i+10] for i in range(0, len(currency_codes), 10)]
        
        message = "🌍 **Supported Currencies** 🌍\n\n"
        for chunk in chunks:
            message += "• " + " | ".join(chunk) + "\n"
        message += f"\n✅ **Total**: {len(currency_codes)} currencies supported"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Currencies command error: {e}")
        await update.message.reply_text(
            "❌ **Error fetching currencies list.**\n\n"
            "Please try again later.",
            parse_mode='Markdown'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages that aren't commands."""
    text = update.message.text
    
    # Check if the message looks like a currency conversion request
    parts = text.strip().split()
    if len(parts) == 3:
        try:
            # Try to parse it as "amount from to"
            amount = float(parts[0])
            from_curr = parts[1].upper()
            to_curr = parts[2].upper()
            if len(from_curr) == 3 and len(to_curr) == 3:
                # Looks like a conversion request, process it
                result, error = await convert_currency(amount, from_curr, to_curr)
                if error:
                    await update.message.reply_text(f"❌ **Error:** {error}", parse_mode='Markdown')
                else:
                    await update.message.reply_text(result, parse_mode='Markdown')
                return
        except ValueError:
            pass
        except Exception:
            pass
    
    # Default response
    await update.message.reply_text(
        "🤔 **I didn't understand that.**\n\n"
        "**Try:**\n"
        "• `/convert 100 USD EUR` - Convert currencies\n"
        "• `/currencies` - List all supported currencies\n"
        "• `/help` - Get help and examples\n\n"
        "💡 You can also send messages like: `50 USD JPY` directly!",
        parse_mode='Markdown'
    )

# --- Callback Query Handlers ---

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
            "• `1000 EUR GBP`\n"
            "• `1 BTC USD`",
            parse_mode='Markdown'
        )
    elif query.data == "view_currencies":
        # Trigger the currencies command
        await currencies(update, context)

# --- Flask Routes (For Railway Webhook) ---

@flask_app.route('/')
def index():
    """Root endpoint for health checks."""
    return jsonify({
        "status": "running",
        "bot": "@currency32converterbot",
        "version": "1.0.0"
    })

@flask_app.route('/health')
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming Telegram updates via webhook."""
    try:
        # Get the update from the request
        update = Update.de_json(request.get_json(force=True), bot_app.bot)
        
        # Process the update
        bot_app.process_update(update)
        
        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@flask_app.route('/setwebhook', methods=['GET'])
def set_webhook():
    """Set the webhook URL for the bot."""
    try:
        webhook_url = f"{request.base_url.replace('/setwebhook', '')}/webhook"
        response = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook",
            json={"url": webhook_url}
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Run the Application ---
if __name__ == '__main__':
    # For local development, use polling
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting bot on port {port}...")
    flask_app.run(host='0.0.0.0', port=port, debug=False)
