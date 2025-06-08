import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import threading
import json
import uuid
import os
from PIL import Image, ImageTk

class PokerClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Texas Hold'em Poker")
        self.root.geometry("1200x800")
        self.root.configure(bg='#0D4F3C')  # Poker table green
        
        # Network settings
        self.socket = None
        self.connected = False
        self.player_id = str(uuid.uuid4())
        self.player_name = ""
        
        # Game state
        self.game_data = {}
        self.my_cards = []
        self.community_cards = []
        self.current_player_id = None # To explicitly track whose turn it is
        self.dealer_player_id = None # To explicitly track the dealer
        
        # Card images
        self.card_images = {}
        self.card_back_image = None
        self.load_card_images()
        
        self.player_widgets = {} # To store references to player UI elements
        
        self.setup_ui()
        self.setup_connection_dialog()
        
    def load_card_images(self):
        """Load all card images from the cards folder"""
        cards_folder = "cards"
        if not os.path.exists(cards_folder):
            messagebox.showerror("Error", "Cards folder not found! Please create a 'cards' folder with card images (e.g., heart_ace.jpg, back_design.jpg).")
            return
        
        try:
            # Load card back - changed to back_design.jpg
            back_path = os.path.join(cards_folder, "back_design.jpg")
            if os.path.exists(back_path):
                img = Image.open(back_path)
                img = img.resize((60, 84), Image.Resampling.LANCZOS)
                self.card_back_image = ImageTk.PhotoImage(img)
            else:
                print(f"Warning: {back_path} not found. Using placeholder if available.")
            
            # Load all card faces
            suits = ['club', 'diamond', 'heart', 'spade']
            ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
            
            for suit in suits:
                for rank in ranks:
                    filename = f"{suit}_{rank}.jpg"
                    filepath = os.path.join(cards_folder, filename)
                    if os.path.exists(filepath):
                        img = Image.open(filepath)
                        img = img.resize((60, 84), Image.Resampling.LANCZOS)
                        self.card_images[filename] = ImageTk.PhotoImage(img)
                    else:
                        print(f"Warning: {filepath} not found.")
                        
        except Exception as e:
            print(f"Error loading card images: {e}")
            messagebox.showwarning("Warning", "Some card images could not be loaded. Please ensure 'cards' folder contains all necessary .jpg files.")
    
    def setup_connection_dialog(self):
        """Show connection dialog at startup"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Connect to Poker Game")
        dialog.geometry("400x250")
        dialog.grab_set() # Make this dialog modal
        dialog.configure(bg='#0D4F3C')
        
        # Center the dialog
        dialog.transient(self.root)
        dialog.protocol("WM_DELETE_WINDOW", lambda: self.root.quit()) # Exit application if dialog is closed
        
        # Server IP
        tk.Label(dialog, text="Server IP:", bg='#0D4F3C', fg='white', font=('Arial', 12)).pack(pady=(10, 2))
        ip_entry = tk.Entry(dialog, font=('Arial', 12))
        ip_entry.insert(0, "localhost")  # Default IP
        ip_entry.pack(pady=5)
        
        # Player name
        tk.Label(dialog, text="Your Name:", bg='#0D4F3C', fg='white', font=('Arial', 12)).pack(pady=(10, 2))
        name_entry = tk.Entry(dialog, font=('Arial', 12))
        name_entry.pack(pady=5)
        
        def connect():
            server_ip = ip_entry.get().strip()
            name = name_entry.get().strip()
            
            if not server_ip or not name:
                messagebox.showerror("Error", "Please fill in all fields", parent=dialog)
                return
            
            self.player_name = name
            if self.connect_to_server(server_ip):
                dialog.destroy() # Close dialog on successful connection
            else:
                messagebox.showerror("Error", "Failed to connect to server. Is the server running?", parent=dialog)
        
        tk.Button(dialog, text="Connect", command=connect, 
                  bg='#4CAF50', fg='white', font=('Arial', 12), 
                  padx=20, pady=5).pack(pady=20)
        
    def setup_ui(self):
        """Setup the main game UI"""
        # Main frame
        main_frame = tk.Frame(self.root, bg='#0D4F3C')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top info panel
        info_frame = tk.Frame(main_frame, bg='#1A5D4A', relief=tk.RAISED, bd=2)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.pot_label = tk.Label(info_frame, text="Pot: $0", 
                                  bg='#1A5D4A', fg='white', font=('Arial', 16, 'bold'))
        self.pot_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.game_state_label = tk.Label(info_frame, text="Waiting for players...", 
                                         bg='#1A5D4A', fg='white', font=('Arial', 12))
        self.game_state_label.pack(side=tk.RIGHT, padx=10, pady=5)
        
        # Community cards area
        community_frame = tk.Frame(main_frame, bg='#0D4F3C')
        community_frame.pack(pady=20)
        
        tk.Label(community_frame, text="Community Cards", 
                 bg='#0D4F3C', fg='white', font=('Arial', 14, 'bold')).pack()
        
        self.community_cards_frame = tk.Frame(community_frame, bg='#0D4F3C')
        self.community_cards_frame.pack(pady=10)
        
        # Players area
        players_frame = tk.Frame(main_frame, bg='#0D4F3C')
        players_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Other players (top) - use a grid for better arrangement
        self.other_players_frame = tk.Frame(players_frame, bg='#0D4F3C')
        self.other_players_frame.pack(fill=tk.X, pady=(0, 20))
        
        # My player area (bottom)
        my_player_frame = tk.Frame(players_frame, bg='#1A5D4A', relief=tk.RAISED, bd=2)
        my_player_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        # My cards
        my_cards_frame = tk.Frame(my_player_frame, bg='#1A5D4A')
        my_cards_frame.pack(side=tk.LEFT, padx=10, pady=10)
        
        tk.Label(my_cards_frame, text="Your Cards", 
                 bg='#1A5D4A', fg='white', font=('Arial', 12, 'bold')).pack()
        
        self.my_cards_display_frame = tk.Frame(my_cards_frame, bg='#1A5D4A')
        self.my_cards_display_frame.pack()
        
        # My info
        my_info_frame = tk.Frame(my_player_frame, bg='#1A5D4A')
        my_info_frame.pack(side=tk.LEFT, padx=20, pady=10)
        
        self.my_name_label = tk.Label(my_info_frame, text=f"Player: {self.player_name}", 
                                      bg='#1A5D4A', fg='white', font=('Arial', 12, 'bold'))
        self.my_name_label.pack()
        
        self.my_chips_label = tk.Label(my_info_frame, text="Chips: $0", 
                                       bg='#1A5D4A', fg='white', font=('Arial', 11))
        self.my_chips_label.pack()
        
        self.my_bet_label = tk.Label(my_info_frame, text="Current Bet: $0", 
                                     bg='#1A5D4A', fg='white', font=('Arial', 11))
        self.my_bet_label.pack()
        
        # Action buttons
        actions_frame = tk.Frame(my_player_frame, bg='#1A5D4A')
        actions_frame.pack(side=tk.RIGHT, padx=10, pady=10)
        
        self.fold_btn = tk.Button(actions_frame, text="Fold", command=self.fold_action,
                                  bg='#FF6B6B', fg='white', font=('Arial', 10), 
                                  padx=15, pady=5, state=tk.DISABLED)
        self.fold_btn.pack(side=tk.LEFT, padx=2)
        
        self.check_btn = tk.Button(actions_frame, text="Check", command=self.check_action,
                                   bg='#4ECDC4', fg='white', font=('Arial', 10), 
                                   padx=15, pady=5, state=tk.DISABLED)
        self.check_btn.pack(side=tk.LEFT, padx=2)
        
        self.call_btn = tk.Button(actions_frame, text="Call", command=self.call_action,
                                  bg='#45B7D1', fg='white', font=('Arial', 10), 
                                  padx=15, pady=5, state=tk.DISABLED)
        self.call_btn.pack(side=tk.LEFT, padx=2)
        
        self.raise_btn = tk.Button(actions_frame, text="Raise", command=self.raise_action,
                                   bg='#FFA07A', fg='white', font=('Arial', 10), 
                                   padx=15, pady=5, state=tk.DISABLED)
        self.raise_btn.pack(side=tk.LEFT, padx=2)
        
        self.all_in_btn = tk.Button(actions_frame, text="All In", command=self.all_in_action,
                                   bg='#9B59B6', fg='white', font=('Arial', 10), 
                                   padx=15, pady=5, state=tk.DISABLED)
        self.all_in_btn.pack(side=tk.LEFT, padx=2)
        
        # Start/New Hand button
        self.start_btn = tk.Button(my_player_frame, text="Start New Hand", 
                                  command=self.start_game,
                                  bg='#27AE60', fg='white', font=('Arial', 12, 'bold'), 
                                  padx=20, pady=8)
        self.start_btn.pack(side=tk.RIGHT, padx=10, pady=10)
    
    def connect_to_server(self, server_ip, port=8888):
        """Connect to the poker server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((server_ip, port))
            self.connected = True
            
            # Send join message immediately after connecting
            join_message = {
                'type': 'join',
                'player_id': self.player_id,
                'name': self.player_name
            }
            self.socket.send(json.dumps(join_message).encode('utf-8') + b'\n') # Add newline for server parsing
            
            # Start listening thread
            listen_thread = threading.Thread(target=self.listen_to_server)
            listen_thread.daemon = True # Allow the main program to exit even if this thread is running
            listen_thread.start()
            
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False
    
    def listen_to_server(self):
        """Listen for messages from the server"""
        while self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break # Server disconnected
                
                # Handle potential partial messages (if multiple messages are sent in one packet)
                messages = data.split('\n') # Assuming server sends newline after each JSON
                for msg_str in messages:
                    if msg_str.strip(): # Ensure it's not an empty string
                        try:
                            message = json.loads(msg_str)
                            self.root.after(0, lambda m=message: self.handle_server_message(m))
                        except json.JSONDecodeError:
                            print(f"Invalid JSON received: {msg_str}")
                
            except Exception as e:
                print(f"Listen error: {e}")
                break
        
        self.connected = False
        self.root.after(0, lambda: messagebox.showinfo("Disconnected", "Lost connection to server. The game will now close."))
        self.root.after(0, self.root.quit) # Close application on disconnect
        
    def handle_server_message(self, message):
        """Handle messages from the server"""
        msg_type = message.get('type')
        
        if msg_type == 'join_success':
            self.update_status("Connected to game!")
            self.my_name_label.config(text=f"Player: {self.player_name}")
            
        elif msg_type == 'join_failed':
            messagebox.showerror("Error", message.get('message'))
            self.root.quit() # Exit if unable to join
            
        elif msg_type == 'game_update':
            self.update_game_state(message.get('data'))
            
        elif msg_type == 'game_started':
            self.update_status("Game started!")
            
        elif msg_type == 'action_failed':
            messagebox.showwarning("Action Failed", message.get('message'))
            
        elif msg_type == 'game_result':
            winners = message.get('winners', [])
            winning_hand_type = message.get('winning_hand_type', 'Unknown Hand') # Get the winning hand type
            
            # Ensure game_data['players'] is populated before accessing
            if 'players' in self.game_data:
                winner_names = [self.game_data['players'][pid]['name'] for pid in winners if pid in self.game_data['players']]
                
                # Construct the message with the winning hand type
                display_message = message.get('message', f"The winner(s) are: {', '.joiwinnern(winner_names)}!")
                if self.player_id in winners:
                    display_message += f"\n\nYou won with a {winning_hand_type}!"
                else:
                    # If not the winner, show what the winner had
                    if len(winners) == 1:
                        display_message += f"\n\n{winner_names[0]} won with a {winning_hand_type}!"

                messagebox.showinfo("Game Result", display_message)
                self.update_status(f"Winners: {', '.join(winner_names)} (Winning Hand: {winning_hand_type})")
            else:
                messagebox.showinfo("Game Result", message.get('message'))
                self.update_status("Game ended.")

        elif msg_type == 'error':
            messagebox.showerror("Server Error", message.get('message'))
    
    def update_game_state(self, game_data):
        """Update the UI with new game state"""
        if not game_data:
            return
        
        self.game_data = game_data
        self.current_player_id = game_data.get('current_player_id')
        self.dealer_player_id = game_data.get('dealer_player_id')
        
        # Update pot and game state label
        self.pot_label.config(text=f"Pot: ${game_data.get('pot', 0)}")
        
        game_state = game_data.get('game_state', 'waiting')
        state_text = {
            'waiting': 'Waiting for players...',
            'dealing': 'Dealing cards...',
            'pre_flop': 'Pre-Flop',
            'flop': 'Flop',
            'turn': 'Turn',
            'river': 'River',
            'showdown': 'Showdown',
            'game_over': 'Game Over'
        }.get(game_state, game_state.title())
        
        if self.current_player_id == self.player_id:
            state_text += " - Your Turn!"
        elif self.current_player_id and self.current_player_id in self.game_data.get('players', {}):
            current_player_name = self.game_data['players'][self.current_player_id]['name']
            state_text += f" - {current_player_name}'s Turn"
            
        self.game_state_label.config(text=state_text)
        
        # Update community cards
        self.update_community_cards(game_data.get('community_cards', []))
        
        # Update players
        self.update_players(game_data.get('players', {}))
        
        # Update action buttons
        self.update_action_buttons(self.current_player_id == self.player_id and game_state in ['pre_flop', 'flop', 'turn', 'river'])
        
        # Control Start New Hand button visibility
        if game_state == 'waiting' or game_state == 'game_over':
            self.start_btn.config(state=tk.NORMAL)
        else:
            self.start_btn.config(state=tk.DISABLED)
            
    def update_community_cards(self, cards):
        """Update community cards display"""
        for widget in self.community_cards_frame.winfo_children():
            widget.destroy()
        
        for card_data in cards:
            card_image = self.card_images.get(card_data['image'])
            if card_image:
                label = tk.Label(self.community_cards_frame, image=card_image, bg='#0D4F3C')
                label.pack(side=tk.LEFT, padx=2)
            
        # Add placeholders for remaining community cards if fewer than 5
        for i in range(len(cards), 5):
            if self.card_back_image:
                label = tk.Label(self.community_cards_frame, image=self.card_back_image, bg='#0D4F3C')
                label.pack(side=tk.LEFT, padx=2)
    
    def update_players(self, players_data):
        """Update players display"""
        # Clear existing player widgets (except my own)
        for widget in self.other_players_frame.winfo_children():
            widget.destroy()
        self.player_widgets.clear() # Clear stored widgets as well

        # Update my player info and cards
        if self.player_id in players_data:
            my_data = players_data[self.player_id]
            self.my_chips_label.config(text=f"Chips: ${my_data.get('chips', 0)}")
            self.my_bet_label.config(text=f"Current Bet: ${my_data.get('current_bet', 0)}")
            self.update_my_cards(my_data.get('cards', []))
        
        # Display other players
        player_keys_ordered = list(players_data.keys())
        if self.player_id in player_keys_ordered:
            my_index = player_keys_ordered.index(self.player_id)
            # Sort players so 'my' player is at the bottom, and others are arranged around the top
            # Simple sorting for display: put current player's ID first, then others
            sorted_pids = [self.player_id] + [pid for pid in player_keys_ordered if pid != self.player_id]
            
            # For displaying other players, skip my own ID
            for pid in sorted_pids:
                if pid == self.player_id:
                    continue 

                player_data = players_data[pid]
                player_frame = tk.Frame(self.other_players_frame, bg='#2E7D32', relief=tk.RAISED, bd=1)
                player_frame.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.Y, expand=True) # Use expand for even distribution
                self.player_widgets[pid] = player_frame # Store for later updates

                # Player name
                name_text = player_data.get('name', 'Unknown')
                if pid == self.dealer_player_id:
                    name_text += " (D)" # Mark dealer
                
                name_label = tk.Label(player_frame, text=name_text, 
                                     bg='#2E7D32', fg='white', font=('Arial', 10, 'bold'))
                name_label.pack(padx=5, pady=2)
                
                # Player chips
                chips_label = tk.Label(player_frame, text=f"${player_data.get('chips', 0)}", 
                                     bg='#2E7D32', fg='white', font=('Arial', 9))
                chips_label.pack(padx=5)
                
                # Player bet
                bet = player_data.get('current_bet', 0)
                bet_label = tk.Label(player_frame, text=f"Bet: ${bet}", 
                                     bg='#2E7D32', fg='yellow', font=('Arial', 9))
                bet_label.pack(padx=5)

                # Player status
                status_text = ""
                status_color = 'white'
                if player_data.get('is_folded'):
                    status_text = "FOLDED"
                    status_color = 'red'
                elif player_data.get('is_all_in'):
                    status_text = "ALL IN"
                    status_color = 'orange'
                elif pid == self.current_player_id:
                    status_text = "TO ACT"
                    status_color = 'cyan'
                
                status_label = tk.Label(player_frame, text=status_text, 
                                        bg='#2E7D32', fg=status_color, font=('Arial', 8, 'bold'))
                status_label.pack(padx=5)
                
                # Player cards
                cards_frame = tk.Frame(player_frame, bg='#2E7D32')
                cards_frame.pack(padx=5, pady=2)

                for card_data in player_data.get('cards', []):
                    card_image = self.card_images.get(card_data['image'])
                    if not card_image: # Fallback to card back if specific image not found
                        card_image = self.card_back_image
                    
                    card_label = tk.Label(cards_frame, image=card_image, bg='#2E7D32')
                    card_label.pack(side=tk.LEFT, padx=1)
    
    def update_my_cards(self, cards):
        """Update my cards display"""
        for widget in self.my_cards_display_frame.winfo_children():
            widget.destroy()
        
        for card_data in cards:
            card_image = self.card_images.get(card_data['image'])
            if card_image:
                label = tk.Label(self.my_cards_display_frame, image=card_image, bg='#1A5D4A')
                label.pack(side=tk.LEFT, padx=2)
    
    def update_action_buttons(self, is_my_turn):
        """Update action buttons based on game state and current player"""
        # Disable all buttons initially
        self.fold_btn.config(state=tk.DISABLED)
        self.check_btn.config(state=tk.DISABLED)
        self.call_btn.config(state=tk.DISABLED)
        self.raise_btn.config(state=tk.DISABLED)
        self.all_in_btn.config(state=tk.DISABLED)

        if not is_my_turn or not self.game_data:
            return
            
        players = self.game_data.get('players', {})
        my_data = players.get(self.player_id)
        
        if not my_data or my_data.get('is_folded') or my_data.get('is_all_in') or my_data.get('chips', 0) <= 0:
            return # Player cannot act
        
        current_bet = self.game_data.get('current_bet', 0)
        my_bet = my_data.get('current_bet', 0)
        my_chips = my_data.get('chips', 0)
        
        self.fold_btn.config(state=tk.NORMAL) # Fold is always an option if you can act
        
        # Determine Check/Call
        if current_bet == my_bet:
            self.check_btn.config(state=tk.NORMAL)
            self.call_btn.config(text="Call") # Reset text if it was showing amount
        else:
            call_amount = current_bet - my_bet
            if my_chips >= call_amount:
                self.call_btn.config(state=tk.NORMAL, text=f"Call ${call_amount}")
            else: # Not enough chips to call, can only go all-in or fold
                # If they can't call, their "call" is effectively an all-in
                self.call_btn.config(state=tk.DISABLED) 
                
        # Raise button logic
        # Player must have enough chips to at least call the current bet AND then raise.
        # Min raise is typically the size of the big blind, or the size of the previous raise.
        # For simplicity, let's use big blind as min increment for raise.
        
        min_raise_increment = self.game_data.get('big_blind', 20)
        
        # The amount to match the current bet
        amount_to_match = current_bet - my_bet

        # Minimum total bet for a raise (current_bet + min_raise_increment)
        min_total_raise_amount = current_bet + min_raise_increment

        # Player must have enough chips to at least make the minimum raise
        if my_chips >= min_total_raise_amount - my_bet:
            self.raise_btn.config(state=tk.NORMAL)
        
        # All-in button is always available if player has chips
        if my_chips > 0:
            self.all_in_btn.config(state=tk.NORMAL)

    def send_action(self, action, amount=0):
        """Send action to server"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "You are not connected to the server.")
            return
            
        message = {
            'type': 'action',
            'player_id': self.player_id,
            'action': action,
            'amount': amount
        }
        
        try:
            self.socket.send(json.dumps(message).encode('utf-8') + b'\n') # Add newline for server parsing
        except Exception as e:
            print(f"Error sending action: {e}")
            self.connected = False # Assume disconnection
            self.root.after(0, lambda: messagebox.showerror("Connection Error", "Failed to send action. Disconnected from server."))
            self.root.after(0, self.root.quit)
    
    def fold_action(self):
        """Fold action"""
        self.send_action('fold')
    
    def check_action(self):
        """Check action"""
        self.send_action('check')
    
    def call_action(self):
        """Call action"""
        if not self.game_data or self.player_id not in self.game_data.get('players', {}):
            return
        
        my_data = self.game_data['players'][self.player_id]
        current_bet = self.game_data.get('current_bet', 0)
        my_bet = my_data.get('current_bet', 0)
        call_amount_needed = current_bet - my_bet
        
        # If player doesn't have enough to call the full amount, their call is an all-in
        if my_data.get('chips', 0) <= call_amount_needed:
            self.send_action('all_in') # Send all-in if cannot afford full call
        else:
            self.send_action('call')
    
    def raise_action(self):
        """Raise action"""
        if not self.game_data or self.player_id not in self.game_data.get('players', {}):
            return
            
        my_data = self.game_data['players'][self.player_id]
        current_bet = self.game_data.get('current_bet', 0)
        my_chips = my_data.get('chips', 0)
        my_current_bet = my_data.get('current_bet', 0)
        
        min_raise_increment = self.game_data.get('big_blind', 20)
        min_total_raise_amount = current_bet + min_raise_increment

        # Player can only raise up to their total chips (current chips + chips already bet this round)
        max_total_bet_possible = my_chips + my_current_bet

        raise_dialog = tk.Toplevel(self.root)
        raise_dialog.title("Raise Amount")
        raise_dialog.geometry("300x200")
        raise_dialog.grab_set()
        raise_dialog.configure(bg='#0D4F3C')
        
        tk.Label(raise_dialog, text=f"Current Bet: ${current_bet}", bg='#0D4F3C', fg='white', font=('Arial', 10)).pack(pady=(5,0))
        tk.Label(raise_dialog, text=f"Your Current Bet: ${my_current_bet}", bg='#0D4F3C', fg='white', font=('Arial', 10)).pack(pady=(0,5))
        tk.Label(raise_dialog, text=f"Your Chips: ${my_chips}", bg='#0D4F3C', fg='white', font=('Arial', 10)).pack(pady=(0,5))
        tk.Label(raise_dialog, text=f"Raise to (min ${min_total_raise_amount}):", 
                 bg='#0D4F3C', fg='white', font=('Arial', 12)).pack(pady=(10,5))
        
        # Pre-fill with the minimum valid raise amount
        amount_var = tk.StringVar(value=str(min_total_raise_amount))
        amount_entry = tk.Entry(raise_dialog, textvariable=amount_var, font=('Arial', 12))
        amount_entry.pack(pady=5)
        
        def confirm_raise():
            try:
                amount = int(amount_var.get())
                # Player must bet at least the minimum raise amount, and not more than their total chips
                if amount >= min_total_raise_amount and amount <= max_total_bet_possible:
                    self.send_action('raise', amount)
                    raise_dialog.destroy()
                else:
                    messagebox.showerror("Invalid Raise", f"Amount must be between ${min_total_raise_amount} and ${max_total_bet_possible}", parent=raise_dialog)
            except ValueError:
                messagebox.showerror("Invalid Input", "Please enter a valid number for the raise amount.", parent=raise_dialog)
        
        tk.Button(raise_dialog, text="Raise", command=confirm_raise,
                  bg='#4CAF50', fg='white', font=('Arial', 10)).pack(pady=10)
    
    def all_in_action(self):
        """All-in action"""
        self.send_action('all_in')
    
    def start_game(self):
        """Send request to start a new game to the server."""
        if not self.connected:
            messagebox.showwarning("Not Connected", "You are not connected to the server.")
            return
        
        message = {
            'type': 'start_game',
            'player_id': self.player_id
        }
        
        try:
            self.socket.send(json.dumps(message).encode('utf-8') + b'\n') # Add newline for server parsing
        except Exception as e:
            print(f"Error starting game: {e}")
            self.connected = False # Assume disconnection
            self.root.after(0, lambda: messagebox.showerror("Connection Error", "Failed to send start game request. Disconnected from server."))
            self.root.after(0, self.root.quit)
    
    def update_status(self, message):
        """Update status message (e.g., in console or a dedicated status bar)"""
        print(f"Client Status: {message}")
    
    def run(self):
        """Runs the Tkinter event loop for the client."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            pass # Allow graceful exit on Ctrl+C
        finally:
            if self.connected and self.socket:
                self.socket.close()

if __name__ == '__main__':
    client = PokerClient()
    client.run()
