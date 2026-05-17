# =========================
# web/app.py
# =========================

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

from sqlalchemy import select

from database.db import AsyncSessionLocal
from database.models import Order

from aiogram import Bot
from dotenv import load_dotenv

import os


# =========================
# ENV
# =========================
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)


# =========================
# APP
# =========================
app = FastAPI()


# =========================
# ПЕРЕВОД СТАТУСОВ
# =========================
STATUS_TRANSLATE = {
    "new": "🆕 Новый",
    "paid": "💰 Оплачен",
    "delivery": "🚚 В доставке",
    "china": "🇨🇳 На складе в Китае",
    "moscow": "🇷🇺 Прибыл в Москву",
    "done": "✅ Завершен",
    "cancel": "❌ Отменен"
}


# =========================
# СМЕНА СТАТУСА
# =========================
@app.get("/status/{order_id}/{new_status}")
async def change_status(order_id: int, new_status: str):

    async with AsyncSessionLocal() as session:

        order = await session.get(
            Order,
            order_id
        )

        if order:

            # СОХРАНЯЕМ
            order.status = (
                new_status
                .strip()
                .lower()
            )

            await session.commit()

            # РУССКИЙ СТАТУС
            ru_status = STATUS_TRANSLATE.get(
                order.status,
                order.status
            )

            # =========================
            # УВЕДОМЛЕНИЕ КЛИЕНТУ
            # =========================
            try:

                await bot.send_message(

                    chat_id=order.user_id,

                    text=(
                        f"📦 <b>Статус заказа обновлен</b>\n\n"
                        f"🆔 Заказ #{order.id}\n"
                        f"📌 Новый статус: {ru_status}"
                    ),

                    parse_mode="HTML"
                )

            except Exception as e:

                print("TELEGRAM ERROR:", e)

    return RedirectResponse(
        url="/",
        status_code=303
    )


# =========================
# DASHBOARD
# =========================
@app.get("/", response_class=HTMLResponse)
async def dashboard():

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(Order).order_by(Order.id.desc())
        )

        orders = result.scalars().all()

    total_orders = len(orders)

    total_revenue = sum(
        order.total_rub
        for order in orders
    )

    html = f"""
    <html>

    <head>

        <title>1688 Admin Panel</title>

        <style>

            body {{
                background: #0f172a;
                color: white;
                font-family: Arial;
                padding: 30px;
            }}

            h1 {{
                color: #38bdf8;
            }}

            .stats {{
                display: flex;
                gap: 20px;
                margin-bottom: 30px;
            }}

            .card {{
                background: #1e293b;
                padding: 20px;
                border-radius: 15px;
                width: 250px;
            }}

            table {{
                width: 100%;
                border-collapse: collapse;
                background: #1e293b;
                border-radius: 15px;
                overflow: hidden;
            }}

            th {{
                background: #334155;
                padding: 15px;
                text-align: left;
            }}

            td {{
                padding: 15px;
                border-top: 1px solid #334155;
            }}

            tr:hover {{
                background: #273449;
            }}

            .buttons {{
                display: flex;
                flex-wrap: wrap;
                gap: 5px;
            }}

            .btn {{
                text-decoration: none;
                padding: 6px 10px;
                border-radius: 8px;
                color: white;
                font-size: 12px;
                font-weight: bold;
            }}

            .new {{
                background: #3b82f6;
            }}

            .paid {{
                background: #22c55e;
            }}

            .delivery {{
                background: #f59e0b;
            }}

            .china {{
                background: #ef4444;
            }}

            .moscow {{
                background: #8b5cf6;
            }}

            .done {{
                background: #10b981;
            }}

            .cancel {{
                background: #6b7280;
            }}

        </style>

    </head>

    <body>

        <h1>👑 1688 ADMIN PANEL</h1>

        <div class="stats">

            <div class="card">
                <h2>📦 Заказов</h2>
                <h1>{total_orders}</h1>
            </div>

            <div class="card">
                <h2>💰 Оборот</h2>
                <h1>{total_revenue:.2f} ₽</h1>
            </div>

        </div>

        <table>

            <tr>
                <th>ID</th>
                <th>USER</th>
                <th>ТОВАР</th>
                <th>SKU</th>
                <th>КОЛ-ВО</th>
                <th>СУММА</th>
                <th>СТАТУС</th>
                <th>УПРАВЛЕНИЕ</th>
            </tr>
    """

    for order in orders:

        status_key = (
            str(order.status)
            .strip()
            .lower()
        )

        ru_status = STATUS_TRANSLATE.get(
            status_key,
            order.status
        )

        html += f"""
            <tr>

                <td>#{order.id}</td>

                <td>{order.user_id}</td>

                <td>{order.product_name}</td>

                <td>{order.sku_name}</td>

                <td>{order.quantity}</td>

                <td>{order.total_rub:.2f} ₽</td>

                <td>{ru_status}</td>

                <td>

                    <div class="buttons">

                        <a class="btn new"
                        href="/status/{order.id}/new">
                        Новый
                        </a>

                        <a class="btn paid"
                        href="/status/{order.id}/paid">
                        Оплачен
                        </a>

                        <a class="btn delivery"
                        href="/status/{order.id}/delivery">
                        Доставка
                        </a>

                        <a class="btn china"
                        href="/status/{order.id}/china">
                        Китай
                        </a>

                        <a class="btn moscow"
                        href="/status/{order.id}/moscow">
                        Москва
                        </a>

                        <a class="btn done"
                        href="/status/{order.id}/done">
                        Готов
                        </a>

                        <a class="btn cancel"
                        href="/status/{order.id}/cancel">
                        Отмена
                        </a>

                    </div>

                </td>

            </tr>
        """

    html += """

        </table>

    </body>

    </html>
    """

    return html