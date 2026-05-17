import re
import aiohttp

from playwright.async_api import async_playwright

browser = None
context = None
playwright_instance = None


# СТАРТ БРАУЗЕРА
async def init_browser():

    global browser
    global context
    global playwright_instance

    try:
        if browser:
            return context
    except:
        pass

    playwright_instance = await async_playwright().start()

    browser = await playwright_instance.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled"
        ]
    )

    context = await browser.new_context(
        viewport={
            "width": 1280,
            "height": 900
        }
    )

    print("BROWSER STARTED")

    return context


# QR -> NORMAL URL
async def resolve_1688_url(url):

    try:

        async with aiohttp.ClientSession() as session:

            async with session.get(
                url,
                allow_redirects=True,
                timeout=20,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 "
                        "(Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 "
                        "(KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"
                    )
                }
            ) as response:

                final_url = str(response.url)

                print("FINAL URL:", final_url)

                return final_url

    except Exception as e:

        print("RESOLVE URL ERROR:", e)

        return url


# ПАРСЕР
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
            timeout=60000,
            wait_until="networkidle"
        )

        # Ждем появления SKU
        try:

            await page.wait_for_selector(
                ".sku-item, .expand-view-item, .sku-item-wrapper",
                timeout=15000
            )

        except:
            pass

        await page.wait_for_timeout(3000)

        print("START PARSE")

        title = "Не найден"
        image = None
        skus = []
        main_price = "0"

        # TITLE
        try:

            title_selectors = [
                "h1",
                ".title-text",
                ".d-title",
                "#productTitle h1"
            ]

            for selector in title_selectors:

                locator = page.locator(selector)

                if await locator.count() > 0:

                    text = await locator.first.inner_text()

                    text = text.strip()

                    if text:

                        title = text

                        break

        except Exception as e:
            print("TITLE ERROR:", e)

        # MAIN PRICE
        try:

            body_text = await page.locator("body").inner_text()

            matches = re.findall(
                r"[¥￥]\s*(\d+(?:\.\d+)?)",
                body_text
            )

            if matches:

                prices = [
                    float(x)
                    for x in matches
                ]

                # убираем слишком маленькие мусорные цены
                prices = [
                    x for x in prices
                    if x >= 1
                ]

                if prices:

                    main_price = str(min(prices))

                    if main_price.endswith(".0"):
                        main_price = main_price[:-2]

            print("MAIN PRICE:", main_price)

        except Exception as e:
            print("MAIN PRICE ERROR:", e)

        # IMAGE
        try:

            image_selectors = [
                ".detail-gallery-img img",
                ".main-img img",
                ".gallery-img img",
                "img"
            ]

            for selector in image_selectors:

                try:

                    locator = page.locator(selector)

                    if await locator.count() > 0:

                        src = await locator.first.get_attribute("src")

                        if src:

                            if src.startswith("//"):
                                src = "https:" + src

                            if src.startswith("/"):
                                src = "https://detail.1688.com" + src

                            src = src.replace(".webp", ".jpg")

                            if src.startswith("http"):

                                image = src

                                print("IMAGE FOUND")

                                break

                except:
                    pass

        except Exception as e:
            print("IMAGE ERROR:", e)

        # SKU
        try:

            selectors = [
                ".expand-view-item",
                ".sku-item-wrapper",
                ".prop-item",
                ".sku-item",
                ".table-sku",
                "[class*=sku]",
                "[class*=Sku]"
            ]

            for selector in selectors:

                sku_items = page.locator(selector)

                count = await sku_items.count()

                if count <= 0:
                    continue

                print("SKU FOUND:", selector)
                print("SKU COUNT:", count)

                for i in range(min(count, 50)):

                    try:

                        item = sku_items.nth(i)

                        text = await item.inner_text()

                        text = text.strip()

                        if not text:
                            continue

                        lines = [
                            x.strip()
                            for x in text.split("\n")
                            if x.strip()
                        ]

                        if not lines:
                            continue

                        sku_name = lines[0][:60]

                        price = main_price

                        # ИЩЕМ ЦЕНУ ТОЛЬКО В СТРОКАХ С ¥
                        for line in lines:

                            if "¥" in line or "￥" in line or "元" in line:

                                match = re.search(
                                    r"(\d+(?:\.\d+)?)",
                                    line
                                )

                                if match:

                                    found_price = match.group(1)

                                    # защита от артикулов
                                    if float(found_price) < 100000:

                                        price = found_price
                                        break

                        if price.endswith(".0"):
                            price = price[:-2]

                        skus.append({
                            "name": sku_name,
                            "price": price
                        })

                    except Exception as e:
                        print("SKU ITEM ERROR:", e)

                if skus:
                    break

            # ЕСЛИ SKU НЕ НАШЛИСЬ
            if not skus:

                skus.append({
                    "name": "Стандарт",
                    "price": main_price
                })

        except Exception as e:
            print("SKU ERROR:", e)

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