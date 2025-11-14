
import os
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import asyncio
import aiohttp

class CardImageGenerator:
    def __init__(self):
        self.card_width = 140
        self.card_height = 200
        self.card_spacing = 10

    def get_card_color(self, suit):
        """Get color for the card suit"""
        if suit in ['♥️', '♦️']:
            return (220, 20, 60)  # Red
        else:
            return (0, 0, 0)  # Black

    def card_value(self, card):
        """Calculate the value of a single card"""
        rank = card[0]
        if rank in ['J', 'Q', 'K']:
            return 10
        elif rank == 'A':
            return 11
        else:
            return int(rank)

    def hand_value(self, hand):
        """Calculate the total value of a hand of cards"""
        value = sum(self.card_value(card) for card in hand)
        aces = sum(1 for card in hand if card[0] == 'A')
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value

    def format_hand(self, hand, hide_first=False):
        """Format a hand for display"""
        if hide_first:
            return f"🂠 {hand[1][0]}{hand[1][1]}"
        return " ".join(f"{card[0]}{card[1]}" for card in hand)

    def create_card_image(self, rank, suit):
        """Create a premium playing card with enhanced styling"""
        # Create card with white background and subtle shadow effect
        img = Image.new('RGB', (self.card_width, self.card_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Draw rounded border effect
        border_color = (30, 30, 30)
        draw.rectangle([0, 0, self.card_width-1, self.card_height-1], 
                      outline=border_color, width=3)
        
        # Inner border for depth
        draw.rectangle([3, 3, self.card_width-4, self.card_height-4], 
                      outline=(200, 200, 200), width=1)

        # Get colors
        color = self.get_card_color(suit)

        try:
            # Try to load fonts with better sizing
            font_rank = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            font_suit_corner = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
            font_suit_center = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 70)
        except:
            try:
                font_rank = ImageFont.truetype("arial.ttf", 36)
                font_suit_corner = ImageFont.truetype("arial.ttf", 32)
                font_suit_center = ImageFont.truetype("arial.ttf", 70)
            except:
                font_rank = ImageFont.load_default()
                font_suit_corner = ImageFont.load_default()
                font_suit_center = ImageFont.load_default()

        # Clean suit symbol
        suit_symbol = suit.replace('️', '').strip()

        # Top-left corner with shadow effect
        shadow_offset = 2
        draw.text((10 + shadow_offset, 8 + shadow_offset), rank, fill=(220, 220, 220), font=font_rank)
        draw.text((10, 8), rank, fill=color, font=font_rank)
        
        bbox = draw.textbbox((0, 0), suit_symbol, font=font_suit_corner)
        text_width = bbox[2] - bbox[0]
        suit_x = 10 + (36 - text_width) // 2
        draw.text((suit_x + shadow_offset, 48 + shadow_offset), suit_symbol, fill=(220, 220, 220), font=font_suit_corner)
        draw.text((suit_x, 48), suit_symbol, fill=color, font=font_suit_corner)

        # Bottom-right corner (upside down) with shadow
        temp_img = Image.new('RGBA', (60, 90), (255, 255, 255, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        temp_draw.text((10 + shadow_offset, 8 + shadow_offset), rank, fill=(220, 220, 220, 255), font=font_rank)
        temp_draw.text((10, 8), rank, fill=color + (255,), font=font_rank)
        
        bbox_temp = temp_draw.textbbox((0, 0), suit_symbol, font=font_suit_corner)
        text_width_temp = bbox_temp[2] - bbox_temp[0]
        temp_suit_x = 10 + (36 - text_width_temp) // 2
        temp_draw.text((temp_suit_x + shadow_offset, 48 + shadow_offset), suit_symbol, fill=(220, 220, 220, 255), font=font_suit_corner)
        temp_draw.text((temp_suit_x, 48), suit_symbol, fill=color + (255,), font=font_suit_corner)
        
        rotated = temp_img.rotate(180)
        img.paste(rotated, (self.card_width-55, self.card_height-85), rotated)

        # Center design - large suit symbol with subtle shadow
        center_x = self.card_width // 2
        center_y = self.card_height // 2

        bbox = draw.textbbox((0, 0), suit_symbol, font=font_suit_center)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Shadow
        draw.text((center_x - text_width//2 + shadow_offset, center_y - text_height//2 + shadow_offset), 
                 suit_symbol, fill=(220, 220, 220), font=font_suit_center)
        # Main symbol
        draw.text((center_x - text_width//2, center_y - text_height//2), 
                 suit_symbol, fill=color, font=font_suit_center)

        return img

    def draw_pips_betrush_style(self, draw, rank, suit_symbol, color, font):
        """Draw pips for number cards in BetRush style with better spacing"""
        try:
            value = int(rank)
        except:
            return
        
        if value < 2 or value > 10:
            return

        # Better pip positions for BetRush style
        center_x = self.card_width // 2
        center_y = self.card_height // 2
        
        # More refined positions for cleaner look
        if value == 2:
            positions = [(center_x, center_y - 35), (center_x, center_y + 35)]
        elif value == 3:
            positions = [(center_x, center_y - 40), (center_x, center_y), (center_x, center_y + 40)]
        elif value == 4:
            positions = [(center_x - 22, center_y - 28), (center_x + 22, center_y - 28),
                        (center_x - 22, center_y + 28), (center_x + 22, center_y + 28)]
        elif value == 5:
            positions = [(center_x - 22, center_y - 28), (center_x + 22, center_y - 28),
                        (center_x, center_y), (center_x - 22, center_y + 28), (center_x + 22, center_y + 28)]
        elif value == 6:
            positions = [(center_x - 22, center_y - 35), (center_x + 22, center_y - 35),
                        (center_x - 22, center_y), (center_x + 22, center_y),
                        (center_x - 22, center_y + 35), (center_x + 22, center_y + 35)]
        elif value == 7:
            positions = [(center_x - 22, center_y - 38), (center_x + 22, center_y - 38),
                        (center_x, center_y - 18), (center_x - 22, center_y + 2), 
                        (center_x + 22, center_y + 2), (center_x - 22, center_y + 22), 
                        (center_x + 22, center_y + 22)]
        elif value == 8:
            positions = [(center_x - 22, center_y - 42), (center_x + 22, center_y - 42),
                        (center_x - 22, center_y - 18), (center_x + 22, center_y - 18),
                        (center_x - 22, center_y + 6), (center_x + 22, center_y + 6),
                        (center_x - 22, center_y + 30), (center_x + 22, center_y + 30)]
        elif value == 9:
            positions = [(center_x - 25, center_y - 42), (center_x + 25, center_y - 42),
                        (center_x - 25, center_y - 22), (center_x + 25, center_y - 22),
                        (center_x, center_y - 2), (center_x - 25, center_y + 18), 
                        (center_x + 25, center_y + 18), (center_x - 25, center_y + 38), 
                        (center_x + 25, center_y + 38)]
        elif value == 10:
            positions = [(center_x - 25, center_y - 48), (center_x + 25, center_y - 48),
                        (center_x - 25, center_y - 28), (center_x + 25, center_y - 28),
                        (center_x - 25, center_y - 8), (center_x + 25, center_y - 8),
                        (center_x - 25, center_y + 12), (center_x + 25, center_y + 12),
                        (center_x - 25, center_y + 32), (center_x + 25, center_y + 32)]
        else:
            positions = []

        # Draw each pip with better centering
        for x, y in positions:
            bbox = draw.textbbox((0, 0), suit_symbol, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text((x - text_width//2, y - text_height//2), suit_symbol, fill=color, font=font)

    def draw_pips(self, draw, rank, suit_symbol, color, font):
        """Legacy method - redirects to BetRush style"""
        self.draw_pips_betrush_style(draw, rank, suit_symbol, color, font)

    def create_back_card(self):
        """Create a modern face-down card with sleek design"""
        img = Image.new('RGB', (self.card_width, self.card_height), (255, 255, 255))
        draw = ImageDraw.Draw(img)

        # Modern card border
        draw.rectangle([0, 0, self.card_width-1, self.card_height-1], 
                      outline=(180, 180, 180), width=2)

        # Card back pattern - modern blue gradient effect
        back_color = (30, 60, 120)
        pattern_color = (70, 130, 220)
        accent_color = (100, 160, 255)

        # Fill with back color
        draw.rectangle([2, 2, self.card_width-3, self.card_height-3], fill=back_color)

        # Modern geometric pattern
        for y in range(20, self.card_height-20, 25):
            for x in range(20, self.card_width-20, 25):
                # Diamond pattern with varying sizes
                points = [(x, y-10), (x+10, y), (x, y+10), (x-10, y)]
                draw.polygon(points, fill=pattern_color)
                # Smaller accent diamonds
                points_small = [(x, y-5), (x+5, y), (x, y+5), (x-5, y)]
                draw.polygon(points_small, fill=accent_color)

        return img

    def create_blackjack_game_image(self, player_hands, dealer_hand, current_hand_index=0, hide_dealer_first=True):
        """Create a comprehensive blackjack game image showing all hands in BetRush style"""
        if not player_hands or not dealer_hand:
            return None

        # Calculate dimensions
        max_cards_in_hand = max(len(hand) for hand in player_hands + [dealer_hand])
        total_width = max_cards_in_hand * (self.card_width + self.card_spacing) + 40
        
        # Height for dealer + player sections
        dealer_height = self.card_height + 80
        if len(player_hands) > 1:
            player_height = len(player_hands) * (self.card_height + 80)
        else:
            player_height = self.card_height + 80
        
        total_height = dealer_height + player_height + 40

        # Create canvas with green felt background like BetRush
        canvas = Image.new('RGB', (total_width, total_height), (34, 87, 45))
        draw = ImageDraw.Draw(canvas)

        try:
            title_font = ImageFont.truetype("arial.ttf", 18)
            value_font = ImageFont.truetype("arial.ttf", 16)
        except:
            title_font = ImageFont.load_default()
            value_font = ImageFont.load_default()

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
        draw.text((20, 20), f"Dealer cards: {dealer_value}", fill='white', font=title_font)
        
        dealer_y = 50
        for i, (rank, suit) in enumerate(dealer_hand):
            if i == 0 and hide_dealer_first:
                card_img = self.create_back_card()
            else:
                card_img = self.create_card_image(rank, suit)

            x_pos = 20 + i * (self.card_width + self.card_spacing)
            canvas.paste(card_img, (x_pos, dealer_y))

        # Draw player section
        player_y_start = dealer_y + self.card_height + 60

        if len(player_hands) == 1:
            # Single hand
            hand = player_hands[0]
            player_value = hand_value(hand)
            draw.text((20, player_y_start - 30), f"Your cards: {player_value}", fill='white', font=title_font)
            
            for i, (rank, suit) in enumerate(hand):
                card_img = self.create_card_image(rank, suit)
                x_pos = 20 + i * (self.card_width + self.card_spacing)
                canvas.paste(card_img, (x_pos, player_y_start))
        else:
            # Multiple hands (split)
            for hand_idx, hand in enumerate(player_hands):
                hand_y = player_y_start + hand_idx * (self.card_height + 80)
                hand_value_calc = hand_value(hand)
                
                is_current = hand_idx == current_hand_index
                indicator = "👉 " if is_current else ""
                label_color = (255, 255, 0) if is_current else (255, 255, 255)
                
                draw.text((20, hand_y - 30), f"{indicator}Hand {hand_idx + 1}: {hand_value_calc}", 
                         fill=label_color, font=title_font)
                
                for card_idx, (rank, suit) in enumerate(hand):
                    card_img = self.create_card_image(rank, suit)
                    x_pos = 20 + card_idx * (self.card_width + self.card_spacing)
                    canvas.paste(card_img, (x_pos, hand_y))

        return canvas

    def create_hand_image(self, hand, hide_first=False):
        """Create an image showing a hand of cards"""
        if not hand:
            return None

        num_cards = len(hand)
        total_width = num_cards * (self.card_width + self.card_spacing) + 40

        # Create canvas with green background
        img = Image.new('RGB', (total_width, self.card_height + 40), (34, 87, 45))

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
