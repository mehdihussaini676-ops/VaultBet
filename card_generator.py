
import os
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import asyncio
import aiohttp

class CardImageGenerator:
    def __init__(self):
        self.card_width = 200
        self.card_height = 280
        self.card_spacing = 20

    def get_card_color(self, suit):
        """Get color for the card suit"""
        if suit in ['♥️', '♦️']:
            return (220, 20, 60)  # Crimson red
        else:
            return (30, 30, 30)  # Dark black

    def draw_dots_for_value(self, draw, rank, suit_color, card_width, card_height):
        """Draw dots corresponding to card value"""
        if rank in ['J', 'Q', 'K', 'A']:
            return  # Face cards and Aces don't get dots
        
        try:
            value = int(rank)
        except:
            return
        
        if value < 1 or value > 10:
            return
        
        dot_size = 8
        dot_color = suit_color
        
        # Define dot positions for each number
        center_x = card_width // 2
        center_y = card_height // 2
        
        positions = {
            1: [(center_x, center_y)],
            2: [(center_x, center_y - 30), (center_x, center_y + 30)],
            3: [(center_x, center_y - 35), (center_x, center_y), (center_x, center_y + 35)],
            4: [(center_x - 20, center_y - 25), (center_x + 20, center_y - 25), 
                (center_x - 20, center_y + 25), (center_x + 20, center_y + 25)],
            5: [(center_x - 20, center_y - 25), (center_x + 20, center_y - 25), (center_x, center_y),
                (center_x - 20, center_y + 25), (center_x + 20, center_y + 25)],
            6: [(center_x - 20, center_y - 30), (center_x + 20, center_y - 30),
                (center_x - 20, center_y), (center_x + 20, center_y),
                (center_x - 20, center_y + 30), (center_x + 20, center_y + 30)],
            7: [(center_x - 20, center_y - 35), (center_x + 20, center_y - 35), (center_x, center_y - 15),
                (center_x - 20, center_y + 5), (center_x + 20, center_y + 5),
                (center_x - 20, center_y + 25), (center_x + 20, center_y + 25)],
            8: [(center_x - 20, center_y - 35), (center_x + 20, center_y - 35), 
                (center_x - 20, center_y - 15), (center_x + 20, center_y - 15),
                (center_x - 20, center_y + 5), (center_x + 20, center_y + 5),
                (center_x - 20, center_y + 25), (center_x + 20, center_y + 25)],
            9: [(center_x - 25, center_y - 35), (center_x, center_y - 35), (center_x + 25, center_y - 35),
                (center_x - 25, center_y), (center_x, center_y), (center_x + 25, center_y),
                (center_x - 25, center_y + 35), (center_x, center_y + 35), (center_x + 25, center_y + 35)],
            10: [(center_x - 25, center_y - 40), (center_x, center_y - 40), (center_x + 25, center_y - 40),
                 (center_x - 25, center_y - 15), (center_x + 25, center_y - 15),
                 (center_x - 25, center_y + 10), (center_x + 25, center_y + 10),
                 (center_x - 25, center_y + 35), (center_x, center_y + 35), (center_x + 25, center_y + 35)]
        }
        
        if value in positions:
            for pos in positions[value]:
                x, y = pos
                # Draw dot with subtle shadow
                draw.ellipse([x - dot_size//2 + 1, y - dot_size//2 + 1, 
                             x + dot_size//2 + 1, y + dot_size//2 + 1], 
                            fill=(200, 200, 200))  # Shadow
                draw.ellipse([x - dot_size//2, y - dot_size//2, 
                             x + dot_size//2, y + dot_size//2], 
                            fill=dot_color)

    def create_card_image(self, rank, suit):
        """Create a professional-looking single card image with dots"""
        # Create card with gradient background
        img = Image.new('RGB', (self.card_width, self.card_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Draw rounded rectangle border with shadow effect
        border_color = (180, 180, 180)
        shadow_color = (120, 120, 120)

        # Shadow effect
        draw.rounded_rectangle([3, 3, self.card_width-1, self.card_height-1], 
                              radius=15, fill=shadow_color)

        # Main card body with subtle gradient effect
        draw.rounded_rectangle([0, 0, self.card_width-3, self.card_height-3], 
                              radius=15, fill='white', outline=border_color, width=2)

        # Inner border for premium look
        draw.rounded_rectangle([4, 4, self.card_width-7, self.card_height-7], 
                              radius=12, outline=(240, 240, 240), width=1)

        # Get colors
        color = self.get_card_color(suit)

        try:
            # Try to load better fonts
            font_large = ImageFont.truetype("arial.ttf", 36)
            font_medium = ImageFont.truetype("arial.ttf", 28)
            font_small = ImageFont.truetype("arial.ttf", 20)
        except:
            try:
                font_large = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 36)
                font_medium = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 28)
                font_small = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 20)
            except:
                # Fallback to default
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()

        # Clean suit symbol
        suit_symbol = suit.replace('️', '').strip()

        # Top-left corner with better positioning
        draw.text((15, 15), rank, fill=color, font=font_large)
        draw.text((15, 55), suit_symbol, fill=color, font=font_medium)

        # Draw dots for numbered cards
        self.draw_dots_for_value(draw, rank, color, self.card_width, self.card_height)

        # For face cards, draw large center suit
        if rank in ['J', 'Q', 'K', 'A']:
            center_x = self.card_width // 2
            center_y = self.card_height // 2

            # Large center suit with better font
            try:
                center_font = ImageFont.truetype("arial.ttf", 48)
            except:
                center_font = font_large

            bbox = draw.textbbox((0, 0), suit_symbol, font=center_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text((center_x - text_width//2, center_y - text_height//2), 
                     suit_symbol, fill=color, font=center_font)

            # Add rank letter for face cards
            if rank in ['J', 'Q', 'K']:
                try:
                    rank_font = ImageFont.truetype("arial.ttf", 32)
                except:
                    rank_font = font_large
                
                bbox = draw.textbbox((0, 0), rank, font=rank_font)
                text_width = bbox[2] - bbox[0]
                draw.text((center_x - text_width//2, center_y + 25), 
                         rank, fill=color, font=rank_font)

        # Bottom-right corner (rotated) with better positioning
        bottom_x = self.card_width - 45
        bottom_y = self.card_height - 65

        # Create temporary image for rotated text
        temp_img = Image.new('RGBA', (80, 80), (255, 255, 255, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        temp_draw.text((20, 15), rank, fill=color, font=font_medium)
        temp_draw.text((20, 45), suit_symbol, fill=color, font=font_small)

        # Rotate and paste
        rotated = temp_img.rotate(180)
        img.paste(rotated, (bottom_x-20, bottom_y-20), rotated)

        return img

    def create_back_card(self):
        """Create a face-down card with enhanced design"""
        img = Image.new('RGB', (self.card_width, self.card_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Shadow effect
        draw.rounded_rectangle([3, 3, self.card_width-1, self.card_height-1], 
                              radius=15, fill=(120, 120, 120))

        # Card back with enhanced pattern
        back_color = (25, 25, 112)  # Dark blue
        pattern_color = (65, 105, 225)  # Royal blue
        accent_color = (100, 149, 237)  # Cornflower blue

        draw.rounded_rectangle([0, 0, self.card_width-3, self.card_height-3], 
                              radius=15, fill=back_color, outline=(100, 100, 100), width=2)

        # Enhanced diamond pattern
        for y in range(25, self.card_height-25, 30):
            for x in range(25, self.card_width-25, 30):
                # Draw diamond shape with gradient effect
                points = [(x, y-10), (x+10, y), (x, y+10), (x-10, y)]
                draw.polygon(points, fill=pattern_color)
                # Small inner diamond
                inner_points = [(x, y-5), (x+5, y), (x, y+5), (x-5, y)]
                draw.polygon(inner_points, fill=accent_color)

        # Border decoration with multiple layers
        draw.rounded_rectangle([8, 8, self.card_width-11, self.card_height-11], 
                              radius=12, outline=pattern_color, width=2)
        draw.rounded_rectangle([12, 12, self.card_width-15, self.card_height-15], 
                              radius=10, outline=accent_color, width=1)

        return img

    def create_blackjack_game_image(self, player_hands, dealer_hand, current_hand_index=0, hide_dealer_first=True):
        """Create a comprehensive blackjack game image showing all hands"""
        if not player_hands or not dealer_hand:
            return None

        # Calculate dimensions for multiple hands
        max_player_cards = max(len(hand) for hand in player_hands) if player_hands else 0
        dealer_cards = len(dealer_hand)
        max_cards = max(max_player_cards, dealer_cards)
        
        # Base width calculation
        hand_width = max_cards * self.card_width + (max_cards - 1) * self.card_spacing
        
        # Calculate width based on the longest hand (since split hands are now vertical)
        canvas_width = hand_width + 40

        # Height calculation: dealer + space + all player hands
        dealer_section_height = self.card_height + 60  # Cards + labels
        if len(player_hands) > 1:
            # For split hands, each additional hand needs full height
            player_section_height = len(player_hands) * (self.card_height + 60) + 40
        else:
            player_section_height = self.card_height + 60

        total_height = dealer_section_height + player_section_height + 20

        # Create canvas with Discord-like background
        canvas = Image.new('RGB', (canvas_width, total_height), (54, 57, 63))
        draw = ImageDraw.Draw(canvas)

        try:
            title_font = ImageFont.truetype("arial.ttf", 24)
            label_font = ImageFont.truetype("arial.ttf", 18)
            small_font = ImageFont.truetype("arial.ttf", 14)
        except:
            title_font = ImageFont.load_default()
            label_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # Calculate hand values
        def hand_value(hand):
            value = 0
            aces = 0
            for rank, suit in hand:
                if rank in ['J', 'Q', 'K']:
                    value += 10
                elif rank == 'A':
                    aces += 1
                    value += 11
                else:
                    value += int(rank)
            while value > 21 and aces:
                value -= 10
                aces -= 1
            return value

        # Draw dealer section
        dealer_value = hand_value(dealer_hand) if not hide_dealer_first else "?"
        dealer_label = f"🤖 Dealer - Value: {dealer_value}"
        draw.text((20, 10), dealer_label, fill='white', font=title_font)
        
        dealer_y = 40
        for i, (rank, suit) in enumerate(dealer_hand):
            if i == 0 and hide_dealer_first:
                card_img = self.create_back_card()
            else:
                card_img = self.create_card_image(rank, suit)

            x_pos = 20 + i * (self.card_width + self.card_spacing)
            canvas.paste(card_img, (x_pos, dealer_y))

        # Draw player section
        player_y_start = dealer_y + self.card_height + 40

        if len(player_hands) == 1:
            # Single hand
            hand = player_hands[0]
            player_value = hand_value(hand)
            player_label = f"🃏 Player - Value: {player_value}"
            draw.text((20, player_y_start - 25), player_label, fill='white', font=title_font)
            
            for i, (rank, suit) in enumerate(hand):
                card_img = self.create_card_image(rank, suit)
                x_pos = 20 + i * (self.card_width + self.card_spacing)
                canvas.paste(card_img, (x_pos, player_y_start))
        else:
            # Multiple hands (split) - show vertically
            draw.text((20, player_y_start - 25), "🃏 Player Hands (Split)", fill='white', font=title_font)
            
            # Calculate vertical layout for multiple hands
            hand_vertical_spacing = self.card_height + 60  # Space between hands vertically
            
            for hand_idx, hand in enumerate(player_hands):
                hand_x = 20
                hand_y = player_y_start + hand_idx * hand_vertical_spacing
                
                # Draw hand indicator
                hand_value_calc = hand_value(hand)
                is_current = hand_idx == current_hand_index
                indicator = "👉 " if is_current else "   "
                status = " (ACTIVE)" if is_current else " (DONE)" if hand_idx < current_hand_index else ""
                
                hand_label = f"{indicator}Hand {hand_idx + 1}: {hand_value_calc}{status}"
                label_color = (255, 255, 0) if is_current else (255, 255, 255)
                draw.text((hand_x, hand_y - 20), hand_label, fill=label_color, font=label_font)
                
                # Draw cards for this hand
                for card_idx, (rank, suit) in enumerate(hand):
                    card_img = self.create_card_image(rank, suit)
                    card_x = hand_x + card_idx * (self.card_width + self.card_spacing)
                    canvas.paste(card_img, (card_x, hand_y))

        return canvas

    def create_combined_hand_image(self, player_hand, dealer_hand, hide_dealer_first=False):
        """Create a combined image showing both player and dealer hands (legacy method)"""
        return self.create_blackjack_game_image([player_hand], dealer_hand, 0, hide_dealer_first)

    def create_hand_image(self, hand, hide_first=False):
        """Create an image showing a hand of cards"""
        if not hand:
            return None

        num_cards = len(hand)
        total_width = num_cards * self.card_width + (num_cards - 1) * self.card_spacing + 40

        # Create canvas
        img = Image.new('RGB', (total_width, self.card_height + 40), (54, 57, 63))

        for i, (rank, suit) in enumerate(hand):
            if i == 0 and hide_first:
                card_img = self.create_back_card()
            else:
                card_img = self.create_card_image(rank, suit)

            x_pos = 20 + i * (self.card_width + self.card_spacing)
            img.paste(card_img, (x_pos, 20))

        return img

    def save_hand_image(self, hand, filename, hide_first=False):
        """Save hand image to file"""
        img = self.create_hand_image(hand, hide_first)
        if img:
            img.save(filename)
            return True
        return False

    def save_blackjack_game_image(self, player_hands, dealer_hand, filename, current_hand_index=0, hide_dealer_first=True):
        """Save comprehensive blackjack game image to file"""
        img = self.create_blackjack_game_image(player_hands, dealer_hand, current_hand_index, hide_dealer_first)
        if img:
            img.save(filename)
            return True
        return False

    def save_combined_game_image(self, player_hand, dealer_hand, filename, hide_dealer_first=False):
        """Save combined game image to file (legacy method)"""
        return self.save_blackjack_game_image([player_hand], dealer_hand, filename, 0, hide_dealer_first)
