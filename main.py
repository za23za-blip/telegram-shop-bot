import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DB_PATH = os.environ.get("DB_PATH", "shop.db")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("telegram-shop")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        price TEXT NOT NULL,
        active INTEGER DEFAULT 1
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        UNIQUE(product_id, code)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_payment',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    return conn

def is_admin(user_id: int) -> bool:
    return ADMIN_ID != 0 and user_id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🛍️ 浏览商品", callback_data="catalog")],
        [InlineKeyboardButton("📦 我的订单", callback_data="orders")],
        [InlineKeyboardButton("联系客服", url=os.environ.get("SUPPORT_URL", "https://t.me/"))],
    ]
    await update.message.reply_text(
        "欢迎来到自助商城！\n请选择下面的功能：",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = db()
    products = conn.execute(
        "SELECT id, name, description, price FROM products WHERE active=1 ORDER BY id"
    ).fetchall()
    conn.close()
    if not products:
        await query.edit_message_text("目前还没有上架商品，请稍后再来。")
        return
    rows = []
    for pid, name, desc, price in products:
        rows.append([InlineKeyboardButton(f"{name} · {price}", callback_data=f"product:{pid}")])
    rows.append([InlineKeyboardButton("返回首页", callback_data="home")])
    await query.edit_message_text("请选择商品：", reply_markup=InlineKeyboardMarkup(rows))

async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    query = update.callback_query
    conn = db()
    item = conn.execute(
        "SELECT name, description, price FROM products WHERE id=? AND active=1",
        (product_id,)
    ).fetchone()
    stock_count = conn.execute(
        "SELECT COUNT(*) FROM stock WHERE product_id=? AND used=0", (product_id,)
    ).fetchone()[0]
    conn.close()
    if not item:
        await query.edit_message_text("商品不存在或已下架。")
        return
    name, desc, price = item
    text = f"商品：{name}\n说明：{desc or '暂无'}\n价格：{price}\n库存：{stock_count}\n\n"
    text += "点击下单后会生成待付款订单。支付接口尚未配置完成前，机器人不会自动确认付款或发货。"
    keyboard = [[InlineKeyboardButton("创建订单", callback_data=f"buy:{product_id}")],
                [InlineKeyboardButton("返回商品列表", callback_data="catalog")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def create_order(update: Update, product_id: int):
    query = update.callback_query
    conn = db()
    available = conn.execute(
        "SELECT id FROM stock WHERE product_id=? AND used=0 ORDER BY id LIMIT 1",
        (product_id,)
    ).fetchone()
    product = conn.execute(
        "SELECT name, price FROM products WHERE id=? AND active=1", (product_id,)
    ).fetchone()
    if not product:
        conn.close()
        await query.edit_message_text("商品不存在或已下架。")
        return
    if not available:
        conn.close()
        await query.edit_message_text("商品暂时缺货，请联系客服。")
        return
    cur = conn.execute(
        "INSERT INTO orders(user_id, product_id) VALUES(?, ?)",
        (query.from_user.id, product_id)
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    await query.edit_message_text(
        f"订单已创建：#{order_id}\n商品：{product[0]}\n金额：{product[1]}\n状态：待付款\n\n"
        "当前版本尚未接入支付宝/USDT自动到账验证。请勿向机器人转账后期待自动发货；"
        "支付接口完成配置并测试后才会开放真实收款。"
    )

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    conn = db()
    rows = conn.execute(
        """SELECT o.id, p.name, o.status, o.created_at
           FROM orders o JOIN products p ON p.id=o.product_id
           WHERE o.user_id=? ORDER BY o.id DESC LIMIT 10""",
        (query.from_user.id,)
    ).fetchall()
    conn.close()
    if not rows:
        await query.edit_message_text("你还没有订单。")
        return
    lines = [f"#{oid}｜{name}｜{status}｜{created}" for oid, name, status, created in rows]
    await query.edit_message_text("最近订单：\n" + "\n".join(lines))

async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    if data == "catalog":
        await catalog(update, context)
    elif data == "orders":
        await my_orders(update, context)
    elif data == "home":
        await q.answer()
        await q.edit_message_text("发送 /start 返回商城首页。")
    elif data.startswith("product:"):
        await q.answer()
        await product_detail(update, context, int(data.split(":")[1]))
    elif data.startswith("buy:"):
        await q.answer()
        await create_order(update, int(data.split(":")[1]))
    else:
        await q.answer("暂不支持此操作。")

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            "格式：/addproduct 商品名称|价格|商品说明\n"
            "例如：/addproduct 月度会员|6 USDT|有效期30天"
        )
        return
    raw = " ".join(context.args)
    parts = [x.strip() for x in raw.split("|", 2)]
    if len(parts) != 3:
        await update.message.reply_text("请使用：/addproduct 名称|价格|说明")
        return
    conn = db()
    conn.execute("INSERT INTO products(name, price, description) VALUES(?,?,?)", parts)
    conn.commit()
    conn.close()
    await update.message.reply_text("商品已添加。")

async def add_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "格式：/addstock 商品ID 兑换码\n"
            "例如：/addstock 1 ABCD-1234"
        )
        return
    try:
        pid = int(context.args[0])
        code = " ".join(context.args[1:])
        conn = db()
        conn.execute("INSERT INTO stock(product_id, code) VALUES(?,?)", (pid, code))
        conn.commit()
        conn.close()
        await update.message.reply_text("库存已添加。")
    except Exception:
        log.exception("add stock failed")
        await update.message.reply_text("添加失败，请检查商品ID或兑换码是否重复。")

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        "管理员命令：\n"
        "/addproduct 名称|价格|说明 - 添加商品\n"
        "/addstock 商品ID 兑换码 - 添加一条库存\n"
        "注意：当前为基础测试版，尚未开放真实收款和自动发货。"
    )

def main():
    db().close()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addproduct", add_product))
    app.add_handler(CommandHandler("addstock", add_stock))
    app.add_handler(CommandHandler("admin", admin_help))
    app.add_handler(CallbackQueryHandler(callback))
    log.info("Bot is starting")
    app.run_polling()

if __name__ == "__main__":
    main()
