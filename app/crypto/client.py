from __future__ import annotations

from aiocryptopay import AioCryptoPay, Networks


class CryptoClient:
    def __init__(self, token: str):
        self._client = AioCryptoPay(token=token, network=Networks.MAIN_NET)

    async def create_invoice(self, amount: float, asset: str = "USDT"):
        return await self._client.create_invoice(asset=asset, amount=amount)

    async def get_invoice(self, invoice_id: int):
        invoices = await self._client.get_invoices(invoice_ids=[invoice_id])
        return invoices[0] if invoices else None

    async def get_balance(self):
        return await self._client.get_balance()

    async def transfer(self, user_id: int, amount: float, asset: str = "USDT", spend_id: str | int | None = None):
        return await self._client.transfer(
            user_id=user_id,
            asset=asset,
            amount=amount,
            spend_id=spend_id or f"wd:{user_id}:{amount}",
        )

    async def close(self) -> None:
        await self._client.close()
