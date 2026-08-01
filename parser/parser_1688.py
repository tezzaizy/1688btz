import re
import json
import html

from deep_translator import GoogleTranslator
from playwright.async_api import async_playwright

browser = None
context = None
playwright_instance = None


# =========================
# START BROWSER
# =========================
async def init_browser():

    global browser
    global context
    global playwright_instance

    try:
        if context:
            _ = context.pages
            return context
    except:
        pass

    print("STEP 1: START INIT")

    playwright_instance = await async_playwright().start()

    browser = await playwright_instance.chromium.launch_persistent_context(
        user_data_dir="userdata",

        headless=False,

        viewport={
            "width": 1400,
            "height": 1000
        },

        args=[
            "--start-maximized",
            "--disable-blink-features=AutomationControlled"
        ]
    )

    context = browser

    print("BROWSER STARTED")

    return context


# =========================
# RESOLVE URL
# =========================
async def resolve_1688_url(url):

    global context

    try:

        if "offer/" in url or "detail.1688.com" in url:
            return url

        temp_page = await context.new_page()

        await temp_page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=120000
        )

        await temp_page.wait_for_timeout(5000)

        final_url = temp_page.url

        print("FINAL URL:", final_url)

        await temp_page.close()

        return final_url

    except Exception as e:

        print("RESOLVE URL ERROR:", e)

        return url


# =========================
# EXTRACT REAL PRICE
# =========================
def extract_real_price(text):

    matches = re.findall(
        r"(?:¥|￥)\s*(\d+(?:\.\d+)?)",
        text
    )

    prices = []

    for m in matches:

        try:

            value = float(m)

            if 15 <= value <= 50000:
                prices.append(value)

        except:
            pass

    if not prices:
        return "0"

    price = min(prices)

    if str(price).endswith(".0"):
        return str(int(price))

    return str(price)


# =========================
# =========================
# TRANSLATE
# =========================

import html


def translate_text(text):

    try:

        # исправляем &gt; &amp; и т.д.
        text = html.unescape(text)

        translated = GoogleTranslator(
            source='auto',
            target='ru'
        ).translate(text)

        translated = html.unescape(translated)

        # красиво разделяем SKU
        translated = translated.replace(">", " / ")

        return translated

    except Exception as e:

        print("TRANSLATE ERROR:", e)

        return html.unescape(text)


# =========================
# MAIN PARSER
# =========================
async def parse_1688_product(url):

    global context

    page = None

    try:

        context = await init_browser()

        url = await resolve_1688_url(url)

        page = await context.new_page()

        print("OPEN PAGE")

        await page.goto(
            url,
            timeout=120000,
            wait_until="domcontentloaded"
        )

        await page.wait_for_timeout(8000)

        # =========================
        # SAVE HTML
        # =========================

        html = await page.content()

        with open(
            "page.html",
            "w",
            encoding="utf-8"
        ) as f:
            f.write(html)

        print("HTML SAVED")

        print("START PARSE")

        title = "Не найден"
        image = None
        skus = []
        main_price = "0"

        # =========================
        # TITLE
        # =========================
        try:

            selectors = [
                "h1",
                ".title-text",
                ".d-title",
                ".od-pc-offer-title"
            ]

            for selector in selectors:

                locator = page.locator(selector)

                if await locator.count() > 0:

                    text = await locator.first.inner_text()

                    text = text.strip()

                    if len(text) > 3:

                        title = text
                        break

            print("TITLE:", title)

        except Exception as e:
            print("TITLE ERROR:", e)

        # =========================
        # PRICE
        # =========================
        try:

            body_text = await page.locator("body").inner_text()

            main_price = extract_real_price(body_text)
            # =========================
            # =========================
            # PRICE FROM HTML JSON
            # =========================

            try:

                # ищем блоки цена + минимальное количество
                price_blocks = re.findall(
                    r'"price":"(\d+(?:\.\d+)?)".*?"beginAmount":(\d+)',
                    html
                )

                print("PRICE BLOCKS:", price_blocks)

                found_price = None

                # сначала ищем цену за 1 штуку
                for price, amount in price_blocks:

                    if int(amount) == 1:
                        found_price = price
                        break

                # если нет beginAmount=1
                # берем первый блок
                if not found_price and price_blocks:
                    found_price = price_blocks[0][0]

                if found_price:
                    main_price = found_price

                    print("MAIN PRICE FROM JSON:", main_price)

            except Exception as e:

                print("HTML PRICE ERROR:", e)

            print("MAIN PRICE:", main_price)

        except Exception as e:
            print("PRICE ERROR:", e)

        # =========================
        # IMAGE
        # =========================
        try:

            image_selectors = [
                "img[src*=jpg]",
                "img[src*=png]",
                "img[data-src]",
                ".detail-gallery img",
                ".main-img img",
                "img"
            ]

            for selector in image_selectors:

                locator = page.locator(selector)

                count = await locator.count()

                if count <= 0:
                    continue

                for i in range(min(count, 20)):

                    try:

                        img = locator.nth(i)

                        src = await img.get_attribute("src")

                        if not src:
                            src = await img.get_attribute("data-src")

                        if not src:
                            continue

                        if src.startswith("//"):
                            src = "https:" + src

                        if "svg" in src:
                            continue

                        if len(src) < 20:
                            continue

                        image = src.split("?")[0]

                        print("IMAGE FOUND:", image)

                        break

                    except:
                        pass

                if image:
                    break

        except Exception as e:
            print("IMAGE ERROR:", e)

        # =========================
        # SKU JSON
        # =========================

        try:

            match = re.search(
                r'"skuMapOriginal":\s*(\[[\s\S]*?\])',
                html
            )

            if match:

                sku_json = match.group(1)

                data = json.loads(sku_json)

                print("SKU JSON FOUND:", len(data))

                for item in data:

                    try:

                        name = item.get(
                            "specAttrs",
                            "Стандарт"
                        )

                        price_fields = [
                            item.get("discountPrice"),
                            item.get("price"),
                            item.get("salePrice"),
                            item.get("priceDisplay"),
                            item.get("displayPrice"),
                            item.get("priceRange")
                        ]

                        price = None

                        for p in price_fields:

                            if not p:
                                continue

                            p = str(p).strip()

                            # мусор
                            if p in ["0", "0.0", "0.00", ""]:
                                continue

                            # если диапазон цен
                            # например: 31.00-45.00
                            if "-" in p:

                                try:

                                    p = p.split("-")[0].strip()

                                except:
                                    pass

                            price = p
                            break

                        # если вообще ничего нет
                        if not price:
                            price = main_price

                        # если main_price тоже 0
                        if str(price).strip() in ["0", "0.0", "0.00", ""]:

                            body_text = await page.locator("body").inner_text()

                            extracted = extract_real_price(body_text)

                            if extracted != "0":
                                price = extracted

                        # финальная защита
                        if str(price).strip() in ["0", "0.0", "0.00", ""]:
                            price = "Цена не указана"

                        translated_name = translate_text(name)

                        skus.append({
                            "name": translated_name,
                            "price": price
                        })

                    except Exception as e:

                        print("SKU ITEM ERROR:", e)

            else:

                print("SKU JSON NOT FOUND")

                skus.append({
                    "name": "Стандарт",
                    "price": main_price
                })

        except Exception as e:

            print("SKU JSON ERROR:", e)

            skus.append({
                "name": "Стандарт",
                "price": main_price
            })

        # =========================
        # REMOVE DUPLICATES
        # =========================

        unique_skus = []

        used = set()

        for sku in skus:

            key = f"{sku['name']}|{sku['price']}"

            if key not in used:

                used.add(key)

                unique_skus.append(sku)

        skus = unique_skus

        print("SKUS:", skus)

        print("PARSE DONE")

        await page.close()

        return {
            "title": title,
            "price": main_price,
            "image": image,
            "skus": skus
        }

    except Exception as e:

        print("GLOBAL ERROR:", e)

        try:
            if page:
                await page.close()
        except:
            pass

        return {
            "title": "Ошибка загрузки",
            "price": "0",
            "image": None,
            "skus": []
        }