from flask import Flask, request
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler
import requests
import json
import os

app = Flask(__name__)

# Bot token and channel details
API_TOKEN = '7510497222:AAH2QxJoA3ZqIc0Z0ydjmvjRHX0sm02ZOas'
CHANNEL_USERNAME = '@THE_ANON_69'
LOG_CHANNEL = '@logsspl'
ADMIN_PASSWORD = 'BorNoX'
DATA_FILE_PATH = '/app/bot_data.json'

# States for conversation handler
ASKING_NUMBER, ASKING_MESSAGE, ASKING_REDEEM_CODE = range(3)

# Load data
try:
    with open(DATA_FILE_PATH, 'r') as f:
        data = json.load(f)
except FileNotFoundError:
    data = {'users': {}, 'redeem_codes': {}, 'referrals': {}}

# Save data function
def save_data():
    with open(DATA_FILE_PATH, 'w') as f:
        json.dump(data, f)

# Initialize the bot
bot = telegram.Bot(API_TOKEN)
updater = Updater(API_TOKEN, use_context=True)
dp = updater.dispatcher

# Check if user has joined the channel
def check_channel_membership(bot, user_id):
    try:
        member = bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

# Decorator to restrict access to the bot only to users who joined the channel
def channel_required(func):
    def wrapped(update, context, *args, **kwargs):
        user_id = update.effective_user.id
        if check_channel_membership(context.bot, user_id):
            return func(update, context, *args, **kwargs)
        else:
            update.message.reply_text('Please join our channel first: ' + CHANNEL_USERNAME)
            return ConversationHandler.END
    return wrapped

# Admin command to stop the bot
def stop(update: Update, context: CallbackContext):
    if update.message.text.split(' ')[1] == ADMIN_PASSWORD:
        context.bot_data['active'] = False
        update.message.reply_text('Bot is now offline.')
    else:
        update.message.reply_text('Invalid admin password.')

# Admin command to start the bot
def start(update: Update, context: CallbackContext):
    if update.message.text.split(' ')[1] == ADMIN_PASSWORD:
        context.bot_data['active'] = True
        update.message.reply_text('Bot is now online.')
    else:
        update.message.reply_text('Invalid admin password.')

# Command to start the bot
@channel_required
def start_command(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    if user_id not in data['users']:
        data['users'][user_id] = {'coins': 0}
        save_data()
    update.message.reply_text('Welcome! Choose an option:', reply_markup=get_main_menu())

# Command to send message
@channel_required
def send_message(update: Update, context: CallbackContext):
    update.message.reply_text('Please enter the number:')
    return ASKING_NUMBER

def receive_number(update: Update, context: CallbackContext):
    context.user_data['number'] = update.message.text
    update.message.reply_text('Please enter the message:')
    return ASKING_MESSAGE

def receive_message(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    message = update.message.text
    number = context.user_data['number']

    # Check if user has enough coins
    if data['users'][user_id]['coins'] < 1:
        update.message.reply_text('You do not have enough coins.')
        return ConversationHandler.END

    # Send request to the URL
    try:
        response = requests.get(f'https://test.swanbd.com/sms.php?number={number}&msg={message}')
        if response.status_code == 200:
            data['users'][user_id]['coins'] -= 1
            save_data()
            update.message.reply_text('Message sent successfully.')
            context.bot.send_message(chat_id=LOG_CHANNEL, text=f"MESSAGED BY {update.effective_user.username}\nNUMBER - {number}\nMESSAGE - {message}")
        else:
            update.message.reply_text('Failed to send message.')
    except Exception as e:
        update.message.reply_text('Error occurred while sending message.')

    return ConversationHandler.END

# Command to show account balance
@channel_required
def account(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    coins = data['users'][user_id]['coins']
    update.message.reply_text(f'You have {coins} coins.')

# Command to redeem code
@channel_required
def redeem(update: Update, context: CallbackContext):
    update.message.reply_text('Please enter the redeem code:')
    return ASKING_REDEEM_CODE

def receive_redeem_code(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    redeem_code = update.message.text

    if redeem_code in data['redeem_codes'] and data['redeem_codes'][redeem_code]['uses'] > 0:
        data['users'][user_id]['coins'] += data['redeem_codes'][redeem_code]['coins']
        data['redeem_codes'][redeem_code]['uses'] -= 1
        save_data()
        update.message.reply_text(f'You have successfully redeemed {data['redeem_codes'][redeem_code]['coins']} coins.')
    else:
        update.message.reply_text('Invalid or expired redeem code.')

    return ConversationHandler.END

# Command to handle referrals
@channel_required
def refer(update: Update, context: CallbackContext):
    user_id = str(update.effective_user.id)
    username = update.effective_user.username
    data['referrals'][username] = user_id
    save_data()
    update.message.reply_text(f'Your referral link: https://t.me/YourBot?start={username}')

# Main menu keyboard
def get_main_menu():
    from telegram import ReplyKeyboardMarkup
    keyboard = [['Send Message', 'Account', 'Refer', 'Redeem Code']]
    return ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

def main():
    updater = Updater(API_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Add conversation handlers
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex('^(Send Message)$'), send_message),
                      MessageHandler(Filters.regex('^(Redeem Code)$'), redeem)],
        states={
            ASKING_NUMBER: [MessageHandler(Filters.text & ~Filters.command, receive_number)],
            ASKING_MESSAGE: [MessageHandler(Filters.text & ~Filters.command, receive_message)],
            ASKING_REDEEM_CODE: [MessageHandler(Filters.text & ~Filters.command, receive_redeem_code)]
        },
        fallbacks=[CommandHandler('cancel', lambda update, context: update.message.reply_text('Cancelled.'))]
    )
    dp.add_handler(conv_handler)

    # Add command handlers
    dp.add_handler(CommandHandler('start', start_command))
    dp.add_handler(CommandHandler('stop', stop))
    dp.add_handler(CommandHandler('open', start))
    dp.add_handler(MessageHandler(Filters.regex('^(Account)$'), account))
    dp.add_handler(MessageHandler(Filters.regex('^(Refer)$'), refer))

    # Initialize bot state
    updater.bot_data['active'] = True

    # Start polling
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

# Keep Glitch project alive
@app.route('/')
def home():
    return "Bot is running"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
      
