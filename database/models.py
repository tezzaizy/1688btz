from sqlalchemy import Column, Integer, String, Float

from database.db import Base


class Order(Base):

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer)

    product_name = Column(String)

    sku_name = Column(String)

    quantity = Column(Integer)

    total_yuan = Column(Float)

    total_rub = Column(Float)

    status = Column(String)


class Settings(Base):

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)

    yuan_rate = Column(Float, default=13.5)


class CartItem(Base):

    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer)

    product_name = Column(String)

    sku_name = Column(String)

    quantity = Column(Integer)

    price_yuan = Column(Float)

    total_rub = Column(Float)

    image = Column(String)