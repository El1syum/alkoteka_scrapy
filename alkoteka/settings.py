from fake_useragent import UserAgent

BOT_NAME = "alkoteka"

SPIDER_MODULES = ["alkoteka.spiders"]
NEWSPIDER_MODULE = "alkoteka.spiders"

ROBOTSTXT_OBEY = False

DOWNLOAD_DELAY = 2
CONCURRENT_REQUESTS_PER_DOMAIN = 8

FEEDS = {
    'result.json': {
        'format': 'json',
        'encoding': 'utf8',
        'store_empty': False,
        'fields': None,
        'indent': 4,
        'item_export_kwargs': {
            'export_empty_fields': True,
        },
    },
}

DOWNLOADER_MIDDLEWARES = {
   'alkoteka.middlewares.ProxyMiddleware': 543,
}

PROXY_LIST = []

USER_AGENT = UserAgent().random