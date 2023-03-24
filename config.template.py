DEBUG = True  # Set this to False in production
SECRET_KEY = "dev"  # Set this to a secure value in production
DOMAIN_NAME = "127.0.0.1:5000"  # Set this to your domain in production, don't append a trailing slash
MONGO_URI = "mongodb://127.0.0.1:27017/users"
MAIL_SERVER = "smtp.gmail.com"
MAIL_PORT = 465
MAIL_USE_TLS = False
MAIL_USE_SSL = True
MAIL_USERNAME = "username"
MAIL_PASSWORD = "password"
MAIL_DEFAULT_SENDER = ("sender", MAIL_USERNAME)
WRITER_WEBHOOK = None  # Webhook where we will get notified on a new application
SUMMARIZATION_API_KEY = "" # API key for the summarization API
SUMMARIZATION_API_KEY_2 = "" # backup API key for the summarization API
OPENAI_API_KEY = "sk-something" # main summarization API key
FTP_HOST = "0.0.0.0"
FTP_USER = "username"
FTP_PASSWORD = "password"