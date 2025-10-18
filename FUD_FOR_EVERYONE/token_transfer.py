from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from solana.rpc.types import TxOpts
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address, create_associated_token_account
import asyncio
import struct
from typing import List, Tuple


async def get_top_token_holders(client: AsyncClient, token_mint: str, count: int) -> List[Tuple[str, int]]:
    try:
        mint_pubkey = Pubkey.from_string(token_mint)
        response = await client.get_token_largest_accounts(mint_pubkey)
        
        if not response.value:
            print(f"No token holders found for {token_mint}")
            return []
        
        top_holders = []
        for account_info in response.value[:count]:
            account_address = str(account_info.address)
            balance = int(account_info.amount.amount)
            
            if balance > 0:
                top_holders.append((account_address, balance))
        
        print(f"Found {len(top_holders)} top holders")
        return top_holders
    
    except Exception as e:
        print(f"Error getting top token holders: {str(e)}")
        return []


async def get_token_balance(client: AsyncClient, owner_pubkey: Pubkey, token_mint: Pubkey) -> int:
    try:
        token_account = get_associated_token_address(owner_pubkey, token_mint)
        
        account_info = await client.get_account_info(token_account)
        if account_info.value is None:
            return 0
        
        response = await client.get_token_account_balance(token_account)
        
        if response.value is None:
            return 0
        
        return int(response.value.amount)
    
    except Exception as e:
        print(f"Error getting token balance: {str(e)}")
        return 0


def create_transfer_instruction(source: Pubkey, dest: Pubkey, owner: Pubkey, amount: int, token_program_id: Pubkey = TOKEN_PROGRAM_ID) -> Instruction:
    data = struct.pack("<BQ", 3, amount)
    
    keys = [
        AccountMeta(pubkey=source, is_signer=False, is_writable=True),
        AccountMeta(pubkey=dest, is_signer=False, is_writable=True),
        AccountMeta(pubkey=owner, is_signer=True, is_writable=False),
    ]
    
    return Instruction(program_id=token_program_id, accounts=keys, data=data)


async def ensure_associated_token_account(client: AsyncClient, payer: Keypair, owner: Pubkey, mint: Pubkey) -> Pubkey:
    ata = get_associated_token_address(owner, mint)
    
    try:
        account_info = await client.get_account_info(ata)
        
        if account_info.value is None:
            print(f"Creating associated token account for receiver...")
            
            create_ata_ix = create_associated_token_account(
                payer=payer.pubkey(),
                owner=owner,
                mint=mint
            )
            
            recent_blockhash_resp = await client.get_latest_blockhash()
            recent_blockhash = recent_blockhash_resp.value.blockhash
            
            message = MessageV0.try_compile(
                payer=payer.pubkey(),
                instructions=[create_ata_ix],
                address_lookup_table_accounts=[],
                recent_blockhash=recent_blockhash,
            )
            
            transaction = VersionedTransaction(message, [payer])
            
            await client.send_transaction(
                transaction,
                opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed)
            )
            
            print(f"Associated token account created: {ata}")
        
        return ata
    
    except Exception as e:
        print(f"Error ensuring associated token account: {str(e)}")
        raise


async def transfer_tokens_to_multiple(private_key: str, token_mint: str, receivers: List[str], rpc_url: str, amount: int = None) -> bool:
    if not receivers:
        print("No receivers specified")
        return False
    
    client = None
    
    try:
        client = AsyncClient(rpc_url)
        
        sender_keypair = Keypair.from_base58_string(private_key)
        sender_pubkey = sender_keypair.pubkey()
        mint_pubkey = Pubkey.from_string(token_mint)
        
        if amount is None:
            balance = await get_token_balance(client, sender_pubkey, mint_pubkey)
            if balance == 0:
                print(f"No tokens found to transfer")
                return False
            total_amount = balance
        else:
            total_amount = amount
        
        amount_per_receiver = total_amount // len(receivers)
        
        if amount_per_receiver == 0:
            print(f"Insufficient tokens to distribute to {len(receivers)} receivers")
            return False
        
        print(f"Distributing {total_amount} tokens to {len(receivers)} receivers ({amount_per_receiver} each)...")
        
        sender_token_account = get_associated_token_address(sender_pubkey, mint_pubkey)
        
        success_count = 0
        for idx, receiver in enumerate(receivers, 1):
            try:
                receiver_token_account = Pubkey.from_string(receiver)
                
                print(f"  [{idx}/{len(receivers)}] Transferring to {receiver[:8]}...{receiver[-8:]}...")
                
                transfer_ix = create_transfer_instruction(sender_token_account, receiver_token_account, sender_pubkey, amount_per_receiver)
                
                recent_blockhash = (await client.get_latest_blockhash()).value.blockhash
                
                message = MessageV0.try_compile(
                    payer=sender_pubkey,
                    instructions=[transfer_ix],
                    address_lookup_table_accounts=[],
                    recent_blockhash=recent_blockhash,
                )
                
                transaction = VersionedTransaction(message, [sender_keypair])
                
                tx_sig = await client.send_transaction(transaction, opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed))
                
                print(f"  Transfer signature: {tx_sig.value}")
                success_count += 1
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"  Failed to transfer to {receiver}: {str(e)}")
                continue
        
        print(f"Successfully transferred to {success_count}/{len(receivers)} receivers")
        return success_count > 0
    
    except Exception as e:
        print(f"Transfer error: {str(e)}")
        return False
    
    finally:
        if client:
            await client.close()


async def transfer_tokens(private_key: str, token_mint: str, receiver: str, rpc_url: str, amount: int = None) -> bool:
    client = None
    
    try:
        client = AsyncClient(rpc_url)
        
        sender_keypair = Keypair.from_base58_string(private_key)
        sender_pubkey = sender_keypair.pubkey()
        receiver_pubkey = Pubkey.from_string(receiver)
        mint_pubkey = Pubkey.from_string(token_mint)
        
        sender_token_account = get_associated_token_address(sender_pubkey, mint_pubkey)
        
        if amount is None:
            balance = await get_token_balance(client, sender_pubkey, mint_pubkey)
            if balance == 0:
                print(f"No tokens found to transfer")
                return False
            transfer_amount = balance
        else:
            transfer_amount = amount
        
        print(f"Transferring {transfer_amount} tokens...")
        
        receiver_token_account = await ensure_associated_token_account(client, sender_keypair, receiver_pubkey, mint_pubkey)
        
        transfer_ix = create_transfer_instruction(sender_token_account, receiver_token_account, sender_pubkey, transfer_amount)
        
        recent_blockhash = (await client.get_latest_blockhash()).value.blockhash
        
        message = MessageV0.try_compile(
            payer=sender_pubkey,
            instructions=[transfer_ix],
            address_lookup_table_accounts=[],
            recent_blockhash=recent_blockhash,
        )
        
        transaction = VersionedTransaction(message, [sender_keypair])
        
        print(f"Sending transfer transaction...")
        tx_sig = await client.send_transaction(transaction, opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed))
        
        print(f"Transfer signature: {tx_sig.value}")
        return True
    
    except Exception as e:
        print(f"Transfer error: {str(e)}")
        return False
    
    finally:
        if client:
            await client.close()