import ssl

ssl._create_default_https_context = ssl._create_unverified_context

from sqlalchemy import select
from database.db import AsyncSessionLocal
from database.models import Order, Settings, CartItem

import asyncio
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton
)

from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from aiogram.utils.keyboard import InlineKeyboardBuilder

from parser.parser_1688 import (
    parse_1688_product,
    init_browser
)

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)

dp = Dispatcher()

ADMIN_ID = 7977451793


# FSM
class OrderState(StatesGroup):
    waiting_quantity = State()


# CACHE
products_cache = {}


# MENU
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🛍 Новый заказ"),
            KeyboardButton(text="🧺 Корзина")
        ],
        [
            KeyboardButton(text="📦 Мои заказы"),
            KeyboardButton(text="ℹ️ Помощь")
        ]
    ],
    resize_keyboard=True
)


# STATUS
status_translate = {
    "new": "🆕 Новый",
    "paid": "💰 Оплачен",
    "delivery": "🚚 В доставке",
    "china": "🇨🇳 На складе в Китае",
    "moscow": "🇷🇺 Прибыл в Москву",
    "done": "✅ Завершен",
    "cancel": "❌ Отменен"
}


# START
@dp.message(CommandStart())
async def start(message: Message):

    text = (
        f"🔥 <b>1688 SHOP BOT</b>\n\n"
        f"🛍 Отправь ссылку на товар\n"
        f"📦 Выбери вариант\n"
        f"💰 Получи расчет\n"
        f"🧺 Добавь в корзину\n"
        f"🚚 Оформи заказ"
    )

    await message.answer(
        text,
        reply_markup=main_keyboard,
        parse_mode="HTML"
    )


# HELP
@dp.message(F.text == "ℹ️ Помощь")
async def help_message(message: Message):

    await message.answer(
        "🔗 Отправь ссылку 1688 и выбери товар",
        parse_mode="HTML"
    )


# NEW ORDER
@dp.message(F.text == "🛍 Новый заказ")
async def new_order(message: Message):

    await message.answer(
        "🔗 Отправь ссылку на товар 1688"
    )


# MY ORDERS
@dp.message(F.text == "📦 Мои заказы")
async def my_orders(message: Message):

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Order).where(
                Order.user_id == message.from_user.id
            )
        )

        orders = result.scalars().all()

    if not orders:

        await message.answer(
            "📭 У вас пока нет заказов"
        )

        return

    messages = []

    current_text = "📦 <b>Ваши заказы:</b>\n\n"

    for order in orders[::-1]:

        ru_status = status_translate.get(
            order.status,
            order.status
        )

        order_text = (
            f"🆔 Заказ #{order.id}\n"
            f"📦 {order.product_name}\n"
            f"📏 {order.sku_name}\n"
            f"📊 {order.quantity} шт\n"
            f"💴 {order.total_rub:.2f} ₽\n"
            f"📌 {ru_status}\n"
            f"{'─' * 20}\n\n"
        )

        # Telegram limit
        if len(current_text + order_text) > 3800:

            messages.append(current_text)

            current_text = order_text

        else:

            current_text += order_text

    if current_text:
        messages.append(current_text)

    for text in messages:

        await message.answer(
            text,
            parse_mode="HTML"
        )


# ADMIN
@dp.message(F.text == "/admin")
async def admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:

        await message.answer("❌ Нет доступа")

        return

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Order)
        )

        orders = result.scalars().all()

    if not orders:

        await message.answer("📭 Заказов нет")

        return

    for order in orders[::-1][:10]:

        ru_status = status_translate.get(
            order.status,
            order.status
        )

        builder = InlineKeyboardBuilder()

        statuses = [
            ("🆕 Новый", "new"),
            ("💰 Оплачен", "paid"),
            ("🚚 Доставка", "delivery"),
            ("🇨🇳 Китай", "china"),
            ("🇷🇺 Москва", "moscow"),
            ("✅ Готов", "done")
        ]

        for text_btn, status in statuses:

            builder.button(
                text=text_btn,
                callback_data=f"status_{order.id}_{status}"
            )

        builder.adjust(2)

        text = (
            f"🆔 <b>Заказ #{order.id}</b>\n\n"
            f"👤 @{order.username}\n"
            f"🆔 {order.user_id}\n"
            f"🔗 https://t.me/{order.username}\n\n"
            f"📦 {order.product_name}\n"
            f"📏 {order.sku_name}\n"
            f"📊 {order.quantity} шт\n"
            f"💴 {order.total_rub:.2f} ₽\n"
            f"📌 {ru_status}\n\n"
            f"🔗 {order.product_url}"
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )


# CHANGE STATUS
@dp.callback_query(F.data.startswith("status_"))
async def change_status_callback(callback: CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        return

    parts = callback.data.split("_")

    order_id = int(parts[1])

    new_status = parts[2]

    ru_status = status_translate.get(
        new_status,
        new_status
    )

    async with AsyncSessionLocal() as session:

        order = await session.get(
            Order,
            order_id
        )

        if not order:
            return

        order.status = new_status

        await session.commit()

    try:

        await bot.send_message(
            order.user_id,
            f"📦 <b>Статус заказа обновлен</b>\n\n"
            f"🆔 Заказ #{order.id}\n"
            f"📌 Новый статус: {ru_status}",
            parse_mode="HTML"
        )

    except Exception as e:

        print(e)

    await callback.answer(
        "✅ Статус обновлен"
    )


# CART
@dp.message(F.text == "🧺 Корзина")
async def show_cart(message: Message):

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(CartItem).where(
                CartItem.user_id == message.from_user.id
            )
        )

        items = result.scalars().all()

    if not items:

        await message.answer(
            "🧺 Корзина пуста"
        )

        return

    total = 0

    text = "🧺 <b>Корзина</b>\n\n"

    builder = InlineKeyboardBuilder()

    for item in items:

        text += (
            f"📦 {item.product_name}\n"
            f"📏 {item.sku_name}\n"
            f"📊 {item.quantity} шт\n"
            f"💴 {item.total_rub:.2f} ₽\n"
            f"🔗 {item.product_url}"
        )

        total += item.total_rub

        builder.button(
            text=f"❌ Удалить #{item.id}",
            callback_data=f"delete_{item.id}"
        )

    builder.button(
        text="✅ Оформить заказ",
        callback_data="checkout"
    )

    builder.adjust(1)

    text += f"💰 <b>Итого:</b> {total:.2f} ₽"

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


# DELETE ITEM
@dp.callback_query(F.data.startswith("delete_"))
async def delete_item(callback: CallbackQuery):

    item_id = int(callback.data.split("_")[1])

    async with AsyncSessionLocal() as session:

        item = await session.get(
            CartItem,
            item_id
        )

        if item:

            await session.delete(item)

            await session.commit()

    await callback.answer(
        "Удалено"
    )

    await callback.message.delete()


# CHECKOUT
@dp.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery):

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(CartItem).where(
                CartItem.user_id == callback.from_user.id
            )
        )

        items = result.scalars().all()

        if not items:
            return

        total = 0

        for item in items:

            order = Order(

                user_id=item.user_id,
                username=item.username,

                product_name=item.product_name,

                sku_name=item.sku_name,

                quantity=item.quantity,

                total_yuan=item.price_yuan * item.quantity,

                total_rub=item.total_rub,

                product_url=item.product_url,

                status="new"
            )

            session.add(order)

            total += item.total_rub

            try:

                await bot.send_message(
                    ADMIN_ID,
                    f"🚨 НОВЫЙ ЗАКАЗ\n\n"
                    f"👤 @{item.username}\n"
                    f"🆔 {item.user_id}\n\n"
                    f"📦 {item.product_name}\n"
                    f"📏 {item.sku_name}\n"
                    f"📊 {item.quantity}\n"
                    f"💴 {item.total_rub:.2f} ₽\n\n"
                    f"🔗 {item.product_url}\n\n"
                    f"https://t.me/{item.username}"
                )

            except Exception as e:
                print(e)

        for item in items:
            await session.delete(item)

        await session.commit()

    await callback.message.answer(
        f"✅ Заказ оформлен\n\n"
        f"💴 Сумма: {total:.2f} ₽"
    )

    await callback.answer()


# QUANTITY
@dp.message(OrderState.waiting_quantity)
async def get_quantity(message: Message, state: FSMContext):

    if not message.text.isdigit():

        await message.answer("❌ Введите число")

        return

    quantity = int(message.text)

    data = await state.get_data()

    product_name = data["product_name"]

    sku_name = data["sku_name"]

    image = data.get("image")
    product_url = data.get("product_url")

    price_text = str(data["sku_price"])

    import re

    def normalize_price(price_text: str) -> float:

        """
        Нормальная обработка цен 1688

        Примеры:
        ¥228 → 228
        228.00 → 228
        ¥2-¥228 → 228
        2-228 → 228
        """

        if not price_text:
            return 0.0

        # Ищем ВСЕ числа
        numbers = re.findall(r"\d+\.?\d*", price_text)

        if not numbers:
            return 0.0

        # Берем максимальную цену
        prices = [float(x) for x in numbers]

        return max(prices)

    # ПРАВИЛЬНАЯ ЦЕНА
    price_yuan = normalize_price(price_text)

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Settings)
        )

        settings = result.scalar_one_or_none()

        if not settings:

            settings = Settings(
                yuan_rate=13.5
            )

            session.add(settings)

            await session.commit()

    yuan_rate = settings.yuan_rate

    commission_percent = 0.10

    total_yuan = price_yuan * quantity

    total_rub = total_yuan * yuan_rate

    commission = total_rub * commission_percent

    final_price = total_rub + commission

    async with AsyncSessionLocal() as session:

        cart_item = CartItem(

            user_id=message.from_user.id,
            username=message.from_user.username,

            product_name=product_name,

            sku_name=sku_name,

            quantity=quantity,

            price_yuan=price_yuan,

            total_rub=final_price,

            image=image,
            product_url=product_url
        )

        session.add(cart_item)

        await session.commit()

    await message.answer(
        f"✅ Товар добавлен в корзину\n\n"
        f"📦 {product_name}\n"
        f"📏 {sku_name}\n"
        f"📊 {quantity} шт\n\n"
        f"💰 Цена товара: {price_yuan:.2f} ¥\n"
        f"💴 Всего юаней: {total_yuan:.2f} ¥\n"
        f"💱 Курс: {yuan_rate} ₽\n"
        f"💼 Комиссия: {commission:.2f} ₽\n\n"
        f"🇷🇺 Итого: {final_price:.2f} ₽"
    )



    await state.clear()


# GET LINK
@dp.message(F.text & ~F.text.startswith("/"))
async def get_link(message: Message, state: FSMContext):

    if await state.get_state():
        return

    if "1688.com" not in message.text and "qr.1688.com" not in message.text:

        await message.answer(
            "❌ Отправь ссылку 1688"
        )

        return

    wait_message = await message.answer(
        "⏳ Парсю товар..."
    )

    data = await parse_1688_product(message.text)

    if not data["skus"]:

        await wait_message.edit_text(
            "❌ Не удалось получить товар"
        )

        return

    data["product_url"] = message.text

    products_cache[message.from_user.id] = data

    builder = InlineKeyboardBuilder()

    for i, sku in enumerate(data["skus"][:20]):

        builder.button(
            text=f"{sku['name']} — {sku['price']}",
            callback_data=f"sku_{i}"
        )

    builder.adjust(1)

    # ЕСЛИ ЕСТЬ SKU
    if len(data["skus"]) > 1:

        response = (
            f"🛍 <b>{data['title']}</b>\n\n"
            f"👇 Выберите вариант:"
        )

    # ЕСЛИ SKU НЕТ
    else:

        response = (
            f"🛍 <b>{data['title']}</b>\n\n"
            f"💰 Цена: {data['price']} ¥\n\n"
            f"👇 Выберите вариант:"
        )

    image = data.get("image")

    # PHOTO
    if image and image.startswith("http"):

        try:

            await message.answer_photo(
                photo=image,
                caption=response,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )

        except Exception as e:

            print("PHOTO ERROR:", e)

            await message.answer(
                response,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )

    else:

        await message.answer(
            response,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    await wait_message.delete()


# SKU
@dp.callback_query(F.data.startswith("sku_"))
async def choose_sku(callback: CallbackQuery, state: FSMContext):

    data = products_cache.get(
        callback.from_user.id
    )

    if not data:
        return

    sku_index = int(
        callback.data.split("_")[1]
    )

    sku = data["skus"][sku_index]

    await state.update_data(
        product_name=data["title"],
        sku_name=sku["name"],
        sku_price=sku["price"],
        image=data.get("image"),
        product_url=data.get("product_url")
    )

    await state.set_state(
        OrderState.waiting_quantity
    )

    await callback.message.answer(
        f"📏 {sku['name']}\n"
        f"💰 {sku['price']}\n\n"
        f"✍️ Введите количество:"
    )

    await callback.answer()


async def main():

    print("BOT STARTED")

    await init_browser()

    await dp.start_polling(bot)


if __name__ == "__main__":

    asyncio.run(main())