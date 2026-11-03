# Telegram Shop Bot (starter)

This is a starter bot for browsing digital products and creating pending orders.

## Important
- Real Alipay and USDT payment verification is NOT implemented yet.
- Do not accept real payments or promise automatic delivery until a legitimate payment provider/API and server-side verification are configured and tested.
- Never commit bot tokens, payment secrets, wallet private keys, or customer credentials.
- Use only lawful products and authorized account/credential distribution.

## Render
Create a Background Worker from this repository.
Build command: `pip install -r requirements.txt`
Start command: `python main.py`

Set environment variables in Render:
- `BOT_TOKEN`: Telegram bot token
- `ADMIN_ID`: your numeric Telegram user ID
- `SUPPORT_URL`: support Telegram URL, e.g. `https://t.me/your_support`

## Admin commands
- `/admin`
- `/addproduct 名称|价格|说明`
- `/addstock 商品ID 兑换码`

The starter stores products, stock, and orders in SQLite. Configure persistent storage before production use.
