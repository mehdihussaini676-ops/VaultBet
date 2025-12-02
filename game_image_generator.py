
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
        """Create enhanced coinflip image with Bitcoin/Litecoin logos"""
        try:
            img = Image.new('RGB', (self.width, self.height), self.bg_color)
            draw = ImageDraw.Draw(img)
            
            # Draw border with gradient effect
            draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=5)
            draw.rectangle([15, 15, self.width-15, self.height-15], outline=(20, 150, 170), width=2)
            
            # Draw title with glow effect
            title_text = "COINFLIP"
            bbox = draw.textbbox((0, 0), title_text, font=self.font_large)
            text_width = bbox[2] - bbox[0]
            title_x = self.width//2 - text_width//2
            
            # Glow effect
            for offset in range(3, 0, -1):
                draw.text((title_x + offset, 50 + offset), title_text, fill=(20, 150, 170, 100), font=self.font_large)
            draw.text((title_x, 50), title_text, fill=self.white_color, font=self.font_large)
            
            # Draw coin with 3D effect
            center_x, center_y = self.width // 2, self.height // 2
            coin_radius = 140
            
            if result == "heads":
                coin_color = (247, 147, 26)  # Bitcoin orange
                coin_highlight = (255, 180, 100)
                coin_shadow_color = (180, 100, 0)
            else:
                coin_color = (52, 116, 190)  # Litecoin blue
                coin_highlight = (100, 150, 220)
                coin_shadow_color = (30, 70, 130)
            
            # Multiple shadow layers for depth
            for i in range(8, 0, -1):
                shadow_alpha = 30 - i * 3
                draw.ellipse([center_x - coin_radius + i*2, center_y - coin_radius + i*2, 
                             center_x + coin_radius + i*2, center_y + coin_radius + i*2], 
                            fill=(0, 0, 0))
            
            # Coin base
            draw.ellipse([center_x - coin_radius, center_y - coin_radius, 
                         center_x + coin_radius, center_y + coin_radius], 
                        fill=coin_shadow_color)
            
            # Coin main body
            draw.ellipse([center_x - coin_radius + 5, center_y - coin_radius + 5, 
                         center_x + coin_radius - 5, center_y + coin_radius - 5], 
                        fill=coin_color, outline=(255, 255, 255), width=8)
            
            # Highlight for 3D effect
            draw.ellipse([center_x - coin_radius//2, center_y - coin_radius + 20, 
                         center_x + coin_radius//3, center_y - coin_radius//3], 
                        fill=coin_highlight)
            
            # Inner ring detail
            draw.ellipse([center_x - coin_radius + 20, center_y - coin_radius + 20, 
                         center_x + coin_radius - 20, center_y + coin_radius - 20], 
                        outline=coin_highlight, width=3)
            
            # Draw crypto logos as simple geometric shapes
            if result == "heads":
                # Bitcoin logo - stylized B with two vertical lines
                logo_size = 80
                
                # Outer circle for B
                draw.ellipse([center_x - logo_size//2, center_y - logo_size//2,
                             center_x + logo_size//2, center_y + logo_size//2],
                            outline=self.white_color, width=8)
                
                # Vertical line on left
                draw.line([(center_x - logo_size//4, center_y - logo_size//2 - 15),
                          (center_x - logo_size//4, center_y + logo_size//2 + 15)],
                         fill=self.white_color, width=6)
                
                # Top curve of B
                draw.arc([center_x - logo_size//4, center_y - logo_size//3,
                         center_x + logo_size//2, center_y],
                        start=270, end=90, fill=self.white_color, width=8)
                
                # Bottom curve of B
                draw.arc([center_x - logo_size//4, center_y,
                         center_x + logo_size//2, center_y + logo_size//3],
                        start=270, end=90, fill=self.white_color, width=8)
                
                # Middle horizontal line
                draw.line([(center_x - logo_size//4, center_y),
                          (center_x + logo_size//3, center_y)],
                         fill=self.white_color, width=8)
                
            else:
                # Litecoin logo - stylized L
                logo_size = 80
                
                # Outer circle for L
                draw.ellipse([center_x - logo_size//2, center_y - logo_size//2,
                             center_x + logo_size//2, center_y + logo_size//2],
                            outline=self.white_color, width=8)
                
                # Vertical line of L
                draw.line([(center_x - logo_size//4, center_y - logo_size//3),
                          (center_x - logo_size//4, center_y + logo_size//3)],
                         fill=self.white_color, width=10)
                
                # Bottom horizontal of L
                draw.line([(center_x - logo_size//4, center_y + logo_size//3),
                          (center_x + logo_size//3, center_y + logo_size//3)],
                         fill=self.white_color, width=10)
                
                # Diagonal slash through L
                draw.line([(center_x - logo_size//2 + 10, center_y + 10),
                          (center_x, center_y - 10)],
                         fill=self.white_color, width=8)
            
            # Draw choice with better styling - fix clipping by adjusting position
            result_color = self.green_color if result == choice else self.red_color
            result_text = "✓ WINNER!" if result == choice else "✗ LOST"
            
            draw.text((50, self.height - 120), f"Your Call: {choice.upper()}", 
                     fill=(200, 200, 200), font=self.font_medium)
            draw.text((50, self.height - 80), f"Result: {result.upper()}", 
                     fill=self.white_color, font=self.font_medium)
            
            # Fix winner text clipping - calculate width and position properly
            bbox = draw.textbbox((0, 0), result_text, font=self.font_large)
            result_text_width = bbox[2] - bbox[0]
            # Position it with margin from right edge
            result_x = self.width - result_text_width - 60
            draw.text((result_x, self.height - 100), result_text, 
                     fill=result_color, font=self.font_large)
            
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
        """Create enhanced slots result image with casino styling"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border with vegas style
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=(255, 215, 0), width=6)
        draw.rectangle([16, 16, self.width-16, self.height-16], outline=self.border_color, width=3)
        
        # Draw title with glow
        title_text = "🎰 SLOTS 🎰"
        bbox = draw.textbbox((0, 0), title_text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        title_x = self.width//2 - text_width//2
        
        # Glow effect
        for offset in range(4, 0, -1):
            draw.text((title_x + offset, 40 + offset), title_text, fill=(255, 215, 0, 80), font=self.font_large)
        draw.text((title_x, 40), title_text, fill=(255, 215, 0), font=self.font_large)
        
        # Draw slot machine frame with gradient effect
        frame_width = 650
        frame_height = 280
        frame_x = (self.width - frame_width) // 2
        frame_y = self.height // 2 - 80
        
        # Machine outer body with metallic look
        draw.rectangle([frame_x - 10, frame_y - 10, frame_x + frame_width + 10, frame_y + frame_height + 10],
                      fill=(60, 60, 70), outline=(150, 150, 160), width=8)
        draw.rectangle([frame_x, frame_y, frame_x + frame_width, frame_y + frame_height],
                      fill=(40, 40, 50), outline=(100, 100, 110), width=5)
        
        # Draw reels with better styling
        reel_width = 170
        reel_spacing = 35
        start_x = frame_x + 40
        
        # Check if jackpot
        is_jackpot = len(set(result)) == 1
        
        # Load larger emoji font for symbols
        try:
            emoji_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 90)
        except:
            emoji_font = self.font_large
        
        for i, symbol in enumerate(result):
            reel_x = start_x + i * (reel_width + reel_spacing)
            reel_y = frame_y + 50
            reel_h = 180
            
            # Reel shadow
            draw.rectangle([reel_x + 5, reel_y + 5, reel_x + reel_width + 5, reel_y + reel_h + 5],
                          fill=(20, 20, 20))
            
            # Reel background with gradient effect
            if is_jackpot:
                # Gold background for jackpot
                draw.rectangle([reel_x, reel_y, reel_x + reel_width, reel_y + reel_h],
                              fill=(255, 235, 180), outline=(255, 215, 0), width=5)
            else:
                # Normal white background
                draw.rectangle([reel_x, reel_y, reel_x + reel_width, reel_y + reel_h],
                              fill=(245, 245, 250), outline=(180, 180, 190), width=4)
            
            # Inner border for depth
            draw.rectangle([reel_x + 5, reel_y + 5, reel_x + reel_width - 5, reel_y + reel_h - 5],
                          outline=(200, 200, 210), width=2)
            
            # Draw emoji symbol larger and centered
            # Get text bounding box for accurate centering
            bbox = draw.textbbox((0, 0), symbol, font=emoji_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # Calculate center position
            symbol_x = reel_x + (reel_width // 2) - text_width // 2
            symbol_y = reel_y + (reel_h // 2) - text_height // 2
            
            # Draw shadow for depth
            draw.text((symbol_x + 2, symbol_y + 2), symbol, font=emoji_font, fill=(100, 100, 100), embedded_color=True)
            # Main symbol - use embedded_color=True to preserve emoji colors
            draw.text((symbol_x, symbol_y), symbol, font=emoji_font, fill=self.white_color, embedded_color=True)
            
            # Shine effect on reel
            draw.polygon([(reel_x + 10, reel_y + 10), (reel_x + 40, reel_y + 10), 
                         (reel_x + 10, reel_y + 40)], fill=(255, 255, 255, 100))
        
        # Result indicator
        if is_jackpot:
            result_text = "🎉 JACKPOT! 🎉"
            result_color = (255, 215, 0)
        elif len(set(result)) == 2:
            result_text = "💰 WIN! 💰"
            result_color = self.green_color
        else:
            result_text = "Try Again"
            result_color = (150, 150, 150)
        
        bbox = draw.textbbox((0, 0), result_text, font=self.font_medium)
        text_width = bbox[2] - bbox[0]
        result_x = self.width//2 - text_width//2
        
        # Result text with glow
        for offset in range(3, 0, -1):
            draw.text((result_x + offset, self.height - 90 + offset), result_text, 
                     fill=(result_color[0]//2, result_color[1]//2, result_color[2]//2), font=self.font_medium)
        draw.text((result_x, self.height - 90), result_text, fill=result_color, font=self.font_medium)
        
        img.save(save_path)
        return True

    def create_rps_image(self, player_choice, bot_choice, save_path):
        """Create enhanced rock paper scissors image with proper symbols"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border with gradient
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=5)
        draw.rectangle([15, 15, self.width-15, self.height-15], outline=(20, 150, 170), width=2)
        
        # Draw title with glow
        title_text = "🤜 ROCK PAPER SCISSORS 🤛"
        bbox = draw.textbbox((0, 0), title_text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        title_x = self.width//2 - text_width//2
        
        for offset in range(3, 0, -1):
            draw.text((title_x + offset, 30 + offset), title_text, fill=(20, 100, 120), font=self.font_large)
        draw.text((title_x, 30), title_text, fill=self.white_color, font=self.font_large)
        
        center_y = self.height // 2
        
        def draw_choice_symbol(x, y, choice, color, is_player=True):
            """Draw the choice symbol centered in circle"""
            # Background circle
            draw.ellipse([x - 120, y - 120, x + 120, y + 120],
                        fill=color, outline=(color[0]+50, color[1]+50, color[2]+50), width=4)
            
            if choice == "rock":
                # Draw rock (fist) using simple shapes
                # Fist body
                draw.ellipse([x - 45, y - 35, x + 45, y + 45], fill=self.white_color, outline=(200, 200, 200), width=3)
                # Thumb
                draw.ellipse([x - 55, y - 10, x - 25, y + 20], fill=self.white_color, outline=(200, 200, 200), width=3)
                # Knuckle lines
                for offset in [-20, 0, 20]:
                    draw.line([(x + offset - 10, y - 15), (x + offset + 10, y - 15)], fill=(150, 150, 150), width=2)
                
            elif choice == "paper":
                # Draw paper (hand) using simple shapes
                # Palm
                draw.rectangle([x - 30, y - 10, x + 30, y + 50], fill=self.white_color, outline=(200, 200, 200), width=3)
                # Fingers
                finger_positions = [x - 35, x - 15, x + 5, x + 25]
                for fx in finger_positions:
                    draw.rectangle([fx - 8, y - 50, fx + 8, y - 5], fill=self.white_color, outline=(200, 200, 200), width=3)
                    draw.ellipse([fx - 8, y - 60, fx + 8, y - 40], fill=self.white_color, outline=(200, 200, 200), width=3)
                
            elif choice == "scissors":
                # Draw scissors using lines
                # Handle circles
                draw.ellipse([x - 25, y + 20, x - 5, y + 40], fill=self.white_color, outline=(200, 200, 200), width=3)
                draw.ellipse([x + 5, y + 20, x + 25, y + 40], fill=self.white_color, outline=(200, 200, 200), width=3)
                # Blades
                draw.line([(x - 15, y + 30), (x - 40, y - 40)], fill=self.white_color, width=8)
                draw.line([(x + 15, y + 30), (x + 40, y - 40)], fill=self.white_color, width=8)
                # Blade tips
                draw.ellipse([x - 45, y - 50, x - 35, y - 40], fill=self.white_color)
                draw.ellipse([x + 35, y - 50, x + 45, y - 40], fill=self.white_color)
        
        # Player side
        player_x = 150
        
        # Label
        label_text = "YOU"
        bbox = draw.textbbox((0, 0), label_text, font=self.font_medium)
        text_w = bbox[2] - bbox[0]
        draw.text((player_x - text_w//2, center_y - 160), label_text, 
                 fill=self.white_color, font=self.font_medium)
        
        # Draw symbol
        draw_choice_symbol(player_x, center_y, player_choice, (0, 120, 0), True)
        
        # Choice name
        choice_text = player_choice.upper()
        bbox = draw.textbbox((0, 0), choice_text, font=self.font_small)
        text_w = bbox[2] - bbox[0]
        draw.text((player_x - text_w//2, center_y + 135), choice_text, 
                 fill=self.green_color, font=self.font_small)
        
        # VS text in center with circle
        vs_x = self.width // 2
        draw.ellipse([vs_x - 50, center_y - 50, vs_x + 50, center_y + 50],
                    fill=(100, 50, 0), outline=self.orange_color, width=4)
        bbox = draw.textbbox((0, 0), "VS", font=self.font_large)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text((vs_x - text_w//2, center_y - text_h//2), "VS", 
                 fill=self.orange_color, font=self.font_large)
        
        # Bot side
        bot_x = self.width - 150
        
        # Label
        label_text = "BOT"
        bbox = draw.textbbox((0, 0), label_text, font=self.font_medium)
        text_w = bbox[2] - bbox[0]
        draw.text((bot_x - text_w//2, center_y - 160), label_text, 
                 fill=self.white_color, font=self.font_medium)
        
        # Draw symbol
        draw_choice_symbol(bot_x, center_y, bot_choice, (120, 0, 0), False)
        
        # Choice name
        choice_text = bot_choice.upper()
        bbox = draw.textbbox((0, 0), choice_text, font=self.font_small)
        text_w = bbox[2] - bbox[0]
        draw.text((bot_x - text_w//2, center_y + 135), choice_text, 
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
        """Create enhanced plinko game image with pegs"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border with gradient
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.orange_color, width=5)
        draw.rectangle([15, 15, self.width-15, self.height-15], outline=(200, 100, 0), width=2)
        
        # Draw title with glow
        title_text = "🏀 PLINKO 🏀"
        bbox = draw.textbbox((0, 0), title_text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        title_x = self.width//2 - text_width//2
        
        for offset in range(3, 0, -1):
            draw.text((title_x + offset, 25 + offset), title_text, fill=(150, 70, 0), font=self.font_large)
        draw.text((title_x, 25), title_text, fill=self.white_color, font=self.font_large)
        
        # Draw pegs in triangular pattern
        peg_rows = 10
        peg_start_y = 100
        peg_spacing_y = 35
        peg_spacing_x = 50
        
        for row in range(peg_rows):
            num_pegs = row + 3
            row_width = num_pegs * peg_spacing_x
            start_x = (self.width - row_width) // 2
            y = peg_start_y + row * peg_spacing_y
            
            for peg in range(num_pegs):
                x = start_x + peg * peg_spacing_x
                # Peg shadow
                draw.ellipse([x + 2, y + 2, x + 10, y + 10], fill=(30, 30, 30))
                # Peg
                draw.ellipse([x, y, x + 8, y + 8], fill=(200, 200, 200), outline=(150, 150, 150), width=1)
        
        # Draw buckets
        bucket_width = 55
        bucket_spacing = 5
        total_width = num_buckets * (bucket_width + bucket_spacing)
        start_x = (self.width - total_width) // 2
        bucket_y = self.height - 120
        
        for i in range(num_buckets):
            x = start_x + i * (bucket_width + bucket_spacing)
            
            # Bucket color based on multiplier
            mult = multipliers[i]
            if mult >= 50:
                bucket_color = (255, 215, 0)  # Gold
                border_color = (255, 180, 0)
            elif mult >= 10:
                bucket_color = self.orange_color
                border_color = (200, 100, 0)
            elif mult >= 2:
                bucket_color = self.green_color
                border_color = (0, 150, 0)
            else:
                bucket_color = (100, 100, 100)
                border_color = (70, 70, 70)
            
            # Bucket shadow
            draw.rectangle([x + 3, bucket_y + 3, x + bucket_width + 3, bucket_y + 63],
                          fill=(30, 30, 30))
            
            # Draw bucket with gradient effect
            draw.rectangle([x, bucket_y, x + bucket_width, bucket_y + 60],
                          fill=bucket_color, outline=border_color, width=3)
            
            # Highlight if this is the winning bucket
            if position == i:
                draw.rectangle([x + 2, bucket_y + 2, x + bucket_width - 2, bucket_y + 58],
                              outline=self.white_color, width=2)
            
            # Multiplier text
            mult_text = f"{mult}x"
            bbox = draw.textbbox((0, 0), mult_text, font=self.font_small)
            text_width = bbox[2] - bbox[0]
            text_x = x + (bucket_width - text_width) // 2
            # Shadow
            draw.text((text_x + 1, bucket_y + 21), mult_text, fill=(0, 0, 0), font=self.font_small)
            # Main text
            draw.text((text_x, bucket_y + 20), mult_text, fill=(0, 0, 0), font=self.font_small)
        
        # Draw ball position
        if position is not None:
            ball_x = start_x + position * (bucket_width + bucket_spacing) + bucket_width // 2
            ball_y = bucket_y - 35
            
            # Ball shadow
            draw.ellipse([ball_x - 17, ball_y - 13, ball_x + 17, ball_y + 17],
                        fill=(50, 50, 50))
            # Ball
            draw.ellipse([ball_x - 18, ball_y - 18, ball_x + 18, ball_y + 18],
                        fill=(255, 50, 50), outline=(200, 0, 0), width=3)
            # Ball highlight
            draw.ellipse([ball_x - 10, ball_y - 10, ball_x - 2, ball_y - 2],
                        fill=(255, 150, 150))
        
        img.save(save_path)
        return True

    def create_limbo_image(self, target_multiplier, won, save_path):
        """Create enhanced limbo game image with cosmic effects"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border with cosmic gradient
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=(147, 51, 234), width=5)
        draw.rectangle([15, 15, self.width-15, self.height-15], outline=(100, 30, 180), width=2)
        
        # Draw title with glow
        title_text = "🌌 LIMBO 🌌"
        bbox = draw.textbbox((0, 0), title_text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        title_x = self.width//2 - text_width//2
        
        for offset in range(4, 0, -1):
            draw.text((title_x + offset, 30 + offset), title_text, fill=(100, 30, 180, 100), font=self.font_large)
        draw.text((title_x, 30), title_text, fill=(147, 51, 234), font=self.font_large)
        
        # Draw cosmic background elements - stars and nebula
        for _ in range(80):
            x = random.randint(50, self.width - 50)
            y = random.randint(100, self.height - 100)
            size = random.randint(1, 4)
            # Random star colors
            star_colors = [(200, 200, 255), (255, 200, 255), (200, 255, 255), (255, 255, 200)]
            color = random.choice(star_colors)
            draw.ellipse([x, y, x + size, y + size], fill=color)
            
            # Add glow to some stars
            if random.random() < 0.3:
                glow_size = size + 4
                draw.ellipse([x - 2, y - 2, x + glow_size, y + glow_size], 
                           fill=(*color[:3], 50))
        
        # Draw cosmic swirls
        for _ in range(5):
            x = random.randint(100, self.width - 100)
            y = random.randint(150, self.height - 150)
            radius = random.randint(30, 60)
            draw.ellipse([x - radius, y - radius, x + radius, y + radius],
                        outline=(147, 51, 234, 80), width=2)
        
        # Draw multiplier in center with glow effect
        center_y = self.height // 2
        mult_text = f"{target_multiplier:.2f}x"
        
        # Use larger font for multiplier
        try:
            mult_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
        except:
            mult_font = self.font_large
        
        bbox = draw.textbbox((0, 0), mult_text, font=mult_font)
        text_width = bbox[2] - bbox[0]
        mult_x = self.width//2 - text_width//2
        
        result_color = self.green_color if won else self.red_color
        glow_color = (0, 200, 0) if won else (200, 0, 0)
        
        # Glow effect
        for offset in range(8, 0, -2):
            draw.text((mult_x + offset//2, center_y + offset//2), mult_text, 
                     fill=glow_color, font=mult_font)
        
        # Main multiplier text
        draw.text((mult_x, center_y), mult_text, fill=result_color, font=mult_font)
        
        # Result text with glow
        result_text = "✨ TRANSCENDED! ✨" if won else "🌑 LOST IN VOID 🌑"
        bbox = draw.textbbox((0, 0), result_text, font=self.font_medium)
        text_width = bbox[2] - bbox[0]
        result_x = self.width//2 - text_width//2
        
        # Glow
        for offset in range(3, 0, -1):
            draw.text((result_x + offset, center_y + 100 + offset), result_text, 
                     fill=glow_color, font=self.font_medium)
        
        draw.text((result_x, center_y + 100), result_text, 
                 fill=result_color, font=self.font_medium)
        
        img.save(save_path)
        return True

    def create_balloon_image(self, pumps, popped, save_path):
        """Create enhanced balloon game image with proper sizing"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=5)
        draw.rectangle([15, 15, self.width-15, self.height-15], outline=(20, 150, 170), width=2)
        
        # Draw title at top with glow - always visible
        title_text = "🎈 BALLOON PUMP 🎈"
        bbox = draw.textbbox((0, 0), title_text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        title_x = self.width//2 - text_width//2
        
        # Glow effect
        for offset in range(3, 0, -1):
            draw.text((title_x + offset, 25 + offset), title_text, fill=(100, 50, 50), font=self.font_large)
        draw.text((title_x, 25), title_text, fill=self.white_color, font=self.font_large)
        
        # Calculate balloon position - keep it centered and sized properly
        center_x = self.width // 2
        # Move balloon down to leave space for title
        center_y = self.height // 2 + 20
        
        # Cap balloon size more conservatively to prevent overflow
        # Max size at 140 to leave room for title and stats
        balloon_size = min(60 + pumps * 7, 140)
        
        if popped:
            # Explosion effect with varied particles
            import math
            for i in range(20):
                angle = random.uniform(0, 360)
                distance = random.randint(40, 120)
                x = center_x + int(distance * math.cos(math.radians(angle)))
                y = center_y + int(distance * math.sin(math.radians(angle)))
                
                # Vary explosion particles
                particles = ["💥", "✨", "💨", "⭐"]
                particle = random.choice(particles)
                draw.text((x, y), particle, fill=self.red_color, font=self.font_small)
            
            # Popped text
            popped_text = "💥 POPPED! 💥"
            bbox = draw.textbbox((0, 0), popped_text, font=self.font_large)
            text_width = bbox[2] - bbox[0]
            draw.text((self.width//2 - text_width//2, self.height - 100), popped_text, 
                     fill=self.red_color, font=self.font_large)
        else:
            # Calculate balloon color - gets redder as it inflates
            red_intensity = min(255, 150 + pumps * 10)
            balloon_color = (red_intensity, max(0, 100 - pumps * 5), max(0, 100 - pumps * 5))
            highlight_color = (min(255, red_intensity + 50), max(0, 150 - pumps * 5), max(0, 150 - pumps * 5))
            
            # Balloon shadow for depth
            shadow_offset = 8
            draw.ellipse([center_x - balloon_size + shadow_offset, center_y - balloon_size - 15 + shadow_offset,
                         center_x + balloon_size + shadow_offset, center_y + balloon_size + 5 + shadow_offset],
                        fill=(30, 30, 30))
            
            # Main balloon body
            draw.ellipse([center_x - balloon_size, center_y - balloon_size - 15,
                         center_x + balloon_size, center_y + balloon_size + 5],
                        fill=balloon_color, outline=(150, 0, 0), width=4)
            
            # Highlight for 3D effect
            highlight_size = balloon_size // 2
            draw.ellipse([center_x - highlight_size, center_y - balloon_size,
                         center_x + highlight_size // 2, center_y - balloon_size // 2],
                        fill=highlight_color)
            
            # Balloon knot
            knot_y = center_y + balloon_size + 5
            draw.ellipse([center_x - 8, knot_y, center_x + 8, knot_y + 16],
                        fill=(120, 40, 40), outline=(80, 20, 20), width=2)
            
            # String with curve
            string_points = [
                (center_x, knot_y + 16),
                (center_x + 5, knot_y + 30),
                (center_x - 5, knot_y + 50),
                (center_x, knot_y + 80)
            ]
            for i in range(len(string_points) - 1):
                draw.line([string_points[i], string_points[i+1]], fill=(100, 100, 100), width=3)
        
        # Pump count at bottom - always visible
        pump_text = f"Pumps: {pumps}"
        bbox = draw.textbbox((0, 0), pump_text, font=self.font_medium)
        text_width = bbox[2] - bbox[0]
        draw.text((self.width//2 - text_width//2, self.height - 60), pump_text, 
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
        """Create baccarat game image with actual card graphics"""
        # Create canvas with green felt background
        total_width = 800
        total_height = 600
        canvas = Image.new('RGB', (total_width, total_height), (34, 87, 45))
        draw = ImageDraw.Draw(canvas)
        
        # Draw border
        draw.rectangle([10, 10, total_width-10, total_height-10], outline=self.border_color, width=4)
        
        # Title with glow
        title_text = "🎴 BACCARAT 🎴"
        bbox = draw.textbbox((0, 0), title_text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        title_x = total_width//2 - text_width//2
        
        for offset in range(3, 0, -1):
            draw.text((title_x + offset, 30 + offset), title_text, fill=(20, 60, 30), font=self.font_large)
        draw.text((title_x, 30), title_text, fill=(255, 215, 0), font=self.font_large)
        
        # Import card generator
        from card_generator import CardImageGenerator
        card_gen = CardImageGenerator()
        
        # Convert numeric cards to proper format
        suits = ['♠️', '♥️', '♦️', '♣️']
        
        def convert_card(card_value):
            """Convert numeric card to (rank, suit) tuple"""
            suit = random.choice(suits)
            if card_value <= 10:
                rank = str(card_value)
            elif card_value == 11:
                rank = 'J'
            elif card_value == 12:
                rank = 'Q'
            elif card_value == 13:
                rank = 'K'
            else:
                rank = 'A'
            return (rank, suit)
        
        # Draw player section
        player_label = "PLAYER"
        draw.text((50, 100), f"{player_label}: {player_total}", fill=(255, 215, 0), font=self.font_medium)
        
        player_y = 130
        for i, card_val in enumerate(player_cards):
            rank, suit = convert_card(card_val)
            card_img = card_gen.create_card_image(rank, suit)
            x_pos = 50 + i * (card_gen.card_width + 15)
            canvas.paste(card_img, (x_pos, player_y))
        
        # Draw banker section
        banker_label = "BANKER"
        banker_y_label = 350
        draw.text((50, banker_y_label), f"{banker_label}: {banker_total}", fill=(34, 211, 238), font=self.font_medium)
        
        banker_y = 380
        for i, card_val in enumerate(banker_cards):
            rank, suit = convert_card(card_val)
            card_img = card_gen.create_card_image(rank, suit)
            x_pos = 50 + i * (card_gen.card_width + 15)
            canvas.paste(card_img, (x_pos, banker_y))
        
        canvas.save(save_path)
        return True

    def create_towers_image(self, current_level, paths_count, correct_count, save_path):
        """Create towers climbing image with path visualization"""
        img = Image.new('RGB', (self.width, self.height), self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([10, 10, self.width-10, self.height-10], outline=self.border_color, width=4)
        draw.rectangle([15, 15, self.width-15, self.height-15], outline=(20, 150, 170), width=2)
        
        # Draw title with glow
        title_text = "🏗️ TOWERS 🏗️"
        bbox = draw.textbbox((0, 0), title_text, font=self.font_large)
        text_width = bbox[2] - bbox[0]
        title_x = self.width//2 - text_width//2
        
        for offset in range(3, 0, -1):
            draw.text((title_x + offset, 25 + offset), title_text, fill=(20, 100, 120), font=self.font_large)
        draw.text((title_x, 25), title_text, fill=self.white_color, font=self.font_large)
        
        # Draw tower levels
        level_height = 55
        level_width = 500
        start_y = 100
        center_x = self.width // 2
        
        for level in range(8):
            y = start_y + level * level_height
            
            # Level color - green if completed, orange if current, gray if future
            if level < current_level:
                color = self.green_color
                border_color = (0, 180, 0)
            elif level == current_level:
                color = self.orange_color
                border_color = (255, 180, 0)
            else:
                color = (60, 60, 70)
                border_color = (100, 100, 110)
            
            # Draw level box with depth
            draw.rectangle([center_x - level_width//2 + 3, y + 3, 
                          center_x + level_width//2 + 3, y + level_height - 2],
                          fill=(30, 30, 30))
            
            draw.rectangle([center_x - level_width//2, y, 
                          center_x + level_width//2, y + level_height - 5],
                          fill=color, outline=border_color, width=3)
            
            # Level number
            level_num = f"Level {8-level}"
            draw.text((center_x - level_width//2 + 15, y + 18), level_num, 
                     fill=self.white_color, font=self.font_medium)
            
            # Draw paths indicator
            if level >= current_level:
                paths_text = f"{paths_count} paths, {correct_count} safe"
                bbox = draw.textbbox((0, 0), paths_text, font=self.font_small)
                text_w = bbox[2] - bbox[0]
                draw.text((center_x + level_width//2 - text_w - 15, y + 20), 
                         paths_text, fill=(200, 200, 200), font=self.font_small)
        
        # Draw climber emoji at current level
        if current_level < 8:
            try:
                emoji_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)
            except:
                emoji_font = self.font_large
            
            climber_y = start_y + (7 - current_level) * level_height + 5
            draw.text((center_x + level_width//2 + 30, climber_y), "🧗", 
                     font=emoji_font, embedded_color=True)
        
        # Progress bar at bottom
        progress_width = 600
        progress_x = (self.width - progress_width) // 2
        progress_y = self.height - 80
        
        # Background
        draw.rectangle([progress_x, progress_y, progress_x + progress_width, progress_y + 35],
                      fill=(60, 60, 60), outline=self.white_color, width=3)
        
        # Filled portion
        if current_level > 0:
            fill_width = int((current_level / 8) * progress_width)
            draw.rectangle([progress_x, progress_y, progress_x + fill_width, progress_y + 35],
                          fill=self.green_color)
        
        # Progress text
        progress_text = f"Progress: {current_level}/8 levels"
        bbox = draw.textbbox((0, 0), progress_text, font=self.font_medium)
        text_w = bbox[2] - bbox[0]
        draw.text((self.width//2 - text_w//2, self.height - 40), progress_text, 
                 fill=self.white_color, font=self.font_medium)
        
        img.save(save_path)
        return True

    
