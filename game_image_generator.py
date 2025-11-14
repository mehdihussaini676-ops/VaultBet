
from PIL import Image, ImageDraw, ImageFont
import os
import random

class GameImageGenerator:
    def __init__(self):
        self.width = 800
        self.height = 600
        self.bg_color = (15, 23, 42)  # Dark blue background
        self.border_color = (34, 211, 238)  # Cyan
        self.green_color = (34, 197, 94)
        self.red_color = (239, 68, 68)
        self.orange_color = (251, 146, 60)
        self.white_color = (255, 255, 255)
        
        # Try multiple font paths
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc"
        ]
        
        font_loaded = False
        for font_path in font_paths:
            try:
                self.font_large = ImageFont.truetype(font_path, 48)
                self.font_medium = ImageFont.truetype(font_path, 32)
                self.font_small = ImageFont.truetype(font_path, 24)
                font_loaded = True
                print(f"✅ Loaded font from: {font_path}")
                break
            except:
                continue
        
        if not font_loaded:
            print("⚠️ Using default font - text may look basic")
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()

    def create_coinflip_image(self, result, choice, save_path):
        """Create coinflip animation image"""
        try:
            img = Image.new('RGB', (self.width, self.height), self.bg_color)
            draw = ImageDraw.Draw(img)
            
            # Draw border
            draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=3)
            
            # Draw title
            draw.text((self.width//2 - 100, 50), "COINFLIP", fill=self.white_color, font=self.font_large)
            
            # Draw coin
            center_x, center_y = self.width // 2, self.height // 2
            coin_radius = 120
            
            if result == "heads":
                coin_color = (255, 215, 0)  # Gold
                coin_text = "H"
            else:
                coin_color = (192, 192, 192)  # Silver
                coin_text = "T"
            
            # Coin shadow
            draw.ellipse([center_x - coin_radius + 5, center_y - coin_radius + 5, 
                         center_x + coin_radius + 5, center_y + coin_radius + 5], 
                        fill=(50, 50, 50))
            
            # Coin
            draw.ellipse([center_x - coin_radius, center_y - coin_radius, 
                         center_x + coin_radius, center_y + coin_radius], 
                        fill=coin_color, outline=(100, 100, 100), width=5)
            
            # Coin letter
            bbox = draw.textbbox((0, 0), coin_text, font=self.font_large)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text((center_x - text_width//2, center_y - text_height//2), 
                     coin_text, fill=self.bg_color, font=self.font_large)
            
            # Draw choice
            draw.text((50, self.height - 100), f"Your Call: {choice.upper()}", 
                     fill=self.white_color, font=self.font_small)
            draw.text((50, self.height - 60), f"Result: {result.upper()}", 
                     fill=self.green_color if result == choice else self.red_color, font=self.font_small)
            
            img.save(save_path)
            print(f"✅ Created coinflip image: {save_path}")
            return True
        except Exception as e:
            print(f"❌ Error creating coinflip image: {e}")
            return False

    def create_dice_image(self, roll, save_path):
        """Create dice roll image"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=3)
        
        # Draw title
        draw.text((self.width//2 - 80, 50), "DICE ROLL", fill=self.white_color, font=self.font_large)
        
        # Draw dice
        center_x, center_y = self.width // 2, self.height // 2
        dice_size = 150
        
        # Dice shadow
        draw.rectangle([center_x - dice_size//2 + 5, center_y - dice_size//2 + 5,
                       center_x + dice_size//2 + 5, center_y + dice_size//2 + 5],
                      fill=(50, 50, 50))
        
        # Dice
        draw.rectangle([center_x - dice_size//2, center_y - dice_size//2,
                       center_x + dice_size//2, center_y + dice_size//2],
                      fill=self.white_color, outline=(100, 100, 100), width=5)
        
        # Draw pips
        self._draw_dice_pips(draw, center_x, center_y, dice_size, roll)
        
        # Draw result
        draw.text((50, self.height - 60), f"Rolled: {roll}", 
                 fill=self.green_color, font=self.font_medium)
        
        img.save(save_path)
        return True
    
    def _draw_dice_pips(self, draw, center_x, center_y, size, number):
        """Draw pips on dice"""
        pip_radius = 12
        offset = size // 4
        
        positions = {
            1: [(center_x, center_y)],
            2: [(center_x - offset, center_y - offset), (center_x + offset, center_y + offset)],
            3: [(center_x - offset, center_y - offset), (center_x, center_y), 
                (center_x + offset, center_y + offset)],
            4: [(center_x - offset, center_y - offset), (center_x + offset, center_y - offset),
                (center_x - offset, center_y + offset), (center_x + offset, center_y + offset)],
            5: [(center_x - offset, center_y - offset), (center_x + offset, center_y - offset),
                (center_x, center_y), (center_x - offset, center_y + offset), 
                (center_x + offset, center_y + offset)],
            6: [(center_x - offset, center_y - offset), (center_x + offset, center_y - offset),
                (center_x - offset, center_y), (center_x + offset, center_y),
                (center_x - offset, center_y + offset), (center_x + offset, center_y + offset)]
        }
        
        for x, y in positions.get(number, []):
            draw.ellipse([x - pip_radius, y - pip_radius, x + pip_radius, y + pip_radius],
                        fill=(0, 0, 0))

    def create_slots_image(self, result, save_path):
        """Create slots result image"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=3)
        
        # Draw title
        draw.text((self.width//2 - 80, 50), "SLOTS", fill=self.white_color, font=self.font_large)
        
        # Draw slot machine frame
        frame_width = 600
        frame_height = 200
        frame_x = (self.width - frame_width) // 2
        frame_y = self.height // 2 - 50
        
        # Machine body
        draw.rectangle([frame_x, frame_y, frame_x + frame_width, frame_y + frame_height],
                      fill=(80, 80, 80), outline=(150, 150, 150), width=5)
        
        # Draw reels
        reel_width = 150
        reel_spacing = 50
        start_x = frame_x + 50
        
        for i, symbol in enumerate(result):
            reel_x = start_x + i * (reel_width + reel_spacing)
            
            # Reel background
            draw.rectangle([reel_x, frame_y + 40, reel_x + reel_width, frame_y + 160],
                          fill=(240, 240, 240), outline=(100, 100, 100), width=3)
            
            # Symbol
            bbox = draw.textbbox((0, 0), symbol, font=self.font_large)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            symbol_x = reel_x + (reel_width - text_width) // 2
            symbol_y = frame_y + 100 - text_height // 2
            
            draw.text((symbol_x, symbol_y), symbol, fill=(0, 0, 0), font=self.font_large)
        
        img.save(save_path)
        return True

    def create_rps_image(self, player_choice, bot_choice, save_path):
        """Create rock paper scissors image"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=3)
        
        # Draw title
        draw.text((self.width//2 - 150, 50), "ROCK PAPER SCISSORS", 
                 fill=self.white_color, font=self.font_medium)
        
        choice_emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        
        # Player side
        draw.text((100, self.height//2 - 100), "YOU", fill=self.white_color, font=self.font_medium)
        draw.text((80, self.height//2), choice_emojis[player_choice], 
                 fill=self.white_color, font=self.font_large)
        draw.text((80, self.height//2 + 80), player_choice.upper(), 
                 fill=self.green_color, font=self.font_small)
        
        # VS text
        draw.text((self.width//2 - 30, self.height//2), "VS", 
                 fill=self.orange_color, font=self.font_medium)
        
        # Bot side
        draw.text((self.width - 200, self.height//2 - 100), "BOT", 
                 fill=self.white_color, font=self.font_medium)
        draw.text((self.width - 200, self.height//2), choice_emojis[bot_choice], 
                 fill=self.white_color, font=self.font_large)
        draw.text((self.width - 220, self.height//2 + 80), bot_choice.upper(), 
                 fill=self.red_color, font=self.font_small)
        
        img.save(save_path)
        return True

    def create_mines_grid_image(self, revealed_tiles, mine_positions, diamonds_found, save_path):
        """Create mines game grid image"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=3)
        
        # Draw title
        draw.text((self.width//2 - 80, 30), "MINES", fill=self.white_color, font=self.font_large)
        
        # Draw grid (5x5)
        tile_size = 100
        grid_start_x = (self.width - 5 * tile_size) // 2
        grid_start_y = 100
        
        for row in range(5):
            for col in range(5):
                tile_idx = row * 5 + col
                x = grid_start_x + col * tile_size
                y = grid_start_y + row * tile_size
                
                if tile_idx in revealed_tiles:
                    if tile_idx in mine_positions:
                        # Mine revealed
                        draw.rectangle([x, y, x + tile_size - 5, y + tile_size - 5],
                                     fill=(150, 0, 0), outline=(255, 0, 0), width=2)
                        draw.text((x + 30, y + 25), "💣", fill=self.white_color, font=self.font_medium)
                    else:
                        # Diamond revealed
                        draw.rectangle([x, y, x + tile_size - 5, y + tile_size - 5],
                                     fill=(0, 100, 0), outline=(0, 255, 0), width=2)
                        draw.text((x + 30, y + 25), "💎", fill=self.white_color, font=self.font_medium)
                else:
                    # Unrevealed tile
                    draw.rectangle([x, y, x + tile_size - 5, y + tile_size - 5],
                                 fill=(60, 60, 60), outline=(120, 120, 120), width=2)
        
        # Draw stats
        draw.text((50, self.height - 50), f"💎 Diamonds Found: {diamonds_found}", 
                 fill=self.green_color, font=self.font_small)
        
        img.save(save_path)
        return True

    def create_plinko_image(self, position, num_buckets, multipliers, save_path):
        """Create plinko game image"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=3)
        
        # Draw title
        draw.text((self.width//2 - 80, 30), "PLINKO", fill=self.white_color, font=self.font_large)
        
        # Draw buckets
        bucket_width = 60
        bucket_spacing = 10
        total_width = num_buckets * (bucket_width + bucket_spacing)
        start_x = (self.width - total_width) // 2
        bucket_y = self.height - 120
        
        for i in range(num_buckets):
            x = start_x + i * (bucket_width + bucket_spacing)
            
            # Bucket color based on multiplier
            mult = multipliers[i]
            if mult >= 50:
                bucket_color = (255, 215, 0)  # Gold
            elif mult >= 10:
                bucket_color = self.orange_color
            elif mult >= 2:
                bucket_color = self.green_color
            else:
                bucket_color = (100, 100, 100)
            
            # Draw bucket
            draw.rectangle([x, bucket_y, x + bucket_width, bucket_y + 60],
                          fill=bucket_color, outline=(255, 255, 255), width=2)
            
            # Multiplier text
            mult_text = f"{mult}x"
            bbox = draw.textbbox((0, 0), mult_text, font=self.font_small)
            text_width = bbox[2] - bbox[0]
            draw.text((x + (bucket_width - text_width) // 2, bucket_y + 20), 
                     mult_text, fill=(0, 0, 0), font=self.font_small)
        
        # Draw ball position
        if position is not None:
            ball_x = start_x + position * (bucket_width + bucket_spacing) + bucket_width // 2
            ball_y = bucket_y - 30
            draw.ellipse([ball_x - 15, ball_y - 15, ball_x + 15, ball_y + 15],
                        fill=(255, 0, 0), outline=(255, 255, 255), width=2)
        
        img.save(save_path)
        return True

    def create_limbo_image(self, target_multiplier, won, save_path):
        """Create limbo game image"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border with cosmic effect
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=(147, 51, 234), width=3)
        
        # Draw title
        draw.text((self.width//2 - 80, 50), "LIMBO", fill=(147, 51, 234), font=self.font_large)
        
        # Draw cosmic background elements
        for _ in range(50):
            x = random.randint(50, self.width - 50)
            y = random.randint(100, self.height - 100)
            size = random.randint(2, 5)
            draw.ellipse([x, y, x + size, y + size], fill=(200, 200, 255))
        
        # Draw multiplier
        center_y = self.height // 2
        mult_text = f"{target_multiplier:.2f}x"
        bbox = draw.textbbox((0, 0), mult_text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        
        result_color = self.green_color if won else self.red_color
        draw.text((self.width//2 - text_width//2, center_y), mult_text, 
                 fill=result_color, font=self.font_large)
        
        # Result text
        result_text = "TRANSCENDED!" if won else "LOST IN THE VOID"
        bbox = draw.textbbox((0, 0), result_text, font=self.font_medium)
        text_width = bbox[2] - bbox[0]
        draw.text((self.width//2 - text_width//2, center_y + 80), result_text, 
                 fill=result_color, font=self.font_medium)
        
        img.save(save_path)
        return True

    def create_balloon_image(self, pumps, popped, save_path):
        """Create balloon game image with better sizing"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=3)
        
        # Draw title
        draw.text((self.width//2 - 100, 30), "BALLOON", fill=self.white_color, font=self.font_large)
        
        # Draw balloon with max size limit
        center_x, center_y = self.width // 2, self.height // 2
        # Cap balloon size to prevent overflow
        balloon_size = min(80 + pumps * 10, 180)
        
        if popped:
            # Explosion effect
            for _ in range(15):
                angle = random.uniform(0, 360)
                import math
                distance = random.randint(50, 100)
                x = center_x + int(distance * math.cos(math.radians(angle)))
                y = center_y + int(distance * math.sin(math.radians(angle)))
                draw.text((x, y), "💥", fill=self.red_color, font=self.font_small)
            
            draw.text((self.width//2 - 80, self.height - 80), "POPPED!", 
                     fill=self.red_color, font=self.font_large)
        else:
            # Draw balloon
            balloon_color = (255, max(0, 120 - pumps * 8), max(0, 120 - pumps * 8))
            draw.ellipse([center_x - balloon_size, center_y - balloon_size - 20,
                         center_x + balloon_size, center_y + balloon_size],
                        fill=balloon_color, outline=(200, 0, 0), width=3)
            
            # String
            draw.line([center_x, center_y + balloon_size, center_x, center_y + balloon_size + 60],
                     fill=(100, 100, 100), width=2)
            
            # Pump count
            draw.text((self.width//2 - 60, self.height - 80), f"Pumps: {pumps}", 
                     fill=self.white_color, font=self.font_medium)
        
        img.save(save_path)
        return True

    def create_dice_battle_image(self, player_roll, bot_roll, save_path):
        """Create dice battle image showing player vs bot"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=3)
        
        # Draw title
        draw.text((self.width//2 - 120, 30), "DICE BATTLE", fill=self.white_color, font=self.font_large)
        
        dice_size = 120
        
        # Player dice (left side)
        player_x = self.width // 4
        player_y = self.height // 2
        
        draw.text((player_x - 40, player_y - 120), "YOU", fill=self.white_color, font=self.font_medium)
        
        # Player dice shadow
        draw.rectangle([player_x - dice_size//2 + 5, player_y - dice_size//2 + 5,
                       player_x + dice_size//2 + 5, player_y + dice_size//2 + 5],
                      fill=(50, 50, 50))
        
        # Player dice
        draw.rectangle([player_x - dice_size//2, player_y - dice_size//2,
                       player_x + dice_size//2, player_y + dice_size//2],
                      fill=self.white_color, outline=(100, 100, 100), width=5)
        
        self._draw_dice_pips(draw, player_x, player_y, dice_size, player_roll)
        
        # Bot dice (right side)
        bot_x = 3 * self.width // 4
        bot_y = self.height // 2
        
        draw.text((bot_x - 40, bot_y - 120), "BOT", fill=self.white_color, font=self.font_medium)
        
        # Bot dice shadow
        draw.rectangle([bot_x - dice_size//2 + 5, bot_y - dice_size//2 + 5,
                       bot_x + dice_size//2 + 5, bot_y + dice_size//2 + 5],
                      fill=(50, 50, 50))
        
        # Bot dice
        draw.rectangle([bot_x - dice_size//2, bot_y - dice_size//2,
                       bot_x + dice_size//2, bot_y + dice_size//2],
                      fill=self.white_color, outline=(100, 100, 100), width=5)
        
        self._draw_dice_pips(draw, bot_x, bot_y, dice_size, bot_roll)
        
        # VS text
        draw.text((self.width//2 - 30, self.height//2 - 20), "VS", 
                 fill=self.orange_color, font=self.font_large)
        
        # Winner indicator
        if player_roll > bot_roll:
            draw.text((player_x - 60, self.height - 100), "WINNER!", fill=self.green_color, font=self.font_medium)
        elif bot_roll > player_roll:
            draw.text((bot_x - 60, self.height - 100), "WINNER!", fill=self.red_color, font=self.font_medium)
        else:
            draw.text((self.width//2 - 40, self.height - 100), "TIE!", fill=self.orange_color, font=self.font_medium)
        
        img.save(save_path)
        return True

    def create_baccarat_image(self, player_cards, banker_cards, player_total, banker_total, save_path):
        """Create baccarat game image"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=3)
        
        # Draw title
        draw.text((self.width//2 - 100, 30), "BACCARAT", fill=self.white_color, font=self.font_large)
        
        # Draw player section
        draw.text((50, 120), f"PLAYER: {player_total}", fill=self.white_color, font=self.font_medium)
        card_text = " ".join([str(c) for c in player_cards])
        draw.text((50, 160), card_text, fill=self.green_color, font=self.font_small)
        
        # Draw banker section
        draw.text((50, 280), f"BANKER: {banker_total}", fill=self.white_color, font=self.font_medium)
        card_text = " ".join([str(c) for c in banker_cards])
        draw.text((50, 320), card_text, fill=self.red_color, font=self.font_small)
        
        img.save(save_path)
        return True
