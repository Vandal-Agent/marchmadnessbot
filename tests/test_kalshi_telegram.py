import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import football_telegram as bot


class CommandTests(unittest.IsolatedAsyncioTestCase):
    def update(self):
        return SimpleNamespace(effective_chat=SimpleNamespace(id=123),message=SimpleNamespace(reply_text=AsyncMock()))

    async def test_unauthorized_user_cannot_read_account(self):
        update=self.update()
        with patch.object(bot,'authorized',return_value=False), patch.object(bot,'build_account_report') as report:
            await bot.kalshi_cmd(update,None)
        report.assert_not_called()
        update.message.reply_text.assert_not_called()

    async def test_report_errors_never_disclose_exception_text(self):
        update=self.update()
        with patch.object(bot,'authorized',return_value=True), patch.object(bot,'build_scores_report',side_effect=RuntimeError('SECRET')):
            await bot.kalshiscores_cmd(update,None)
        self.assertNotIn('SECRET',update.message.reply_text.call_args.args[0])
        self.assertIn('unavailable',update.message.reply_text.call_args.args[0])

    async def test_large_history_is_chunked_for_telegram(self):
        update=self.update()
        with patch.object(bot,'authorized',return_value=True), patch.object(bot,'build_history',return_value='x'*8100):
            await bot.kalshihistory_cmd(update,None)
        chunks=[call.args[0] for call in update.message.reply_text.call_args_list]
        self.assertEqual(''.join(chunks),'x'*8100)
        self.assertTrue(all(len(part)<=3000 for part in chunks))
