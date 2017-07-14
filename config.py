# bot
TOKEN = ''
DEBUG = False
WEBHOOK = True


# botan
BOTAN_TOKEN = ''


# webhook
WEBHOOK_HOST = ''
WEBHOOK_PORT = 443
WEBHOOK_LISTEN = '0.0.0.0'

WEBHOOK_SSL_CERT = './cert/webhook_cert.pem'
WEBHOOK_SSL_PRIV = './cert/webhook_pkey.pem'

WEBHOOK_URL_BASE = f"https://{WEBHOOK_HOST}:{WEBHOOK_PORT}"
WEBHOOK_URL_PATH = f"/{TOKEN}/"

# info
VERSION = "2.5.0"
DB_DATE = "12.07.2017"


# database
MYSQL_HOST = 'localhost'
MYSQL_USER = ''
MYSQL_PASSWORD = ''
LIB_DATABASE = 'flibusta'
USERS_DATABASE = 'flibusta_users'


# ftp_controller
#   USE_FTP = True
LIFE_TIME = 3600  # seconds
FTP_DIR = './ftp'


# time
TIME_ZONE = 2


# tor
PROXIES = {'http': 'localhost:8118',
           'https': 'localhost:8118'}
