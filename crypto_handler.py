import aiohttp
import asyncio
import json
import hashlib
import hmac
import discord
import os
import time
from typing import Optional, Dict, Any, List

class LitecoinHandler:
    def __init__(self, api_key: str, webhook_secret: str = None, bot_instance=None):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.base_url = "https://api.blockcypher.com/v1/ltc/main"
        self.bot = bot_instance
        self.monitoring_addresses = set()
        self.pending_transactions = {}
        self.house_wallet_address = None
        self.house_wallet_private_key = None
        self.scan_running = False

    async def generate_deposit_address(self, user_id: str) -> Optional[str]:
        """Generate a new deposit address for a user"""
        try:
            # Check if user already has an address
            try:
                with open("crypto_addresses.json", "r") as f:
                    mappings = json.load(f)

                # Find existing address for this user
                for address, data in mappings.items():
                    if data.get("user_id") == user_id:
                        print(f"Returning existing address for user {user_id}: {address}")
                        return address
            except FileNotFoundError:
                pass

            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/addrs"
                params = {"token": self.api_key}

                async with session.post(url, params=params) as response:
                    if response.status == 201:
                        data = await response.json()
                        address = data["address"]
                        private_key = data["private"]

                        # Store the address mapping
                        await self.store_address_mapping(user_id, address, private_key)

                        # Add to monitoring
                        self.monitoring_addresses.add(address)

                        print(f"Generated new address for user {user_id}: {address}")
                        return address
                    else:
                        error_text = await response.text()
                        print(f"Failed to generate address: HTTP {response.status} - {error_text}")
                        return None
        except Exception as e:
            print(f"Error generating address: {e}")
            return None

    async def store_address_mapping(self, user_id: str, address: str, private_key: str):
        """Store address to user mapping"""
        try:
            with open("crypto_addresses.json", "r") as f:
                mappings = json.load(f)
        except FileNotFoundError:
            mappings = {}

        mappings[address] = {
            "user_id": user_id,
            "private_key": private_key,
            "created_at": time.time()
        }

        with open("crypto_addresses.json", "w") as f:
            json.dump(mappings, f, indent=2)

    async def setup_webhook(self, address: str):
        """Set up webhooks to monitor both unconfirmed and confirmed transactions"""
        try:
            async with aiohttp.ClientSession() as session:
                params = {"token": self.api_key}

                # Webhook for unconfirmed transactions
                unconfirmed_webhook = {
                    "event": "unconfirmed-tx",
                    "address": address,
                    "url": "https://vaultbot-gambling.replit.app/webhook/litecoin"
                }

                # Webhook for confirmed transactions
                confirmed_webhook = {
                    "event": "confirmed-tx",
                    "address": address,
                    "url": "https://vaultbot-gambling.replit.app/webhook/litecoin"
                }

                # Set up both webhooks
                for webhook_data in [unconfirmed_webhook, confirmed_webhook]:
                    url = f"{self.base_url}/hooks"
                    async with session.post(url, json=webhook_data, params=params) as response:
                        if response.status == 201:
                            webhook_response = await response.json()
                            print(f"✅ Webhook set up for address {address} - event: {webhook_data['event']}")
                            print(f"   Webhook ID: {webhook_response.get('id', 'Unknown')}")
                        else:
                            error_text = await response.text()
                            print(f"❌ Failed to set up webhook for {webhook_data['event']}: HTTP {response.status}")
                            print(f"   Error: {error_text}")

                            # Try to parse error response
                            try:
                                error_data = json.loads(error_text)
                                if 'error' in error_data:
                                    print(f"   API Error: {error_data['error']}")
                            except:
                                pass

                # Add to monitoring set
                self.monitoring_addresses.add(address)

        except Exception as e:
            print(f"Error setting up webhook: {e}")

    async def initialize_house_wallet(self):
        """Initialize or load the house wallet"""
        try:
            with open("house_wallet.json", "r") as f:
                house_data = json.load(f)
                self.house_wallet_address = house_data["address"]
                self.house_wallet_private_key = house_data["private_key"]
                print(f"Loaded existing house wallet: {self.house_wallet_address}")
                return True
        except FileNotFoundError:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self.base_url}/addrs"
                    params = {"token": self.api_key}

                    async with session.post(url, params=params) as response:
                        if response.status == 201:
                            data = await response.json()
                            self.house_wallet_address = data["address"]
                            self.house_wallet_private_key = data["private"]

                            house_data = {
                                "address": self.house_wallet_address,
                                "private_key": self.house_wallet_private_key,
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

    async def get_address_balance(self, address: str) -> float:
        """Get the balance of a specific address in LTC"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/addrs/{address}/balance"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["balance"] / 100000000
                    else:
                        return 0.0
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0.0

    async def get_house_balance(self) -> float:
        """Get the current house wallet balance in LTC"""
        if not self.house_wallet_address:
            return 0.0
        return await self.get_address_balance(self.house_wallet_address)

    async def scan_address_for_deposits(self, address: str) -> List[Dict]:
        """Scan a specific address for new deposits"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/addrs/{address}/full"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        transactions = data.get('txs', [])

                        new_deposits = []

                        for tx in transactions:
                            tx_hash = tx['hash']
                            confirmations = tx.get('confirmations', 0)

                            # Only process confirmed transactions (1+ confirmations)
                            if confirmations >= 1:
                                # Check if this is an incoming transaction
                                for output in tx.get('outputs', []):
                                    if address in output.get('addresses', []):
                                        amount_satoshis = output.get('value', 0)
                                        amount_ltc = amount_satoshis / 100000000

                                        if amount_ltc > 0:
                                            new_deposits.append({
                                                'tx_hash': tx_hash,
                                                'amount_ltc': amount_ltc,
                                                'confirmations': confirmations,
                                                'address': address
                                            })

                        return new_deposits
                    else:
                        return []
        except Exception as e:
            print(f"Error scanning address {address}: {e}")
            return []

    async def process_deposit(self, deposit: Dict, user_id: str):
        """Process a confirmed deposit for a user"""
        try:
            amount_ltc = deposit['amount_ltc']
            tx_hash = deposit['tx_hash']

            # Convert to USD
            ltc_price = await self.get_ltc_to_usd_rate()
            amount_usd = amount_ltc * ltc_price

            # Load and update user balance
            if os.path.exists("balances.json"):
                with open("balances.json", "r") as f:
                    balances = json.load(f)
            else:
                balances = {}

            if user_id not in balances:
                balances[user_id] = {"balance": 0.0, "deposited": 0.0, "withdrawn": 0.0, "wagered": 0.0}

            balances[user_id]["balance"] += amount_usd
            balances[user_id]["deposited"] += amount_usd

            with open("balances.json", "w") as f:
                json.dump(balances, f, indent=2)

            # Update house balance stats
            if os.path.exists("house_balance.json"):
                with open("house_balance.json", "r") as f:
                    house_stats = json.load(f)
            else:
                house_stats = {"balance_ltc": 0.0, "balance_usd": 0.0, "total_deposits": 0.0, "total_withdrawals": 0.0}

            house_stats['total_deposits'] += amount_usd
            
            with open("house_balance.json", "w") as f:
                json.dump(house_stats, f, indent=2)

            print(f"✅ Processed deposit: {amount_ltc:.8f} LTC (${amount_usd:.2f}) for user {user_id}")

            # Notify user if bot is available
            if self.bot:
                try:
                    user = self.bot.get_user(int(user_id))
                    if user:
                        embed = discord.Embed(
                            title="✅ Deposit Confirmed & Credited!",
                            description="Your Litecoin deposit has been automatically processed",
                            color=0x00ff00
                        )
                        embed.add_field(name="💰 Amount", value=f"{amount_ltc:.8f} LTC", inline=True)
                        embed.add_field(name="💵 USD Value", value=f"${amount_usd:.2f} USD", inline=True)
                        embed.add_field(name="🔗 Transaction", value=f"`{tx_hash[:16]}...`", inline=False)
                        embed.add_field(name="🎮 Status", value="Balance updated - ready to play!", inline=True)
                        embed.set_footer(text="Your deposit has been credited automatically!")

                        await user.send(embed=embed)

                        # Log deposit
                        from main import log_deposit
                        await log_deposit(user, amount_usd)

                except Exception as e:
                    print(f"Error notifying user {user_id}: {e}")

            # Forward to house wallet
            await self.forward_deposit_to_house(deposit['address'], amount_ltc)

            return True

        except Exception as e:
            print(f"Error processing deposit: {e}")
            return False

    async def forward_deposit_to_house(self, from_address: str, amount_ltc: float):
        """Forward deposit from user address to house wallet"""
        try:
            if not self.house_wallet_address:
                print("❌ House wallet not initialized")
                return None

            # Load address mappings to get private key
            with open("crypto_addresses.json", "r") as f:
                mappings = json.load(f)

            if from_address not in mappings:
                print(f"❌ Address {from_address} not found in mappings")
                return None

            private_key = mappings[from_address]["private_key"]

            # Calculate fee and amount to send
            fee_satoshis = 2000  # ~0.00002 LTC
            total_satoshis = int(amount_ltc * 100000000)
            amount_to_send = total_satoshis - fee_satoshis

            if amount_to_send <= 0:
                print("Amount too small to forward after fees")
                return None

            async with aiohttp.ClientSession() as session:
                # Create transaction
                tx_data = {
                    "inputs": [{"addresses": [from_address]}],
                    "outputs": [{"addresses": [self.house_wallet_address], "value": amount_to_send}]
                }

                url = f"{self.base_url}/txs/new"
                params = {"token": self.api_key}

                async with session.post(url, json=tx_data, params=params) as response:
                    if response.status == 201:
                        tx_skeleton = await response.json()
                        tx_skeleton["privkeys"] = [private_key]

                        # Send signed transaction
                        send_url = f"{self.base_url}/txs/send"
                        async with session.post(send_url, json=tx_skeleton, params=params) as send_response:
                            if send_response.status == 201:
                                result = await send_response.json()
                                forwarded_ltc = amount_to_send / 100000000
                                print(f"✅ Forwarded {forwarded_ltc:.8f} LTC to house wallet: {result['tx']['hash']}")
                                return result["tx"]["hash"]
                            else:
                                error_text = await send_response.text()
                                print(f"❌ Failed to send forward transaction: {error_text}")
                                return None
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed to create forward transaction: {error_text}")
                        return None

        except Exception as e:
            print(f"❌ Error forwarding to house wallet: {e}")
            return None

    async def start_blockchain_scanner(self):
        """Start the automatic blockchain scanner"""
        if self.scan_running:
            print("⚠️ Blockchain scanner already running")
            return

        self.scan_running = True
        print("🔍 Starting automatic blockchain scanner...")

        # Load existing processed transactions
        try:
            with open("processed_deposits.json", "r") as f:
                processed_deposits = json.load(f)
        except FileNotFoundError:
            processed_deposits = {}

        while self.scan_running:
            try:
                # Load address mappings
                try:
                    with open("crypto_addresses.json", "r") as f:
                        address_mappings = json.load(f)
                except FileNotFoundError:
                    address_mappings = {}

                deposits_processed = 0

                for address, addr_data in address_mappings.items():
                    user_id = addr_data['user_id']

                    # Scan for deposits
                    deposits = await self.scan_address_for_deposits(address)

                    for deposit in deposits:
                        tx_hash = deposit['tx_hash']

                        # Skip if already processed
                        if tx_hash in processed_deposits:
                            continue

                        # Process the deposit
                        success = await self.process_deposit(deposit, user_id)

                        if success:
                            processed_deposits[tx_hash] = {
                                'user_id': user_id,
                                'amount_ltc': deposit['amount_ltc'],
                                'address': address,
                                'processed_at': time.time()
                            }
                            deposits_processed += 1

                # Save processed deposits
                if deposits_processed > 0:
                    with open("processed_deposits.json", "w") as f:
                        json.dump(processed_deposits, f, indent=2)
                    print(f"🔍 Processed {deposits_processed} new deposits")

                # Wait before next scan
                await asyncio.sleep(30)  # Scan every 30 seconds

            except Exception as e:
                print(f"❌ Error in blockchain scanner: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def stop_blockchain_scanner(self):
        """Stop the blockchain scanner"""
        self.scan_running = False
        print("🛑 Blockchain scanner stopped")

    async def withdraw_from_house_wallet(self, to_address: str, amount_ltc: float) -> Optional[str]:
        """Withdraw funds from house wallet to specified address"""
        if not self.house_wallet_address or not self.house_wallet_private_key:
            print("❌ House wallet not initialized")
            return None

        try:
            house_balance = await self.get_house_balance()
            if house_balance < amount_ltc:
                print(f"❌ Insufficient house balance: {house_balance:.8f} LTC < {amount_ltc:.8f} LTC")
                return None

            fee_satoshis = 2000
            amount_satoshis = int(amount_ltc * 100000000)
            amount_to_send = amount_satoshis - fee_satoshis

            if amount_to_send <= 0:
                print("❌ Amount too small after fees")
                return None

            async with aiohttp.ClientSession() as session:
                tx_data = {
                    "inputs": [{"addresses": [self.house_wallet_address]}],
                    "outputs": [{"addresses": [to_address], "value": amount_to_send}]
                }

                url = f"{self.base_url}/txs/new"
                params = {"token": self.api_key}

                async with session.post(url, json=tx_data, params=params) as response:
                    if response.status == 201:
                        tx_skeleton = await response.json()
                        tx_skeleton["privkeys"] = [self.house_wallet_private_key]

                        send_url = f"{self.base_url}/txs/send"
                        async with session.post(send_url, json=tx_skeleton, params=params) as send_response:
                            if send_response.status == 201:
                                result = await send_response.json()
                                actual_amount = amount_to_send / 100000000
                                print(f"✅ Withdrew {actual_amount:.8f} LTC from house wallet: {result['tx']['hash']}")
                                return result["tx"]["hash"]
                            else:
                                error_text = await send_response.text()
                                print(f"❌ Failed to send withdrawal: {error_text}")
                                return None
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed to create withdrawal: {error_text}")
                        return None

        except Exception as e:
            print(f"❌ Error withdrawing from house wallet: {e}")
            return None

    def set_bot_instance(self, bot_instance):
        """Set the Discord bot instance for sending notifications"""
        self.bot = bot_instance

# Global handler instance
ltc_handler = None

def init_litecoin_handler(api_key: str, webhook_secret: str = None, bot_instance=None):
    global ltc_handler
    ltc_handler = LitecoinHandler(api_key, webhook_secret, bot_instance)
    return ltc_handler
