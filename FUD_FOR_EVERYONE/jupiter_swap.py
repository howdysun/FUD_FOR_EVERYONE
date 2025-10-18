import aiohttp
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio
import base64
from dataclasses import dataclass

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.message import to_bytes_versioned


SOL = Pubkey.from_string("So11111111111111111111111111111111111111112")


class SwapError(Exception):
    pass


@dataclass
class SwapResult:
    success: bool
    message: str
    timestamp: str
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "timestamp": self.timestamp
        }


class JupiterSwap:
    def __init__(self, private_key: Keypair | str):
        self.private_key = private_key if isinstance(private_key, Keypair) else Keypair.from_base58_string(private_key)
        self.JUPITER_API_URL = "https://lite-api.jup.ag"
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _get_order(self, input_mint: str, output_mint: str, amount: int) -> Dict[str, Any]:
        url = f"{self.JUPITER_API_URL}/ultra/v1/order"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": amount,
            "taker": str(self.private_key.pubkey()),
        }

        try:
            async with self._get_session().get(url, headers={"Accept": "application/json"}, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise SwapError(f"Order API error (Status {response.status}): {error_text}")
                
                order_data = await response.json()
                if "error" in order_data:
                    raise SwapError(f"Order error: {order_data['error']}")
                
                return order_data
        
        except asyncio.TimeoutError:
            raise SwapError(f"Network error while getting order")
        except Exception as e:
            raise SwapError(f"Unexpected error while getting order: {str(e)}")

    async def _execute_order(self, order_id: str, transaction: str) -> Dict[str, Any]:
        url = f"{self.JUPITER_API_URL}/ultra/v1/execute"
        payload = {"requestId": order_id, "signedTransaction": transaction}
        
        try:
            async with self._get_session().post(
                url,
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json=payload
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise SwapError(f"Order execution API error (Status {response.status}): {error_text}")
                
                return await response.json()
            
        except asyncio.TimeoutError:
            raise SwapError(f"Network error while executing order")
        except Exception as e:
            raise SwapError(f"Unexpected error while executing order: {str(e)}")

    async def _get_account_balances(self) -> Dict[str, Dict[str, Any]]:
        url = f"{self.JUPITER_API_URL}/ultra/v1/balances/{self.private_key.pubkey()}"
        
        try:
            async with self._get_session().get(url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise SwapError(f"Balances API error (Status {response.status}): {error_text}")
                
                return await response.json()
            
        except asyncio.TimeoutError:
            raise SwapError(f"Network error while getting balances")
        except Exception as e:
            raise SwapError(f"Unexpected error while getting balances: {str(e)}")
            
    async def _verify_sol_balance(self, amount: int) -> bool:
        balances = await self._get_account_balances()

        if "SOL" not in balances:
            raise SwapError("SOL balance not found, cannot buy tokens")
        
        if int(balances["SOL"]["amount"]) < amount:
            raise SwapError(f"Insufficient SOL balance: {balances['SOL']['amount']} < {amount}")

        return True

    async def _sign_transaction(self, transaction: str) -> str:
        swap_transaction_buf = base64.b64decode(transaction)
        raw_tx = VersionedTransaction.from_bytes(swap_transaction_buf)
        signature = self.private_key.sign_message(to_bytes_versioned(raw_tx.message))
        signed_tx = VersionedTransaction.populate(raw_tx.message, [signature])
        return base64.b64encode(bytes(signed_tx)).decode('utf-8')

    async def execute_swap(self, output_mint: str, amount: int, verify_balance: bool = False) -> SwapResult:
        try:
            print(f"\nBuying {output_mint} with {amount} lamports of SOL...")

            if verify_balance:
                await self._verify_sol_balance(amount)

            print("Getting order from Jupiter...")
            order = await self._get_order(SOL.__str__(), output_mint, amount)
            
            order_id = order.get('requestId')
            if not order_id:
                raise SwapError("No order ID returned from the API")

            transaction = order.get('transaction')
            if not transaction:
                raise SwapError("No transaction returned from the API")   

            print(f"Order received! ID: {order_id}")

            serialized_tx = await self._sign_transaction(transaction)

            print("Executing order...")
            execution_result = await self._execute_order(order_id, serialized_tx)

            signature = execution_result.get('signature')
            if not signature:
                raise SwapError("No signature returned from execution or execution failed")
            if execution_result.get('status', '').lower() != "success":
                raise SwapError(f"Execution failed: {execution_result.get('error')}")

            print(f"Transaction sent! Signature: {signature}")
            
            return SwapResult(
                success=True,
                message=execution_result,
                timestamp=datetime.now().isoformat()
            )

        except SwapError as e:
            print(f"Swap Error: {str(e)}")
            return SwapResult(
                success=False,
                message=str(e),
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            print(f"Unexpected Error: {str(e)}")
            return SwapResult(
                success=False,
                message=str(e),
                timestamp=datetime.now().isoformat()
            )

