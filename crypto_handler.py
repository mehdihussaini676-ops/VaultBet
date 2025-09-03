import aiohttp
import asyncio
import json
import hashlib
import hmac
import discord
import os
from typing import Optional, Dict, Any, List

class LitecoinHandler:
    def __init__(self, api_key: str, webhook_secret: str = None, bot_instance=None):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.base_url = "https://api.blockcypher.com/v1/ltc/main"
        self.bot = bot_instance
        self.monitoring_addresses = set()
        self.pending_transactions = {}  # tx_hash -> user_info
        self.house_wallet_address = None
        self.house_wallet_private_key = None

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

                        # Set up webhook
                        await self.setup_webhook(address)

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
        """Store address to user mapping (implement proper encryption for private keys)"""
        # Load existing mappings
        try:
            with open("crypto_addresses.json", "r") as f:
                mappings = json.load(f)
        except FileNotFoundError:
            mappings = {}

        # Store mapping (encrypt private_key in production!)
        mappings[address] = {
            "user_id": user_id,
            "private_key": private_key,  # ENCRYPT THIS IN PRODUCTION
            "created_at": asyncio.get_event_loop().time()
        }

        # Save mappings
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
            # Try to load existing house wallet
            with open("house_wallet.json", "r") as f:
                house_data = json.load(f)
                self.house_wallet_address = house_data["address"]
                self.house_wallet_private_key = house_data["private_key"]
                print(f"Loaded existing house wallet: {self.house_wallet_address}")
                return True
        except FileNotFoundError:
            # Generate new house wallet
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self.base_url}/addrs"
                    params = {"token": self.api_key}

                    async with session.post(url, params=params) as response:
                        if response.status == 201:
                            data = await response.json()
                            self.house_wallet_address = data["address"]
                            self.house_wallet_private_key = data["private"]

                            # Save house wallet
                            house_data = {
                                "address": self.house_wallet_address,
                                "private_key": self.house_wallet_private_key,  # ENCRYPT IN PRODUCTION
                                "created_at": asyncio.get_event_loop().time()
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

    async def get_house_balance(self) -> float:
        """Get the current house wallet balance in LTC"""
        if not self.house_wallet_address:
            return 0.0
        return await self.get_address_balance(self.house_wallet_address)

    async def forward_to_house_wallet(self, from_address: str, private_key: str, amount_ltc: float) -> Optional[str]:
        """Forward funds from a deposit address to the house wallet"""
        if not self.house_wallet_address:
            print("House wallet not initialized")
            return None

        try:
            # Get current balance of the from_address
            current_balance = await self.get_address_balance(from_address)
            if current_balance < 0.0001:  # Need minimum balance to forward
                print(f"Insufficient balance to forward: {current_balance:.8f} LTC")
                return None

            # Calculate fee and amount to send (use most of the balance)
            fee_satoshis = 2000  # ~0.00002 LTC (higher fee for reliable forwarding)
            total_satoshis = int(current_balance * 100000000)
            amount_to_send = total_satoshis - fee_satoshis

            if amount_to_send <= 0:
                print("Amount too small to forward after fees")
                return None

            async with aiohttp.ClientSession() as session:
                # Create transaction to house wallet
                tx_data = {
                    "inputs": [{"addresses": [from_address]}],
                    "outputs": [{"addresses": [self.house_wallet_address], "value": amount_to_send}]
                }

                url = f"{self.base_url}/txs/new"
                params = {"token": self.api_key}

                async with session.post(url, json=tx_data, params=params) as response:
                    if response.status == 201:
                        tx_skeleton = await response.json()

                        # Add private key for signing
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
                                print(f"❌ Failed to send transaction: {send_response.status} - {error_text}")
                                return None
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed to create transaction: {response.status} - {error_text}")
                        return None

        except Exception as e:
            print(f"❌ Error forwarding to house wallet: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def withdraw_from_house_wallet(self, to_address: str, amount_ltc: float) -> Optional[str]:
        """Withdraw funds from house wallet to specified address"""
        if not self.house_wallet_address or not self.house_wallet_private_key:
            print("❌ House wallet not initialized")
            return None

        try:
            # Check house balance
            house_balance = await self.get_house_balance()
            if house_balance < amount_ltc:
                print(f"❌ Insufficient house balance: {house_balance:.8f} LTC < {amount_ltc:.8f} LTC")
                return None

            # Calculate fee and amount to send
            fee_satoshis = 2000  # ~0.00002 LTC
            amount_satoshis = int(amount_ltc * 100000000)
            amount_to_send = amount_satoshis - fee_satoshis

            if amount_to_send <= 0:
                print("❌ Amount too small after fees")
                return None

            async with aiohttp.ClientSession() as session:
                # Create transaction from house wallet
                tx_data = {
                    "inputs": [{"addresses": [self.house_wallet_address]}],
                    "outputs": [{"addresses": [to_address], "value": amount_to_send}]
                }

                url = f"{self.base_url}/txs/new"
                params = {"token": self.api_key}

                async with session.post(url, json=tx_data, params=params) as response:
                    if response.status == 201:
                        tx_skeleton = await response.json()

                        # Add private key for signing
                        tx_skeleton["privkeys"] = [self.house_wallet_private_key]

                        # Send signed transaction
                        send_url = f"{self.base_url}/txs/send"
                        async with session.post(send_url, json=tx_skeleton, params=params) as send_response:
                            if send_response.status == 201:
                                result = await send_response.json()
                                actual_amount = amount_to_send / 100000000
                                print(f"✅ Withdrew {actual_amount:.8f} LTC from house wallet: {result['tx']['hash']}")
                                return result["tx"]["hash"]
                            else:
                                error_text = await send_response.text()
                                print(f"❌ Failed to send withdrawal transaction: {send_response.status} - {error_text}")
                                return None
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed to create withdrawal transaction: {response.status} - {error_text}")
                        return None

        except Exception as e:
            print(f"❌ Error withdrawing from house wallet: {e}")
            import traceback
            traceback.print_exc()
            return None

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature"""
        if not self.webhook_secret:
            return True  # Skip verification if no secret is set

        expected_signature = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(signature, expected_signature)

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
                        return 100.0  # Fallback rate
        except Exception as e:
            print(f"Error getting exchange rate: {e}")
            return 100.0  # Fallback rate

    async def get_address_balance(self, address: str) -> float:
        """Get the balance of a specific address in LTC"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/addrs/{address}/balance"
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data["balance"] / 100000000  # Convert satoshis to LTC
                    else:
                        return 0.0
        except Exception as e:
            print(f"Error getting balance: {e}")
            return 0.0

    async def sweep_address_to_main_wallet(self, address: str, private_key: str, main_wallet_address: str) -> Optional[str]:
        """Sweep all funds from a deposit address to main wallet"""
        try:
            # Get current balance
            balance_ltc = await self.get_address_balance(address)

            if balance_ltc < 0.001:  # Minimum amount to sweep
                return None

            # Calculate fee (simplified - use proper fee estimation in production)
            fee_satoshis = 1000  # ~0.00001 LTC
            amount_to_send = int((balance_ltc * 100000000) - fee_satoshis)

            if amount_to_send <= 0:
                return None

            async with aiohttp.ClientSession() as session:
                # Create transaction
                tx_data = {
                    "inputs": [{"addresses": [address]}],
                    "outputs": [{"addresses": [main_wallet_address], "value": amount_to_send}]
                }

                url = f"{self.base_url}/txs/new"
                params = {"token": self.api_key}

                async with session.post(url, json=tx_data, params=params) as response:
                    if response.status == 201:
                        tx_skeleton = await response.json()

                        # Sign transaction (simplified for demo)
                        # This is where you'd use the private key to sign
                        # For production, use a proper crypto library like bitcoinlib

                        # Send signed transaction
                        send_url = f"{self.base_url}/txs/send"
                        async with session.post(send_url, json=tx_skeleton, params=params) as send_response:
                            if send_response.status == 201:
                                result = await send_response.json()
                                return result["tx"]["hash"]

                return None
        except Exception as e:
            print(f"Error sweeping address: {e}")
            return None

    async def collect_all_deposits(self, main_wallet_address: str) -> Dict[str, Any]:
        """Collect crypto from all user deposit addresses to main wallet"""
        results = {"success": [], "failed": [], "total_collected": 0.0}

        try:
            # Load address mappings
            with open("crypto_addresses.json", "r") as f:
                mappings = json.load(f)

            for address, data in mappings.items():
                try:
                    private_key = data["private_key"]
                    balance = await self.get_address_balance(address)

                    if balance >= 0.001:  # Only sweep if minimum amount
                        tx_hash = await self.sweep_address_to_main_wallet(address, private_key, main_wallet_address)

                        if tx_hash:
                            results["success"].append({
                                "address": address,
                                "amount": balance,
                                "tx_hash": tx_hash
                            })
                            results["total_collected"] += balance
                        else:
                            results["failed"].append({"address": address, "reason": "Transaction failed"})

                except Exception as e:
                    results["failed"].append({"address": address, "reason": str(e)})

        except FileNotFoundError:
            results["failed"].append({"error": "No address mappings found"})

        return results

    async def get_transaction_details(self, tx_hash: str) -> Optional[Dict]:
        """Get detailed information about a transaction"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/txs/{tx_hash}"
                async with session.get(url) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        return None
        except Exception as e:
            print(f"Error getting transaction details: {e}")
            return None

    async def start_blockchain_monitoring(self):
        """Start monitoring blockchain for transactions"""
        while True:
            try:
                await self.check_pending_transactions()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                print(f"Error in blockchain monitoring: {e}")
                await asyncio.sleep(60)  # Wait longer on error

    async def check_pending_transactions(self):
        """Check status of pending transactions"""
        try:
            # Load pending transactions from file
            try:
                with open('pending_transactions.json', 'r') as f:
                    pending_file = json.load(f)
            except FileNotFoundError:
                pending_file = {}

            # Merge file transactions with memory transactions
            for tx_hash, tx_info in pending_file.items():
                if tx_hash not in self.pending_transactions:
                    self.pending_transactions[tx_hash] = tx_info

            for tx_hash, tx_info in list(self.pending_transactions.items()):
                try:
                    if tx_info.get('confirmed'):
                        continue

                    tx_details = await self.get_transaction_details(tx_hash)
                    if tx_details:
                        confirmations = tx_details.get('confirmations', 0)
                        print(f"Checking transaction {tx_hash[:8]}... - {confirmations} confirmations")

                        if confirmations >= 1 and not tx_info.get('confirmed'):
                            # Transaction confirmed
                            print(f"Transaction {tx_hash[:8]}... confirmed! Processing...")
                            await self.handle_confirmed_transaction(tx_hash, tx_details, tx_info)
                            self.pending_transactions[tx_hash]['confirmed'] = True

                            # Update file
                            pending_file[tx_hash] = self.pending_transactions[tx_hash]
                            with open('pending_transactions.json', 'w') as f:
                                json.dump(pending_file, f, indent=2)

                except Exception as e:
                    print(f"Error checking transaction {tx_hash}: {e}")
        except Exception as e:
            print(f"Error in check_pending_transactions: {e}")

    async def handle_unconfirmed_transaction(self, tx_data: Dict, user_id: str, address: str, amount_ltc: float):
        """Handle when an unconfirmed transaction is detected"""
        try:
            if not self.bot:
                return

            user = self.bot.get_user(int(user_id))
            if not user:
                return

            # Store transaction info
            tx_hash = tx_data['hash']
            self.pending_transactions[tx_hash] = {
                'user_id': user_id,
                'address': address,
                'amount_ltc': amount_ltc,
                'confirmed': False,
                'notified_unconfirmed': True
            }

            embed = discord.Embed(
                title="🔄 Processing deposit...",
                description=f"Transaction detected (awaiting confirmations...)",
                color=0xffaa00
            )
            embed.add_field(name="💰 Amount", value=f"{amount_ltc:.8f} LTC", inline=True)
            embed.add_field(name="🔗 Transaction ID", value=f"`{tx_hash[:16]}...`", inline=True)
            embed.add_field(name="⏳ Status", value="Waiting for 1 confirmation", inline=False)
            embed.set_footer(text="Your deposit will be credited once confirmed on the blockchain")

            try:
                await user.send(embed=embed)
                print(f"Sent unconfirmed transaction notification to user {user_id}")
            except discord.Forbidden:
                print(f"Could not send DM to user {user_id}")

        except Exception as e:
            print(f"Error handling unconfirmed transaction: {e}")

    async def handle_confirmed_transaction(self, tx_hash: str, tx_data: Dict, tx_info: Dict):
        """Handle when a transaction gets confirmed and forward to house wallet"""
        try:
            if not self.bot:
                print("No bot instance available for notifications")
                return

            user_id = tx_info['user_id']
            amount_ltc = tx_info.get('amount_ltc', 0)
            deposit_address = tx_info.get('address', '')

            print(f"Processing confirmed transaction for user {user_id}: {amount_ltc} LTC")

            user = self.bot.get_user(int(user_id))
            if not user:
                print(f"Could not find user {user_id}")
                return

            # Get current LTC price for USD conversion
            ltc_price = await self.get_ltc_to_usd_rate()
            amount_usd = amount_ltc * ltc_price

            print(f"Converting {amount_ltc} LTC to ${amount_usd:.2f} USD at rate ${ltc_price:.2f}")

            # Update user balance in the main balance file
            try:
                # Load balances
                if os.path.exists("balances.json"):
                    with open("balances.json", "r") as f:
                        balances = json.load(f)
                else:
                    balances = {}

                # Initialize user if not exists
                if user_id not in balances:
                    balances[user_id] = {"balance": 0.0, "deposited": 0.0, "withdrawn": 0.0, "wagered": 0.0}

                # Add to balance and deposited
                balances[user_id]["balance"] += amount_usd
                balances[user_id]["deposited"] += amount_usd

                # Save balances
                with open("balances.json", "w") as f:
                    json.dump(balances, f)

                print(f"Updated user {user_id} balance: +${amount_usd:.2f} USD")

            except Exception as e:
                print(f"Error updating balance: {e}")

            # Forward funds to house wallet
            forwarding_success = False
            try:
                if deposit_address and os.path.exists("crypto_addresses.json") and self.house_wallet_address:
                    with open("crypto_addresses.json", "r") as f:
                        mappings = json.load(f)
                        if deposit_address in mappings:
                            private_key = mappings[deposit_address]["private_key"]

                            # Forward to house wallet
                            forward_tx = await self.forward_to_house_wallet(deposit_address, private_key, amount_ltc)
                            if forward_tx:
                                print(f"✅ Successfully forwarded deposit to house wallet: {forward_tx}")
                                forwarding_success = True
                            else:
                                print(f"❌ Failed to forward deposit to house wallet")
                        else:
                            print(f"❌ Address {deposit_address} not found in mappings")
                else:
                    if not self.house_wallet_address:
                        print(f"❌ House wallet not initialized for forwarding")
                    elif not deposit_address:
                        print(f"❌ No deposit address provided for forwarding")
                    else:
                        print(f"❌ crypto_addresses.json not found")
            except Exception as e:
                print(f"❌ Error forwarding to house wallet: {e}")

            print(f"🔄 Forwarding result for {deposit_address}: {'✅ Success' if forwarding_success else '❌ Failed'}")

            # Send notification to user
            embed = discord.Embed(
                title="✅ Deposit confirmed and credited!",
                description="Your deposit has been successfully processed",
                color=0x00ff00
            )
            embed.add_field(name="💰 Amount", value=f"{amount_ltc:.8f} LTC", inline=True)
            embed.add_field(name="💵 USD Value", value=f"${amount_usd:.2f} USD", inline=True)
            embed.add_field(name="🔗 Transaction ID", value=f"`{tx_hash}`", inline=False)
            embed.add_field(name="🎮 Status", value="Ready to play!", inline=True)
            embed.set_footer(text="Your balance has been updated automatically")

            try:
                await user.send(embed=embed)
                print(f"Sent confirmation notification to user {user_id}")
            except discord.Forbidden:
                print(f"Could not send DM to user {user_id}")
            except Exception as e:
                print(f"Error sending notification: {e}")

        except Exception as e:
            print(f"Error handling confirmed transaction: {e}")

    def set_bot_instance(self, bot_instance):
        """Set the Discord bot instance for sending notifications"""
        self.bot = bot_instance

# Global handler instance
ltc_handler = None

def init_litecoin_handler(api_key: str, webhook_secret: str = None, bot_instance=None):
    global ltc_handler
    ltc_handler = LitecoinHandler(api_key, webhook_secret, bot_instance)
    return ltc_handler
