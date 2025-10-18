import asyncio
import json
import sys
from pathlib import Path

from jupiter_swap import JupiterSwap, SwapResult
from token_transfer import transfer_tokens_to_multiple, get_top_token_holders
from solana.rpc.async_api import AsyncClient


def load_config(config_path: str) -> dict:
    if not Path(config_path).exists():
        print(f"Error: Config file not found: {config_path}")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = json.load(file)
        
        required_fields = ['private_key', 'token_mint', 'sol_amount', 'top_holders_count', 'rpc_url']
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            print(f"Error: Missing required fields in config.json: {missing_fields}")
            sys.exit(1)
        
        if 'blacklist' not in config:
            config['blacklist'] = []
        
        return config
    
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config file: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading config file: {str(e)}")
        sys.exit(1)


async def buy_and_distribute(config: dict) -> bool:
    private_key = config['private_key']
    token_mint = config['token_mint']
    sol_amount_in_sol = float(config['sol_amount'])
    top_holders_count = int(config['top_holders_count'])
    rpc_url = config['rpc_url']
    blacklist = config['blacklist']
    
    sol_amount_lamports = int(sol_amount_in_sol * 1_000_000_000)
    
    print(f"CONFIGURATION")
    print(f"{'='*60}")
    print(f"Token Mint: {token_mint}")
    print(f"SOL Amount to Spend: {sol_amount_in_sol} SOL ({sol_amount_lamports:,} lamports)")
    print(f"Top Holders Count: {top_holders_count}")
    print(f"Blacklisted Addresses: {len(blacklist)}")
    print(f"{'='*60}\n")
    
    try:
        print(f"[Step 1/3] Getting top {top_holders_count} holders of {token_mint}...")
        
        client = AsyncClient(rpc_url)
        try:
            top_holders = await get_top_token_holders(client, token_mint, top_holders_count * 2)
            
            if not top_holders:
                print(f"Error: No top holders found for {token_mint}")
                return False
            
            blacklist_set = set(blacklist)
            filtered_holders = [(addr, bal) for addr, bal in top_holders if addr not in blacklist_set]
            
            blacklisted_count = len(top_holders) - len(filtered_holders)
            if blacklisted_count > 0:
                print(f"Filtered out {blacklisted_count} blacklisted addresses")
            
            final_holders = filtered_holders[:top_holders_count]
            
            if len(final_holders) < top_holders_count:
                print(f"Warning: Only found {len(final_holders)} non-blacklisted holders (requested {top_holders_count})")
            
            holder_addresses = [holder[0] for holder in final_holders]
            
            print(f"Found {len(holder_addresses)} top holders (after filtering)")
            for idx, (address, balance) in enumerate(final_holders, 1):
                print(f"  {idx}. {address[:8]}...{address[-8:]} (Balance: {balance:,})")
            print()
            
        finally:
            await client.close()
        
        print(f"[Step 2/3] Buying tokens with {sol_amount_in_sol} SOL ({sol_amount_lamports:,} lamports) via Jupiter...")
        
        async with JupiterSwap(private_key) as jupiter:
            swap_result: SwapResult = await jupiter.execute_swap(
                output_mint=token_mint,
                amount=sol_amount_lamports,
                verify_balance=True
            )
            
            if not swap_result.success:
                print(f"Error: Swap failed - {swap_result.message}")
                return False
            
            print(f"Swap successful!\n")
        
        print("Waiting for transaction to settle...")
        await asyncio.sleep(5)
        
        print(f"[Step 3/3] Distributing tokens equally to {len(holder_addresses)} top holders...")
        
        transfer_success = await transfer_tokens_to_multiple(
            private_key=private_key,
            token_mint=token_mint,
            receivers=holder_addresses,
            rpc_url=rpc_url,
            amount=None
        )
        
        if not transfer_success:
            print(f"Error: Distribution failed")
            return False
        
        print(f"\n{'='*60}")
        print(f"SUCCESS")
        print(f"{'='*60}")
        print(f"Bought {token_mint} with {sol_amount_in_sol} SOL")
        print(f"Distributed equally to {len(holder_addresses)} top holders")
        print(f"{'='*60}\n")
        
        return True
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


async def main():

    config_path = "config.json"
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    
    print(f"Loading configuration from: {config_path}")
    config = load_config(config_path)
    
    success = await buy_and_distribute(config)
    
    if success:
        print("Process completed successfully!")
        sys.exit(0)
    else:
        print("Process failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
