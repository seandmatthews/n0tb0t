import re
import selenium
from selenium.webdriver.common.keys import Keys

from TwitchSocket import TwitchSocket
from Bot import Bot
from config import SOCKET_ARGS

ts = TwitchSocket(**SOCKET_ARGS)
bot = Bot(ts)

p = re.compile('(\n\n).*$')

for methods in bot.sorted_methods.values():
    for method in methods:
        doc = str(getattr(bot, method).__doc__)
        re_str = re.sub(' +', ' ', doc).lstrip().rstrip()
        m = p.search(re_str)
        if m is None:
            print(method)
            print(doc)
        else:
            print(m.group().lstrip())


# driver = selenium.webdriver.Firefox()
#
# driver.get('http://www.twitch.tv/login')
# user_field = driver.find_element_by_id('username')
# user_field.send_keys('n0tb0t')
# pass_field = driver.find_element_by_xpath('//*[@id="password"]/input')
# pass_field.send_keys('Ferret1123')
# login_btn = driver.find_element_by_xpath('//*[@id="loginForm"]/div[3]/button')
# login_btn.click()
#
# driver.get('http://www.twitch.tv/n0t1337')
#
# chat_text_input = driver.find_element_by_css_selector('.ember-chat .chat-interface .textarea-contain textarea')
# chat_text_input.send_keys("n0t1337 You're sexy.", Keys.RETURN)
