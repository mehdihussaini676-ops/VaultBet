
import os
from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import asyncio
import aiohttp

class CardImageGenerator:
    def __init__(self):
        self.card_width = 120
        self.card_height = 168
        self.font_size = 24
        self.card_cache = {}
        
    def get_card_color(self, suit):
        """Get color for card based on suit"""
        if suit in ['♥️', '♦️']:
            return (220, 20, 60)  # Crimson red
        else:
            return (0, 0, 0)  # Black
    
    def get_face_card_symbol(self, rank):
        """Get special symbol for face cards"""
        face_symbols = {
            'J': '🤴',
            'Q': '👸', 
            'K': '👑',
            'A': '🔱'
        }
        return face_symbols.get(rank, rank)
    
    def create_card_image(self, rank, suit):
        """Create a single card image with enhanced graphics"""
        # Create a white card background with rounded corners effect
        card = Image.new('RGB', (self.card_width, self.card_height), 'white')
        draw = ImageDraw.Draw(card)
        
        # Draw card border with shadow effect
        draw.rectangle([0, 0, self.card_width-1, self.card_height-1], outline='black', width=3)
        draw.rectangle([2, 2, self.card_width-3, self.card_height-3], outline='gray', width=1)
        
        # Add gradient effect
        for i in range(5):
            color_intensity = 250 - i * 5
            draw.rectangle([i, i, self.card_width-1-i, self.card_height-1-i], 
                         outline=(color_intensity, color_intensity, color_intensity), width=1)
        
        # Get text color
        color = self.get_card_color(suit)
        
        try:
            font = ImageFont.load_default()
            large_font = ImageFont.load_default()
        except:
            font = None
            large_font = None
        
        # Draw rank and suit
        rank_text = str(rank)
        
        # Top left corner
        if font:
            draw.text((10, 10), rank_text, fill=color, font=font)
            draw.text((10, 35), suit, fill=color, font=font)
        else:
            draw.text((10, 10), rank_text, fill=color)
            draw.text((10, 35), suit, fill=color)
        
        # Center area - show card value simply
        center_x = self.card_width // 2
        center_y = self.card_height // 2
        
        # Get card value for display
        if rank in ['J', 'Q', 'K']:
            card_value_text = "10"
        elif rank == 'A':
            card_value_text = "11"
        else:
            card_value_text = rank
        
        # Draw very large value covering most of the card
        try:
            # Try to create a much larger font
            from PIL import ImageFont
            try:
                # Use a large font size for the card value
                huge_font = ImageFont.load_default()
                # Scale up the text by drawing it multiple times with offset for bold effect
                for x_offset in range(-2, 3):
                    for y_offset in range(-2, 3):
                        draw.text((center_x - 20 + x_offset, center_y - 25 + y_offset), 
                                card_value_text, fill=color, font=huge_font)
            except:
                # Fallback - draw large text multiple times
                for x_offset in range(-3, 4):
                    for y_offset in range(-3, 4):
                        draw.text((center_x - 20 + x_offset, center_y - 25 + y_offset), 
                                card_value_text, fill=color)
        except:
            # Final fallback
            draw.text((center_x - 20, center_y - 25), card_value_text, fill=color)
        
        # Add smaller suit below value
        if font:
            bbox = draw.textbbox((0, 0), suit, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            draw.text((center_x - text_width//2, center_y + 25), suit, fill=color, font=font)
        else:
            draw.text((center_x - 10, center_y + 25), suit, fill=color)
        
        # Bottom right corner (rotated)
        if font:
            draw.text((self.card_width - 35, self.card_height - 50), rank_text, fill=color, font=font)
            draw.text((self.card_width - 35, self.card_height - 25), suit, fill=color, font=font)
        else:
            draw.text((self.card_width - 35, self.card_height - 50), rank_text, fill=color)
            draw.text((self.card_width - 35, self.card_height - 25), suit, fill=color)
        
        return card
    
    def create_back_card(self):
        """Create a face-down card with pattern"""
        card = Image.new('RGB', (self.card_width, self.card_height), (25, 25, 112))  # Dark blue back
        draw = ImageDraw.Draw(card)
        
        # Draw border
        draw.rectangle([2, 2, self.card_width-3, self.card_height-3], outline='gold', width=3)
        
        # Draw diamond pattern
        for x in range(15, self.card_width-15, 25):
            for y in range(15, self.card_height-15, 25):
                # Draw diamond shape
                points = [(x, y-8), (x+8, y), (x, y+8), (x-8, y)]
                draw.polygon(points, fill='gold', outline='white')
                
        # Add VaultBet text in center
        try:
            font = ImageFont.load_default()
            text = "VAULT"
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (self.card_width - text_width) // 2
            y = (self.card_height - text_height) // 2
            draw.text((x, y), text, fill='white', font=font)
        except:
            draw.text((self.card_width//2 - 20, self.card_height//2), "VAULT", fill='white')
        
        return card
    
    def create_hand_image(self, hand, hide_first=False):
        """Create an image showing multiple cards in a hand"""
        if not hand:
            return None
            
        # Calculate total width needed
        card_spacing = 30  # Overlap cards by this amount
        total_width = self.card_width + (len(hand) - 1) * card_spacing + 20  # Extra padding
        total_height = self.card_height + 20
        
        # Create canvas with subtle background
        canvas = Image.new('RGB', (total_width, total_height), (34, 139, 34))  # Forest green
        draw = ImageDraw.Draw(canvas)
        
        # Add felt texture effect
        for i in range(0, total_width, 3):
            for j in range(0, total_height, 3):
                if (i + j) % 6 == 0:
                    draw.point((i, j), fill=(28, 120, 28))
        
        for i, card in enumerate(hand):
            if hide_first and i == 0:
                # Create face-down card for dealer's first card
                card_img = self.create_back_card()
            else:
                rank, suit = card
                card_img = self.create_card_image(rank, suit)
            
            # Add shadow effect
            shadow_offset = 3
            shadow = Image.new('RGBA', (self.card_width + shadow_offset, self.card_height + shadow_offset), (0, 0, 0, 128))
            canvas.paste(shadow, (i * card_spacing + shadow_offset + 10, shadow_offset + 10), shadow)
            
            # Paste card onto canvas
            x_pos = i * card_spacing + 10
            canvas.paste(card_img, (x_pos, 10))
        
        return canvas
    
    def save_hand_image(self, hand, filename, hide_first=False):
        """Save hand image to file"""
        hand_img = self.create_hand_image(hand, hide_first)
        if hand_img:
            hand_img.save(filename, 'PNG')
            return filename
        return None

# Global generator instance
card_generator = CardImageGenerator()
