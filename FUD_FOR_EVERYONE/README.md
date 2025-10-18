# Solana Token Buyer & Distributor

Buy Solana tokens with SOL and automatically send them to the top holders.

## What Does This Do?

This tool buys a Solana token and splits it equally among the top holders of that token.

**Example:** You spend 0.1 SOL to buy a token, and it automatically sends equal amounts to the top 10 holders.

---

## Setup Instructions

### Step 1: Install Python

**Windows:**
1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or newer
3. Run the installer
4. **IMPORTANT:** Check the box "Add Python to PATH" during installation
5. Click "Install Now"

**Mac:**
1. Open Terminal
2. Install Homebrew (if not installed): `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
3. Install Python: `brew install python@3.11`

**Linux:**
```bash
sudo apt update
sudo apt install python3.11
```

### Step 2: Install Dependencies

1. Open Command Prompt (Windows) or Terminal (Mac/Linux)
2. Navigate to the tool folder
3. Run:
```bash
pip install -r requirements.txt
```

---

## How to Use

### 1. Edit `config.json`

Open `config.json` and fill in:

```json
{
  "private_key": "YOUR_WALLET_PRIVATE_KEY", // Your Solana wallet private key
  "token_mint": "TOKEN_ADDRESS_YOU_WANT_TO_BUY", // The token address you want to buy
  "sol_amount": 0.1, // How much SOL to spend (0.1 = 0.1 SOL)
  "top_holders_count": 10, // How many top holders you want to send to (10 = top 10 holders)
  "rpc_url": "https://api.mainnet-beta.solana.com", // The RPC URL you want to use
  "blacklist": [] // The addresses you want to skip for example CEX addresses
}
```

**What each setting means:**

- `private_key`: Your Solana wallet private key
- `token_mint`: The token address you want to buy
- `sol_amount`: How much SOL to spend (0.1 = 0.1 SOL)
- `top_holders_count`: How many top holders to send to (10 = top 10 holders)
- `rpc_url`: Leave as default or use a faster RPC (Helius, QuickNode)
- `blacklist`: Addresses to skip (usually exchange wallets)

### 2. Run the Tool

Open Command Prompt or Terminal and run:
```bash
python main.py
```

### 3. Wait

The tool will:
1. Find the top holders
2. Buy the token with your SOL
3. Split and send tokens to each holder

---

## Example

**Want to buy a meme coin and send it to top 20 holders using 0.5 SOL?**

```json
{
  "private_key": "your_private_key_here",
  "token_mint": "TokenAddressHere",
  "sol_amount": 0.5,
  "top_holders_count": 20,
  "rpc_url": "https://api.mainnet-beta.solana.com",
  "blacklist": []
}
```

---

## Blacklist (Skip Certain Addresses)

Add addresses you want to skip in the blacklist:

```json
{
  "blacklist": [
    "AddressToSkip1",
    "AddressToSkip2"
  ]
}
```

Common use: Skip exchange wallets so tokens only go to real holders.

---

## Important Security

- **NEVER share your private key**
- Keep `config.json` safe
- Test with small amounts first

THIS IS A TOOL FOR EDUCATIONAL PURPOSES ONLY. I AM NOT RESPONSIBLE FOR ANY LOSSES YOU MAY INCUR. USE AT YOUR OWN RISK.