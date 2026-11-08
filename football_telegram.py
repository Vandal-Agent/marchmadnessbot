from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from football_v2.config import settings
from football_v2.kalshi_history import build_history
from football_v2.kalshi_reports import build_account_report, build_scores_report
from football_v2.telegram_support import (
    build_status,
    build_top_ten,
    is_authorized_chat,
    run_manual_scan,
)

scan_lock = asyncio.Lock()


def authorized(update: Update) -> bool:
    chat = update.effective_chat
    return is_authorized_chat(None if chat is None else chat.id, settings.telegram_chat_id)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update) or update.message is None:
        return
    await update.message.reply_text(
        "Football V2 paper bot\n\n"
        "/footballstatus - paper record and top five\n"
        "/footballtop10 - latest saved top ten\n"
        "/footballscan - run one extra saved scan\n\n"
        "/kalshi - actual account balance and positions\n"
        "/kalshiscores - positions with current football scores\n"
        "/kalshihistory - daily Pacific balances\n\n"
        "Recommendations use paper tracking. Account reports are read-only. No trades are placed."
    )


async def footballstatus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update) or update.message is None:
        return
    report = await asyncio.to_thread(build_status, settings.database_path)
    await update.message.reply_text(report)


async def footballtop10_cmd(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not authorized(update) or update.message is None:
        return
    report = await asyncio.to_thread(
        build_top_ten,
        settings.database_path,
    )
    await update.message.reply_text(report)


async def footballscan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not authorized(update) or update.message is None:
        return
    if scan_lock.locked():
        await update.message.reply_text("A football scan is already running.")
        return
    async with scan_lock:
        await update.message.reply_text("Starting an extra Football V2 paper scan. This uses API credits.")
        try:
            report = await asyncio.to_thread(run_manual_scan)
        except Exception:
            report = "Football scan failed. Check the server log."
        await update.message.reply_text(report)


async def account_reply(update: Update, builder) -> None:
    if not authorized(update) or update.message is None:
        return
    try:
        report = await asyncio.to_thread(builder)
    except Exception:
        report = "Kalshi report unavailable. Check server configuration or try again later."
    # 3000 Python characters remain below Telegram's limit even with typical
    # market text. Measure UTF-16 too, since supplementary characters count twice.
    while report:
        end = min(len(report), 3000)
        while len(report[:end].encode('utf-16-le')) // 2 > 3000:
            end -= 1
        await update.message.reply_text(report[:end])
        report = report[end:]


async def kalshi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await account_reply(update, build_account_report)


async def kalshiscores_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await account_reply(update, build_scores_report)


async def kalshihistory_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await account_reply(update, build_history)


def main() -> None:
    if not settings.telegram_bot_token:
        raise ValueError("Missing MARCHMADNESS_TELEGRAM_BOT_TOKEN in /home/vandal/.env")
    if not settings.telegram_chat_id:
        raise ValueError("Missing MARCHMADNESS_TELEGRAM_CHAT_ID in /home/vandal/.env")
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("footballstatus", footballstatus_cmd))
    app.add_handler(CommandHandler("footballtop10", footballtop10_cmd))
    app.add_handler(CommandHandler("footballscan", footballscan_cmd))
    app.add_handler(CommandHandler("kalshi", kalshi_cmd))
    app.add_handler(CommandHandler("kalshiscores", kalshiscores_cmd))
    app.add_handler(CommandHandler("kalshihistory", kalshihistory_cmd))
    app.run_polling()


if __name__ == "__main__":
    main()
