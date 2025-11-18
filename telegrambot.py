import os
import requests

class TelegramBot:
    BOT_TOKEN = ""
    CHAT_ID = ""
    def __init__(self):
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        self.CHAT_ID = "332138069"
        return
    
    def send_msg(self, message):
        if message != "" and self.BOT_TOKEN != None:
            url = f"https://api.telegram.org/bot{self.BOT_TOKEN}/sendMessage?chat_id={self.CHAT_ID}&text={message}"
            requests.get(url).json()
        return



#bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
#@bot.message_handler(commands=['start', 'hello'])
#def send_welcome(message):
#    bot.reply_to(message, "Howdy, how are you doing?")
#bot.infinity_polling()




#get chat id with my bot
#BOT_TOKEN = os.getenv('BOT_TOKEN')
#url = "https://api.telegram.org/bot"+BOT_TOKEN+"/getUpdates"
#print(requests.get(url).json())

#send message to my bot
#BOT_TOKEN = os.getenv('BOT_TOKEN')
#CHAT_ID = "332138069"
#message = "Hi from Python code"
#url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
#print(requests.get(url).json())
