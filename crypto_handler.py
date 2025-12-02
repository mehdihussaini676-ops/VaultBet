
import aiohttp
import asyncio
import json
import hashlib
import hmac
import discord
import os
import time
from typing import Optional, Dict, Any, List
from bitcoinlib.keys import Key
from bitcoinlib.transactions import Transaction
import hashlib

class LitecoinHandler:
    def __init__(self, api_key: str, webhook_secret: str = None, bot_instance=None, main_wallet_id: str = None):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.apirone_url = "https://apirone.com/api/v2"
        self.bot = bot_instance
        self.main_wallet_id = main_wallet_id or "ltc-5561e2f4f79ea23ac688c64fa9760bf2"
        self.house_wallet_address = None
        self.house_wallet_id = None
        self.scan_running = False
        self.balance_cache = None
        self.balance_cache_time = 0
        self.balance_cache_ttl = 30

    async def generate_deposit_address(self, user_id: str) -> Optional[str]:
        """Generate a new Litecoin deposit address via Apirone Wallet"""
        try:
            # Check if user already has an address
            try:
                with open("crypto_addresses.json", "r") as f:
                    mappings = json.load(f)
                for address, data in mappings.items():
                    if data.get("user_id") == user_id:
                        print(f"Returning existing address for user {user_id}: {address}")
                        return address
            except FileNotFoundError:
                pass

            # Generate address from main wallet
            async with aiohttp.ClientSession() as session:
                address_data = {
                    "callback": {
                        "url": f"https://{os.getenv('REPLIT_DEV_DOMAIN', 'localhost')}/webhook/apirone",
                        "method": "POST",
                        "data": {
                            "user_id": user_id,
                            "secret": self.webhook_secret or "default_secret"
                        }
                    }
                }

                url = f"{self.apirone_url}/wallets/{self.main_wallet_id}/addresses"
                headers = {"Content-Type": "application/json"}
                
                async with session.post(url, json=address_data, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        address = result.get("address")
                        
                        if address:
                            # Store address mapping
                            await self.store_address_mapping(user_id, address, self.main_wallet_id)
                            print(f"Generated new address from main wallet for user {user_id}: {address}")
                            return address
                    else:
                        error = await response.text()
                        print(f"Failed to generate address: {response.status} - {error}")
                        return None
        except Exception as e:
            print(f"Error generating address: {e}")
            return None

    async def store_address_mapping(self, user_id: str, address: str, wallet_id: str):
        """Store address to user mapping"""
        try:
            with open("crypto_addresses.json", "r") as f:
                mappings = json.load(f)
        except FileNotFoundError:
            mappings = {}

        mappings[address] = {
            "user_id": user_id,
            "wallet_id": wallet_id,
            "created_at": time.time()
        }

        with open("crypto_addresses.json", "w") as f:
            json.dump(mappings, f, indent=2)

    async def initialize_house_wallet(self):
        """Initialize or load the house wallet"""
        try:
            with open("house_wallet.json", "r") as f:
                house_data = json.load(f)
                self.house_wallet_address = house_data["address"]
                self.house_wallet_id = house_data.get("wallet_id")
                print(f"Loaded existing house wallet: {self.house_wallet_address}")
                return True
        except FileNotFoundError:
            try:
                async with aiohttp.ClientSession() as session:
                    # Create house wallet without auto-forwarding
                    wallet_data = {
                        "currency": "ltc",
                        "callback": {
                            "url": f"https://{os.getenv('REPLIT_DEV_DOMAIN', 'localhost')}/webhook/apirone",
                            "method": "POST",
                            "data": {"type": "house_wallet"}
                        }
                    }
                    
                    url = f"{self.apirone_url}/wallets"
                    headers = {"Content-Type": "application/json"}
                    
                    async with session.post(url, json=wallet_data, headers=headers) as response:
                        if response.status == 200:
                            result = await response.json()
                            wallet_id = result.get("id")
                            
                            if result.get("addresses"):
                                self.house_wallet_address = result["addresses"][0]
                                self.house_wallet_id = wallet_id
                                
                                house_data = {
                                    "address": self.house_wallet_address,
                                    "wallet_id": wallet_id,
                                    "created_at": time.time()
                                }
                                
                                with open("house_wallet.json", "w") as f:
                                    json.dump(house_data, f, indent=2)
                                
                                print(f"Created new house wallet: {self.house_wallet_address}")
                                return True
                        else:
                            print(f"Failed to create house wallet: {response.status}")
                            return False
            except Exception as e:
                print(f"Error creating house wallet: {e}")
                return False

    async def get_ltc_to_usd_rate(self) -> float:
        """Get current LTC to USD exchange rate"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["litecoin"]["usd"]
                    else:
                        return 100.0
        except Exception as e:
            print(f"Error getting exchange rate: {e}")
            return 100.0

    async def get_house_balance(self) -> float:
        """Get the current house wallet balance in LTC from blockchain (real-time confirmed balance only)"""
        if not self.house_wallet_address:
            return 0.0
        
        # Check cache first - only hit API once per 30 seconds
        current_time = time.time()
        if self.balance_cache is not None and (current_time - self.balance_cache_time) < self.balance_cache_ttl:
            return self.balance_cache
        
        # Use BlockCypher API to get confirmed balance with retry logic for rate limiting
        max_retries = 3
        retry_delay = 2
        
        try:
            async with aiohttp.ClientSession() as session:
                for attempt in range(max_retries):
                    url = f"https://api.blockcypher.com/v1/ltc/main/addrs/{self.house_wallet_address}/balance"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        if response.status == 200:
                            data = await response.json()
                            balance_satoshi = data.get('final_balance', 0)
                            balance_ltc = balance_satoshi / 100000000
                            self.balance_cache = balance_ltc
                            self.balance_cache_time = current_time
                            print(f"💰 House Balance from BlockCypher: {balance_ltc:.8f} LTC confirmed")
                            return balance_ltc
                        elif response.status == 429:
                            # Rate limited - retry with exponential backoff
                            if attempt < max_retries - 1:
                                print(f"⏳ Rate limited on balance check, retrying in {retry_delay} seconds...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                            else:
                                print(f"❌ Rate limited on balance check after {max_retries} attempts")
                                # Return cached value if available
                                if self.balance_cache is not None:
                                    print(f"📊 Using cached balance: {self.balance_cache:.8f} LTC")
                                    return self.balance_cache
                                return 0.0
                        else:
                            print(f"⚠️ BlockCypher returned status {response.status}")
                            return 0.0
        except Exception as e:
            print(f"⚠️ BlockCypher API error: {e}")
        
        # If blockchain API fails, return cached value if available
        if self.balance_cache is not None:
            return self.balance_cache
        return 0.0

    async def process_apirone_callback(self, callback_data: Dict) -> bool:
        """Process an Apirone callback for deposit detection"""
        try:
            value_satoshi = callback_data.get('value', 0)
            amount_ltc = value_satoshi / 100000000
            confirmations = callback_data.get('confirmations', 0)
            tx_hash = callback_data.get('input_transaction_hash')
            input_address = callback_data.get('input_address')
            
            # Only credit on 1+ confirmations
            if confirmations < 1:
                # Silently wait for confirmation - don't spam console
                return False
            
            # Check if already processed
            try:
                with open("processed_deposits.json", "r") as f:
                    processed = json.load(f)
            except FileNotFoundError:
                processed = {}
            
            if tx_hash in processed:
                # Silently skip duplicate - don't spam console
                return False
            
            # Get user ID from callback data
            callback_data_obj = callback_data.get('data', {})
            user_id = callback_data_obj.get('user_id')
            
            if not user_id:
                print(f"❌ No user_id in callback for address {input_address}")
                return False
            
            # Load and update user balance
            try:
                with open("balances.json", "r") as f:
                    balances = json.load(f)
            except FileNotFoundError:
                balances = {}
            
            if user_id not in balances:
                balances[user_id] = {"balance": 0.0, "deposited": 0.0, "withdrawn": 0.0, "wagered": 0.0}
            
            # Convert to USD
            ltc_price = await self.get_ltc_to_usd_rate()
            amount_usd = amount_ltc * ltc_price
            
            balances[user_id]["balance"] += amount_usd
            balances[user_id]["deposited"] += amount_usd
            
            with open("balances.json", "w") as f:
                json.dump(balances, f, indent=2)
            
            # Mark as processed
            processed[tx_hash] = {
                "user_id": user_id,
                "amount_ltc": amount_ltc,
                "amount_usd": amount_usd,
                "timestamp": time.time(),
                "confirmations": confirmations
            }
            with open("processed_deposits.json", "w") as f:
                json.dump(processed, f, indent=2)
            
            print(f"✅ Credited {amount_ltc:.8f} LTC (${amount_usd:.2f} USD) to user {user_id}")
            
            # Send notification to user
            if self.bot:
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    if user:
                        embed = discord.Embed(
                            title="✅ Deposit Confirmed & Credited!",
                            description="Your Litecoin deposit has been automatically processed",
                            color=0x00ff00
                        )
                        embed.add_field(name="💰 Amount", value=f"{amount_ltc:.8f} LTC", inline=True)
                        embed.add_field(name="💵 USD Value", value=f"${amount_usd:.2f} USD", inline=True)
                        embed.add_field(name="🔗 Transaction", value=f"`{tx_hash[:16]}...`", inline=False)
                        embed.add_field(name="✅ Confirmations", value=f"{confirmations}", inline=True)
                        embed.add_field(name="🎮 Status", value="Balance updated - ready to play!", inline=True)
                        embed.set_footer(text="Your deposit has been credited automatically!")
                        
                        await user.send(embed=embed)
                        
                        # Call log_deposit function from bot if available
                        if hasattr(self.bot, 'get_cog'):
                            from_module = __import__('bot', fromlist=['log_deposit_webhook'])
                            if hasattr(from_module, 'log_deposit_webhook'):
                                try:
                                    await from_module.log_deposit_webhook(user, amount_ltc, amount_usd, tx_hash, input_address)
                                except Exception as e:
                                    print(f"Failed to log deposit: {e}")
                except Exception as e:
                    print(f"Error notifying user {user_id}: {e}")
            
            return True
        
        except Exception as e:
            print(f"Error processing Apirone callback: {e}")
            return False

    async def withdraw_from_house_wallet(self, to_address: str, amount_ltc: float) -> Optional[str]:
        """Withdraw funds from house wallet to specified address using signed transaction"""
        if not self.house_wallet_address:
            print("❌ House wallet not initialized")
            return None

        try:
            # Check house balance first
            house_balance = await self.get_house_balance()
            if house_balance < amount_ltc:
                print(f"❌ Insufficient house balance: {house_balance:.8f} LTC < {amount_ltc:.8f} LTC")
                return None
            
            # Load house wallet private key
            try:
                with open("house_wallet.json", "r") as f:
                    wallet_data = json.load(f)
                    private_key_hex = wallet_data.get("private_key")
            except:
                print("❌ Could not load house wallet private key")
                return None
            
            if not private_key_hex:
                print("❌ No private key found in house wallet")
                return None
            
            # Create key from private key hex
            key = Key(private_key_hex, network="litecoin")
            
            # Convert amount to satoshis
            amount_satoshi = int(amount_ltc * 100000000)
            
            # Use BlockCypher API to sign and broadcast transaction
            async with aiohttp.ClientSession() as session:
                # Get unspent outputs for the house wallet
                url = f"https://api.blockcypher.com/v1/ltc/main/addrs/{self.house_wallet_address}?unspentOnly=true"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status != 200:
                        print(f"❌ Failed to get unspent outputs: {response.status}")
                        return None
                    
                    addr_data = await response.json()
                    txrefs = addr_data.get("txrefs", [])
                    
                    if not txrefs:
                        print(f"❌ No unspent outputs found for house wallet")
                        return None
                    
                    # Build simplified transaction and let BlockCypher calculate fees/change
                    tx_payload = {
                        "inputs": [{"addresses": [self.house_wallet_address]}],
                        "outputs": [{"addresses": [to_address], "value": amount_satoshi}]
                    }
                    
                    # Create transaction
                    url = "https://api.blockcypher.com/v1/ltc/main/txs/new"
                    async with session.post(url, json=tx_payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                        error_text = await response.text()
                        if response.status != 201:
                            print(f"❌ Failed to create transaction: {response.status} - {error_text}")
                            return None
                        
                        try:
                            tx_data = json.loads(error_text)
                        except:
                            print(f"❌ Invalid transaction response: {error_text}")
                            return None
                        
                        # Sign inputs with private key
                        if "tosign" not in tx_data:
                            print(f"❌ No tosign field in transaction response: {tx_data}")
                            return None
                        
                        tosign_list = tx_data.get("tosign", [])
                        if not tosign_list or all(not s for s in tosign_list):
                            print(f"❌ Empty tosign data: {tosign_list}")
                            return None
                        
                        signatures = []
                        for tosign_hex in tosign_list:
                            try:
                                if not tosign_hex:
                                    print(f"⚠️ Empty tosign hex, skipping")
                                    signatures.append("")
                                    continue
                                
                                # Sign the tosign data with the private key
                                tosign_bytes = bytes.fromhex(tosign_hex)
                                from ecdsa import SigningKey, NIST256p
                                from ecdsa.util import sigencode_der
                                
                                # Create signing key from private key hex
                                sk = SigningKey.from_string(bytes.fromhex(private_key_hex), curve=NIST256p)
                                # sign_digest takes the already-hashed data and signs it
                                signature = sk.sign_digest(tosign_bytes, sigencode=sigencode_der)
                                signatures.append(signature.hex())
                            except Exception as sign_err:
                                print(f"❌ Failed to sign transaction: {sign_err}")
                                import traceback
                                traceback.print_exc()
                                return None
                        
                        if signatures:
                            tx_data["signatures"] = signatures
                        
                        # Send signed transaction with retry logic for rate limiting
                        url = "https://api.blockcypher.com/v1/ltc/main/txs/send"
                        max_retries = 3
                        retry_delay = 2  # Start with 2 second delay
                        
                        for attempt in range(max_retries):
                            async with session.post(url, json=tx_data, timeout=aiohttp.ClientTimeout(total=10)) as send_response:
                                send_text = await send_response.text()
                                
                                if send_response.status == 201:
                                    try:
                                        result = json.loads(send_text)
                                        tx_hash = result.get("hash")
                                        print(f"✅ Withdrawal of {amount_ltc:.8f} LTC sent with tx: {tx_hash[:16]}...")
                                        return tx_hash
                                    except:
                                        print(f"❌ Invalid send response: {send_text}")
                                        return None
                                elif send_response.status == 429:
                                    # Rate limited - retry with exponential backoff
                                    if attempt < max_retries - 1:
                                        print(f"⏳ Rate limited, retrying in {retry_delay} seconds... (attempt {attempt + 1}/{max_retries})")
                                        await asyncio.sleep(retry_delay)
                                        retry_delay *= 2  # Exponential backoff
                                    else:
                                        print(f"❌ Failed to broadcast transaction after {max_retries} attempts: Rate limit exceeded")
                                        return None
                                else:
                                    print(f"❌ Failed to broadcast transaction: {send_response.status} - {send_text}")
                                    return None

        except Exception as e:
            print(f"❌ Error withdrawing from house wallet: {e}")
            import traceback
            traceback.print_exc()
            return None

    def set_bot_instance(self, bot_instance):
        """Set the Discord bot instance for sending notifications"""
        self.bot = bot_instance

# Global handler instance
ltc_handler = None

def init_litecoin_handler(api_key: str, webhook_secret: str = None, bot_instance=None, main_wallet_id: str = None):
    global ltc_handler
    ltc_handler = LitecoinHandler(api_key, webhook_secret, bot_instance, main_wallet_id)
    return ltc_handler
