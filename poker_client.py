import pygame
import socket
import threading
import json
import uuid
import os
import sys

# --- Pygame UI Helper Classes ---

class InputBox:
    """A simple input box component for Pygame."""
    def __init__(self, x, y, w, h, font, text=''):
        self.rect = pygame.Rect(x, y, w, h)
        self.color_inactive = pygame.Color('#444444')
        self.color_active = pygame.Color('white')
        self.color = self.color_inactive
        self.text = text
        self.font = font
        self.txt_surface = self.font.render(text, True, self.color)
        self.active = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.active = not self.active
            else:
                self.active = False
            self.color = self.color_active if self.active else self.color_inactive
        if event.type == pygame.KEYDOWN:
            if self.active:
                if event.key == pygame.K_RETURN:
                    # Optional: handle enter key press
                    pass
                elif event.key == pygame.K_BACKSPACE:
                    self.text = self.text[:-1]
                else:
                    self.text += event.unicode
                self.txt_surface = self.font.render(self.text, True, 'white')

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect, 2)
        screen.blit(self.txt_surface, (self.rect.x + 5, self.rect.y + 5))
        self.rect.w = max(200, self.txt_surface.get_width() + 10)


class Button:
    """A simple button component for Pygame."""
    def __init__(self, x, y, w, h, text, font, color, hover_color, callback, enabled=True):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.font = font
        self.color = color
        self.hover_color = hover_color
        self.callback = callback
        self.enabled = enabled
        self.is_hovered = False

    def handle_event(self, event):
        if not self.enabled:
            return
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.is_hovered:
                self.callback()

    def draw(self, screen):
        if self.enabled:
            current_color = self.hover_color if self.is_hovered else self.color
            pygame.draw.rect(screen, current_color, self.rect, border_radius=8)
            text_surf = self.font.render(self.text, True, pygame.Color('white'))
        else:
            pygame.draw.rect(screen, pygame.Color('gray'), self.rect, border_radius=8)
            text_surf = self.font.render(self.text, True, pygame.Color('lightgray'))

        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)

# --- Main Poker Client Class ---

class PokerClient:
    def __init__(self):
        # Pygame setup
        pygame.init()
        self.screen_width = 1200
        self.screen_height = 800
        self.screen = pygame.display.set_mode((self.screen_width, self.screen_height))
        pygame.display.set_caption("Texas Hold'em Poker")
        self.clock = pygame.time.Clock()
        self.font_sm = pygame.font.SysFont('Arial', 18)
        self.font_md = pygame.font.SysFont('Arial', 24)
        self.font_lg = pygame.font.SysFont('Arial', 32, bold=True)
        self.bg_color = pygame.Color('#0D4F3C')

        # Custom event for server messages
        self.SERVER_MESSAGE_EVENT = pygame.USEREVENT + 1
        
        # Network settings
        self.socket = None
        self.connected = False
        self.player_id = str(uuid.uuid4())
        self.player_name = ""
        
        # Game state
        self.game_data = {}
        self.current_player_id = None
        self.dealer_player_id = None
        self.scene = 'connecting' # Manages which screen to show: 'connecting' or 'game'

        # Card images
        self.card_images = {}
        self.card_back_image = None
        self.load_card_images()
        
        # UI Elements
        self.buttons = {}
        self.setup_ui_elements()

    def load_card_images(self):
        """Load all card images using Pygame."""
        cards_folder = "cards"
        if not os.path.exists(cards_folder):
            print("Error: 'cards' folder not found!")
            sys.exit()

        try:
            back_path = os.path.join(cards_folder, "back_design.jpg")
            img = pygame.image.load(back_path).convert()
            self.card_back_image = pygame.transform.scale(img, (75, 105))

            suits = ['club', 'diamond', 'heart', 'spade']
            ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
            for suit in suits:
                for rank in ranks:
                    filename = f"{suit}_{rank}.jpg"
                    filepath = os.path.join(cards_folder, filename)
                    if os.path.exists(filepath):
                        img = pygame.image.load(filepath).convert()
                        self.card_images[filename] = pygame.transform.scale(img, (75, 105))
                    else:
                        print(f"Warning: Card image not found: {filename}")
        except Exception as e:
            print(f"Error loading card images: {e}")
            sys.exit()

    def setup_ui_elements(self):
        """Initialize UI elements like buttons and input boxes."""
        # Connection Screen
        self.ip_input = InputBox(450, 280, 300, 40, self.font_md, "localhost")
        self.name_input = InputBox(450, 380, 300, 40, self.font_md)
        self.connect_button = Button(500, 480, 200, 50, "Connect", self.font_md, '#4CAF50', '#66BB6A', self.attempt_connection)

        # Game Screen Buttons
        actions_y = self.screen_height - 60
        self.buttons['fold'] = Button(550, actions_y, 100, 40, "Fold", self.font_md, '#FF6B6B', '#FF8E8E', self.fold_action, False)
        self.buttons['check'] = Button(660, actions_y, 100, 40, "Check", self.font_md, '#4ECDC4', '#70E0DA', self.check_action, False)
        self.buttons['call'] = Button(770, actions_y, 100, 40, "Call", self.font_md, '#45B7D1', '#68C8E0', self.call_action, False)
        self.buttons['raise'] = Button(880, actions_y, 100, 40, "Raise", self.font_md, '#FFA07A', '#FFB799', self.raise_action, False)
        self.buttons['all_in'] = Button(990, actions_y, 100, 40, "All In", self.font_md, '#9B59B6', '#B17ACC', self.all_in_action, False)
        self.buttons['start'] = Button(10, self.screen_height - 60, 200, 40, "Start New Hand", self.font_md, '#27AE60', '#48C97A', self.start_game, True)
        self.raise_input_active = False # Flag to show raise input
        self.raise_input_box = InputBox(self.screen_width // 2 - 100, self.screen_height // 2 - 20, 200, 40, self.font_md)
        self.confirm_raise_button = Button(self.screen_width // 2 - 50, self.screen_height // 2 + 40, 100, 40, "Confirm", self.font_md, '#4CAF50', '#66BB6A', self.confirm_raise)


    def connect_to_server(self, server_ip, port=8888):
        """Connect to the poker server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((server_ip, port))
            self.connected = True
            
            join_message = {'type': 'join', 'player_id': self.player_id, 'name': self.player_name}
            self.socket.send(json.dumps(join_message).encode('utf-8') + b'\n')
            
            threading.Thread(target=self.listen_to_server, daemon=True).start()
            self.scene = 'game' # Switch to game scene on success
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False
            
    def attempt_connection(self):
        """Callback for the connect button."""
        server_ip = self.ip_input.text.strip()
        name = self.name_input.text.strip()
        if not server_ip or not name:
            print("Error: Please fill in all fields.")
            return
        self.player_name = name
        self.connect_to_server(server_ip)

    def listen_to_server(self):
        """Listen for messages from the server in a separate thread."""
        buffer = ""
        while self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break
                buffer += data
                while '\n' in buffer:
                    msg_str, buffer = buffer.split('\n', 1)
                    if msg_str.strip():
                        message = json.loads(msg_str)
                        # Post a custom event to the main thread's event queue
                        pygame.event.post(pygame.event.Event(self.SERVER_MESSAGE_EVENT, {'message': message}))
            except Exception as e:
                print(f"Listen error: {e}")
                break
        self.connected = False
        print("Disconnected from server.")

    def handle_server_message(self, message):
        """Process messages from the server on the main thread."""
        msg_type = message.get('type')
        if msg_type == 'join_success':
            print("Successfully joined the game.")
        elif msg_type == 'join_failed':
            print(f"Failed to join: {message.get('message')}")
            self.scene = 'connecting' # Revert to connection screen
        elif msg_type == 'game_update':
            self.game_data = message.get('data', {})
            self.update_ui_from_gamestate()
        elif msg_type == 'game_result':
            # This could be handled by drawing a popup message
            print(f"Game Result: {message.get('message')}")
        elif msg_type == 'action_failed' or msg_type == 'error':
             print(f"Server message: {message.get('message')}")

    def update_ui_from_gamestate(self):
        """Update button states and other UI info based on new game data."""
        if not self.game_data:
            return
            
        self.current_player_id = self.game_data.get('current_player_id')
        self.dealer_player_id = self.game_data.get('dealer_player_id')
        game_state = self.game_data.get('game_state', 'waiting')

        is_my_turn = (self.current_player_id == self.player_id and game_state in ['pre_flop', 'flop', 'turn', 'river'])
        
        # Disable all action buttons by default
        for key in ['fold', 'check', 'call', 'raise', 'all_in']:
            self.buttons[key].enabled = False

        if is_my_turn:
            my_data = self.game_data.get('players', {}).get(self.player_id)
            if my_data and not my_data.get('is_folded') and not my_data.get('is_all_in'):
                current_bet = self.game_data.get('current_bet', 0)
                my_bet = my_data.get('current_bet', 0)
                my_chips = my_data.get('chips', 0)

                self.buttons['fold'].enabled = True
                self.buttons['all_in'].enabled = my_chips > 0

                if current_bet == my_bet:
                    self.buttons['check'].enabled = True
                    self.buttons['call'].text = "Call"
                else:
                    call_amount = current_bet - my_bet
                    if my_chips >= call_amount:
                        self.buttons['call'].enabled = True
                        self.buttons['call'].text = f"Call ${call_amount}"
                
                # Simple raise logic: can raise if you have more chips than the call amount
                if my_chips > (current_bet - my_bet):
                    self.buttons['raise'].enabled = True

        # Start button visibility
        self.buttons['start'].enabled = (game_state in ['waiting', 'game_over'])

    def run(self):
        """Main game loop."""
        running = True
        while running:
            # Event handling
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                
                if self.scene == 'connecting':
                    self.ip_input.handle_event(event)
                    self.name_input.handle_event(event)
                    self.connect_button.handle_event(event)
                
                elif self.scene == 'game':
                    if self.raise_input_active:
                        self.raise_input_box.handle_event(event)
                        self.confirm_raise_button.handle_event(event)
                    else:
                        for button in self.buttons.values():
                            button.handle_event(event)

                if event.type == self.SERVER_MESSAGE_EVENT:
                    self.handle_server_message(event.message)

            # Drawing
            self.screen.fill(self.bg_color)
            if self.scene == 'connecting':
                self.draw_connection_screen()
            elif self.scene == 'game':
                self.draw_game_screen()
                if self.raise_input_active:
                    self.draw_raise_dialog()

            pygame.display.flip()
            self.clock.tick(30) # Limit frame rate to 30 FPS

        # Cleanup
        if self.socket:
            self.socket.close()
        pygame.quit()
        sys.exit()

    # --- Drawing Methods ---
    def draw_text(self, text, font, color, x, y, center=False):
        """Helper to draw text on screen."""
        text_surface = font.render(str(text), True, color)
        text_rect = text_surface.get_rect()
        if center:
            text_rect.center = (x, y)
        else:
            text_rect.topleft = (x, y)
        self.screen.blit(text_surface, text_rect)

    def draw_connection_screen(self):
        self.draw_text("Texas Hold'em Poker", self.font_lg, 'white', self.screen_width / 2, 100, center=True)
        self.draw_text("Server IP:", self.font_md, 'white', self.screen_width / 2, 250, center=True)
        self.ip_input.draw(self.screen)
        self.draw_text("Your Name:", self.font_md, 'white', self.screen_width / 2, 350, center=True)
        self.name_input.draw(self.screen)
        self.connect_button.draw(self.screen)

    def draw_game_screen(self):
        """Draws the main poker table UI."""
        # Draw Pot and Game State
        pot = self.game_data.get('pot', 0)
        self.draw_text(f"Pot: ${pot}", self.font_lg, 'yellow', self.screen_width / 2, 20, center=True)
        
        game_state_str = self.game_data.get('game_state', 'Waiting').replace('_', ' ').title()
        if self.current_player_id and self.current_player_id == self.player_id:
            game_state_str += " - Your Turn!"
        self.draw_text(game_state_str, self.font_md, 'white', self.screen_width / 2, 60, center=True)

        # Draw Community Cards
        community_cards = self.game_data.get('community_cards', [])
        start_x = (self.screen_width - len(community_cards) * 85) / 2
        for i, card in enumerate(community_cards):
            img = self.card_images.get(card['image'])
            if img:
                self.screen.blit(img, (start_x + i * 85, 200))

        # Draw players
        players = self.game_data.get('players', {})
        other_players = {pid: p for pid, p in players.items() if pid != self.player_id}
        
        # Draw other players at the top
        for i, (pid, player) in enumerate(other_players.items()):
            x = 100 + i * 200
            y = 100
            self.draw_player_info(player, x, y, pid)

        # Draw my player info at the bottom
        my_player_data = players.get(self.player_id)
        if my_player_data:
            self.draw_player_info(my_player_data, self.screen_width / 2 - 100, self.screen_height - 250, self.player_id, is_me=True)

        # Draw buttons
        for button in self.buttons.values():
            button.draw(self.screen)

    def draw_player_info(self, player_data, x, y, pid, is_me=False):
        """Draws a single player's information box."""
        name = player_data.get('name', 'Unknown')
        chips = player_data.get('chips', 0)
        bet = player_data.get('current_bet', 0)
        cards = player_data.get('cards', [])

        # Highlight current player and dealer
        border_color = 'gray'
        if pid == self.current_player_id: border_color = 'cyan'
        
        box_rect = pygame.Rect(x, y, 180, 160)
        pygame.draw.rect(self.screen, pygame.Color('#1A5D4A'), box_rect, border_radius=10)
        pygame.draw.rect(self.screen, pygame.Color(border_color), box_rect, 2, border_radius=10)

        display_name = name
        if pid == self.dealer_player_id: display_name += " (D)"
        self.draw_text(display_name, self.font_md, 'white', x + 10, y + 5)
        self.draw_text(f"Chips: ${chips}", self.font_sm, 'white', x + 10, y + 35)
        self.draw_text(f"Bet: ${bet}", self.font_sm, 'yellow', x + 10, y + 55)

        # Draw status like FOLDED or ALL-IN
        status_text = ""
        if player_data.get('is_folded'): status_text = "FOLDED"
        if player_data.get('is_all_in'): status_text = "ALL IN"
        if status_text:
             self.draw_text(status_text, self.font_md, 'red', box_rect.centerx, y + 140, center=True)

        # Draw cards
        for i, card_info in enumerate(cards):
            # For other players, the server sends card_back.jpg image name
            img = self.card_images.get(card_info['image']) if 'image' in card_info and card_info['image'] != 'card_back.jpg' else self.card_back_image
            if img:
                 card_pos_y = y - 110 if not is_me else y + 80
                 self.screen.blit(img, (x + 10 + i * 85, card_pos_y))
    
    def draw_raise_dialog(self):
        """Draws a modal dialog for entering a raise amount."""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # Dialog box
        dialog_rect = pygame.Rect(self.screen_width // 2 - 150, self.screen_height // 2 - 100, 300, 200)
        pygame.draw.rect(self.screen, self.bg_color, dialog_rect, border_radius=15)
        pygame.draw.rect(self.screen, 'white', dialog_rect, 2, border_radius=15)
        
        self.draw_text("Raise Amount:", self.font_md, 'white', dialog_rect.centerx, dialog_rect.y + 30, center=True)
        self.raise_input_box.draw(self.screen)
        self.confirm_raise_button.draw(self.screen)


    # --- Action Methods ---
    def send_action(self, action, amount=0):
        if not self.connected:
            print("Not connected to server.")
            return
        message = {'type': 'action', 'player_id': self.player_id, 'action': action, 'amount': amount}
        try:
            self.socket.send(json.dumps(message).encode('utf-8') + b'\n')
        except Exception as e:
            print(f"Error sending action: {e}")
            self.connected = False

    def fold_action(self): self.send_action('fold')
    def check_action(self): self.send_action('check')
    def call_action(self): self.send_action('call')
    def all_in_action(self): self.send_action('all_in')
    def start_game(self): self.send_action('start_game')

    def raise_action(self):
        self.raise_input_active = True
        my_data = self.game_data.get('players', {}).get(self.player_id, {})
        current_bet = self.game_data.get('current_bet', 0)
        min_raise_increment = self.game_data.get('big_blind', 20)
        min_raise = current_bet + min_raise_increment
        self.raise_input_box.text = str(min_raise) # Pre-fill with min raise amount

    def confirm_raise(self):
        try:
            amount = int(self.raise_input_box.text)
            self.send_action('raise', amount)
            self.raise_input_active = False
            self.raise_input_box.text = "" # Clear for next time
        except ValueError:
            print("Invalid raise amount. Please enter a number.")


if __name__ == '__main__':
    client = PokerClient()
    client.run()