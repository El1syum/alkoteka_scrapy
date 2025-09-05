import json
import time

import scrapy


class AlkotekaSpider(scrapy.Spider):
    name = 'alkoteka'
    allowed_domains = ['alkoteka.com']

    KRASNODAR_CITY_UUID = '4a70f9e0-46ae-11e7-83ff-00155d026416'
    per_page = 4  # 2000 оптимально

    def get_api_category_url(self, slug):
        return f"https://alkoteka.com/web-api/v1/product?city_uuid={self.KRASNODAR_CITY_UUID}&page=1&per_page={self.per_page}&root_category_slug={slug}"

    def get_set_city_url(self):
        return f"https://alkoteka.com/web-api/v1/city?city_uuid={self.KRASNODAR_CITY_UUID}"

    def get_additional_info_url(self, slug):
        return f"https://alkoteka.com/web-api/v1/product/{slug}?city_uuid={self.KRASNODAR_CITY_UUID}"

    async def start(self):
        """
        Инициирует процесс: сначала устанавливает город, затем начинает парсинг категорий.
        """
        self.logger.info(f"Начинаю установку города UUID: {self.KRASNODAR_CITY_UUID}")

        yield scrapy.Request(
            url=self.get_set_city_url(),
            method='GET',
            callback=self.set_city_and_proceed,
            dont_filter=True
        )

    def set_city_and_proceed(self, response):
        """
        Обрабатывает ответ от запроса установки города.
        После установки города, получает список URL категорий и начинает их парсинг.
        """
        self.logger.info(f"Город установлен (или попытка была): {response.url}, Status: {response.status}")

        if response.status != 200:
            self.logger.error(f"Не удалось установить город. Статус: {response.status}, Ответ: {response.text[:200]}")
            return

        try:
            with open('start_urls.txt', 'r') as f:
                start_urls = [url.strip() for url in f.readlines() if url.strip()]
        except FileNotFoundError:
            self.logger.error("Файл start_urls.txt не найден.")
            return

        for url in start_urls:
            slug = url.split('/')[-1]
            print(slug)
            api_category_url = self.get_api_category_url(slug)

            yield scrapy.Request(api_category_url, callback=self.get_items_from_category)

    def get_items_from_category(self, response):
        self.logger.info(f"Получаю товары из категории: {response.url}")

        try:
            data = response.json()
            products_data = data.get('results', [])
        except json.JSONDecodeError:
            self.logger.error(f"Не удалось декодировать JSON с URL: {response.url}")
            return

        if not products_data:
            self.logger.info(f"В категории {response.url} товары не найдены или JSON пуст.")
            return

        for product_data in products_data:
            # product_page_url = product_data.get('product_url')
            product_slug = product_data.get('slug')
            product_page_url = self.get_additional_info_url(product_slug)

            if not product_page_url:
                self.logger.warning(f"Не найден URL для товара: {product_data.get('name')}")
                continue

            yield scrapy.Request(
                url=product_page_url,
                callback=self.parse_item_first,
                meta={
                    'api_data': product_data
                }
            )

    def parse_item_first(self, response):
        """
        Парсинг json товара и извлечение всей необходимой информации.
        """
        self.logger.info(f"Парсинг товара: {response.url}")

        first_api_data = response.meta.get('api_data', {})
        add_api_data = response.json().get('results')

        brand, desc = '', ''

        category = first_api_data.get('category')

        rpc = add_api_data.get('vendor_code')
        url = response.url
        title = first_api_data.get('name')
        marketing_tags = [i.get('title') for i in first_api_data.get('action_labels')]
        section = [category.get('parent').get('name'), category.get('name')]

        price_current = first_api_data.get('price')
        price_original = first_api_data.get('prev_price') or price_current
        sale_tag = ""
        if price_current < price_original:
            discount = round((1 - price_current / price_original) * 100)
            sale_tag = f"Скидка {discount}%"

        in_stock = first_api_data.get('available')
        count = first_api_data.get('quantity_total') or 0

        main_image = first_api_data.get('image_url')
        set_images = ['']  # Ни у одного товара нет более 1 фотографии
        view = ['']  # Нет ни у одного товара
        video = ['']  # Нет ни у одного товара

        text_blocks = add_api_data.get('text_blocks')
        for text_block in text_blocks:
            if text_block.get('title').lower().strip() == 'описание':
                desc = text_block.get('content').replace('<br>', '').strip()
                break

        metadata = {'__description': desc}

        props = add_api_data.get('description_blocks')
        for prop in props:
            key = prop.get('title')
            values = prop.get('values')
            min = prop.get('min')
            if values:
                value = values[0].get('name')
            else:
                if prop.get('enabled'):
                    value = min
                else:
                    continue
            if key and value:
                metadata[key] = value

                if key.lower() == 'бренд':
                    brand = value

        variants = 1  # На сайте нет товаров с несколькими вариантами

        # Постобработка названия
        volume = None
        filter_labels = first_api_data.get('filter_labels')
        for filter_label in filter_labels:
            if filter_label.get('filter') == 'obem':
                volume = filter_label.get('title')
                break

        if volume and (volume not in title):
            title = f'{title}, {volume}'

        item  = {
            "timestamp": int(time.time()),
            "RPC": rpc,
            "url": url,
            "title": title,
            "marketing_tags": marketing_tags,
            "brand": brand,
            "section": section,
            "price_data": {
                "current": price_current,
                "original": price_original,
                "sale_tag": sale_tag
            },
            "stock": {
                "in_stock": in_stock,
                "count": count
            },
            "assets": {
                "main_image": main_image,
                "set_images": set_images,
                "view360": view,
                "video": video
            },
            "metadata": {
                "__description": desc,
                **metadata
            },
            "variants": variants,
        }

        yield item


