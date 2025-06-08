import socket
import threading
import json
import random
from enum import Enum
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple
import time

class GameState(Enum):
    WAITING = "waiting"
    DEALING = "dealing"
    PRE_FLOP = "pre_flop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    GAME_OVER = "game_over"

class ActionType(Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    RAISE = "raise"
    ALL_IN = "all_in"

@dataclass
class Card:
    suit: str  # hearts, diamonds, clubs, spades
    rank: str  # 2-10, jack, queen, king, ace
    
    def __post_init__(self):
        # Map rank names to match your image files
        if self.rank == "J":
            self.rank = "jack"
        elif self.rank == "Q":
            self.rank = "queen"
        elif self.rank == "K":
            self.rank = "king"
        elif self.rank == "A":
            self.rank = "ace"
        
        # Map suit names to match your image files
        suit_mapping = {
            "hearts": "heart",
            "diamonds": "diamond", 
            "clubs": "club",
            "spades": "spade"
        }
        if self.suit in suit_mapping:
            self.suit = suit_mapping[self.suit]
    
    def get_image_name(self):
        return f"{self.suit}_{self.rank}.jpg"
    
    def get_value(self):
        if self.rank in ['jack', 'queen', 'king']:
            return {'jack': 11, 'queen': 12, 'king': 13}[self.rank]
        elif self.rank == 'ace':
            return 14
        else:
            return int(self.rank)

@dataclass
class Player:
    id: str
    name: str
    chips: int
    cards: List[Card]
    current_bet: int # Amount player has put into the pot in the current betting round
    total_bet: int # Total amount player has put into the pot for the entire hand
    is_folded: bool
    is_all_in: bool
    connection: socket.socket
    has_acted_this_round: bool = False # Track if player has acted in current betting round
    
    def can_act(self):
        """Determines if a player is eligible to make an action."""
        return not self.is_folded and not self.is_all_in and self.chips > 0

class PokerGame:
    def __init__(self):
        self.players: Dict[str, Player] = {}
        self.community_cards: List[Card] = []
        self.deck: List[Card] = []
        self.pot = 0
        self.current_bet = 0 # Highest bet placed by any player in the current betting round
        self.dealer_position = -1 # Index in the list of active players for the dealer button
        self.current_player_index = -1 # Index in the list of active players for current turn
        self.game_state = GameState.WAITING
        self.small_blind = 10
        self.big_blind = 20
        self.action_history = []
        self.last_raiser = None # Tracks the ID of the last player who made a raise in the current round
        
    def create_deck(self):
        """Creates and shuffles a standard 52-card deck."""
        suits = ['hearts', 'diamonds', 'clubs', 'spades']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'jack', 'queen', 'king', 'ace']
        self.deck = [Card(suit, rank) for suit in suits for rank in ranks]
        random.shuffle(self.deck)
    
    def add_player(self, player_id: str, name: str, connection: socket.socket):
        """Adds a new player to the game if there's space."""
        if len(self.players) < 6:  # Max 6 players
            self.players[player_id] = Player(
                id=player_id,
                name=name,
                chips=1000,  # Starting chips
                cards=[],
                current_bet=0,
                total_bet=0,
                is_folded=False,
                is_all_in=False,
                connection=connection
            )
            return True
        return False
    
    def remove_player(self, player_id: str):
        """Removes a player from the game."""
        if player_id in self.players:
            del self.players[player_id]
            # If less than 2 players remain and game is not waiting, end the game
            if len([p for p in self.players.values() if p.chips > 0]) < 2 and self.game_state != GameState.WAITING:
                self.game_state = GameState.GAME_OVER
    
    def start_new_hand(self):
        """Starts a new hand of poker."""
        active_players_in_game = [p for p in self.players.values() if p.chips > 0]
        if len(active_players_in_game) < 2:
            print("Not enough active players to start a new hand.")
            self.game_state = GameState.WAITING
            return False
            
        self.create_deck()
        self.community_cards = []
        self.pot = 0
        self.current_bet = 0
        self.action_history = []
        self.last_raiser = None

        # Rotate dealer position to the next active player
        players_ids = list(self.players.keys())
        # Find the index of the next active player after the current dealer
        next_dealer_found = False
        for i in range(len(players_ids)):
            potential_dealer_index = (self.dealer_position + 1 + i) % len(players_ids)
            potential_dealer_id = players_ids[potential_dealer_index]
            if self.players[potential_dealer_id].chips > 0: # Only active players can be dealer
                self.dealer_position = potential_dealer_index
                next_dealer_found = True
                break
        if not next_dealer_found: # Should not happen if len(active_players_in_game) >= 2
            print("Error: Could not find a new dealer.")
            return False

        # Reset player states for the new hand
        for player_id in players_ids:
            player = self.players[player_id]
            player.cards = []
            player.current_bet = 0
            player.total_bet = 0 # Reset total bet for the new hand
            player.is_folded = False
            player.is_all_in = False
            player.has_acted_this_round = False # Reset for the new hand

        # Deal hole cards
        for _ in range(2):
            for player_id in players_ids:
                player = self.players[player_id]
                if self.deck:
                    player.cards.append(self.deck.pop())
        
        self.post_blinds()
        self.game_state = GameState.PRE_FLOP
        
        # Determine who starts the pre-flop betting round (UTG, or player after Big Blind)
        # It's the first active player after the Big Blind
        self.current_player_index = self._get_player_index_after_dealer(self.dealer_position, 3)
        if self.current_player_index == -1: # Fallback if no player found after BB (e.g., only 2 players)
             self.current_player_index = self._get_player_index_after_dealer(self.dealer_position, 0) # Start from player after dealer
             
        print(f"New hand started. Dealer: {self.players[players_ids[self.dealer_position]].name}. First to act: {self.players[players_ids[self.current_player_index]].name}")
        return True
    
    def post_blinds(self):
        """Handles posting of small and big blinds."""
        players_list = list(self.players.values())
        players_ids = list(self.players.keys())

        # Small blind position: 1 after dealer
        sb_pos_index = (self.dealer_position + 1) % len(players_ids)
        sb_player = players_list[sb_pos_index]
        
        # Big blind position: 2 after dealer
        bb_pos_index = (self.dealer_position + 2) % len(players_ids)
        bb_player = players_list[bb_pos_index]

        # Handle cases with fewer than 3 players (e.g., heads-up)
        if len(players_list) == 2:
            # In heads-up, dealer is small blind, other player is big blind
            sb_player = players_list[self.dealer_position]
            bb_player = players_list[(self.dealer_position + 1) % len(players_list)]

        # Small blind
        sb_amount = min(self.small_blind, sb_player.chips)
        sb_player.chips -= sb_amount
        sb_player.current_bet += sb_amount
        sb_player.total_bet += sb_amount
        self.pot += sb_amount
        sb_player.has_acted_this_round = True # Blinds count as actions
        print(f"{sb_player.name} posted Small Blind of ${sb_amount}")
        
        # Big blind
        bb_amount = min(self.big_blind, bb_player.chips)
        bb_player.chips -= bb_amount
        bb_player.current_bet += bb_amount
        bb_player.total_bet += bb_amount
        self.pot += bb_amount
        bb_player.has_acted_this_round = True # Blinds count as actions
        print(f"{bb_player.name} posted Big Blind of ${bb_amount}")
        
        self.current_bet = bb_player.current_bet
        self.last_raiser = bb_player.id # Big blind is the initial "raiser" for checking purposes

    def _get_player_index_after_dealer(self, start_pos: int, offset: int = 1) -> int:
        """
        Finds the index of the next active player to act, starting from an offset
        relative to a given starting position (e.g., dealer, small blind).
        """
        players_ids = list(self.players.keys())
        num_players = len(players_ids)
        if num_players == 0:
            return -1

        # Start checking from the player after the offset from the start_pos
        initial_index = (start_pos + offset) % num_players
        
        for i in range(num_players):
            current_index = (initial_index + i) % num_players
            player_id = players_ids[current_index]
            if self.players[player_id].can_act():
                return current_index
        return -1 # No active players found
    
    def process_action(self, player_id: str, action: str, amount: int = 0):
        """Processes a player's action (fold, check, call, raise, all-in)."""
        if player_id not in self.players:
            print(f"Error: Player {player_id} not found.")
            return False
            
        player = self.players[player_id]
        if not player.can_act():
            print(f"Error: Player {player.name} cannot act (folded, all-in, or no chips).")
            return False

        # Ensure it's the current player's turn
        players_list = list(self.players.keys())
        if self.current_player_index == -1 or players_list[self.current_player_index] != player_id:
            print(f"Error: Not {player.name}'s turn. Current player is {players_list[self.current_player_index] if self.current_player_index != -1 else 'None'}.")
            return False

        player.has_acted_this_round = True # Mark player as having acted this round
        
        success = False
        if action == ActionType.FOLD.value:
            player.is_folded = True
            success = True
            print(f"{player.name} folds.")
        elif action == ActionType.CHECK.value:
            if self.current_bet > player.current_bet:
                print(f"Error: {player.name} cannot check, current bet is ${self.current_bet} (player has ${player.current_bet}).")
                return False  # Can't check if there's a bet to call
            success = True
            print(f"{player.name} checks.")
        elif action == ActionType.CALL.value:
            call_amount_needed = self.current_bet - player.current_bet
            
            if call_amount_needed <= 0: # Can't call if no bet to match
                print(f"Error: {player.name} cannot call, no bet to match or already matched.")
                return False

            amount_to_add = min(call_amount_needed, player.chips)
            
            player.chips -= amount_to_add
            player.current_bet += amount_to_add
            player.total_bet += amount_to_add
            self.pot += amount_to_add
            
            if player.chips == 0:
                player.is_all_in = True
                print(f"{player.name} calls ${amount_to_add} and goes ALL IN.")
            else:
                print(f"{player.name} calls ${amount_to_add}.")
            success = True
        elif action == ActionType.RAISE.value:
            # 'amount' here is the total amount the player wants to bet (e.g., raise to $100)
            if amount <= self.current_bet: # Raise must be higher than current bet
                print(f"Error: Raise amount ${amount} is not higher than current bet ${self.current_bet}.")
                return False

            # Calculate the amount to add to their current bet to reach the 'amount'
            amount_to_add = amount - player.current_bet
            
            if amount_to_add > player.chips: # Player cannot afford the full raise
                amount_to_add = player.chips # Player goes all-in for remaining chips
                amount = player.current_bet + amount_to_add # Adjust total amount to reflect all-in
                player.is_all_in = True
            
            player.chips -= amount_to_add
            player.current_bet += amount_to_add
            player.total_bet += amount_to_add
            self.pot += amount_to_add
            self.current_bet = player.current_bet # New highest bet for the round
            self.last_raiser = player.id # Update last raiser
            
            if player.chips == 0:
                player.is_all_in = True
                print(f"{player.name} raises to ${amount} and goes ALL IN.")
            else:
                print(f"{player.name} raises to ${amount}.")
            success = True

            # Reset has_acted_this_round for players who need to act again (those who haven't matched new current_bet)
            for pid, p in self.players.items():
                if p.can_act() and p.id != player.id and p.current_bet < self.current_bet:
                    p.has_acted_this_round = False
        elif action == ActionType.ALL_IN.value:
            all_in_amount = player.chips
            
            # The player's total bet for the round is their current bet + all_in_amount
            player.current_bet += all_in_amount
            player.total_bet += all_in_amount
            player.chips = 0 # Chips become 0 after going all-in
            player.is_all_in = True
            self.pot += all_in_amount
            
            if player.current_bet > self.current_bet:
                self.current_bet = player.current_bet
                self.last_raiser = player.id
                # Reset has_acted_this_round for players who need to act again
                for pid, p in self.players.items():
                    if p.can_act() and p.id != player.id and p.current_bet < self.current_bet:
                        p.has_acted_this_round = False

            print(f"{player.name} goes ALL IN with ${all_in_amount}.")
            success = True
        
        if success:
            self.action_history.append((player_id, action, amount))
        return success
    
    def advance_to_next_street(self):
        """Advances the game to the next betting street (Flop, Turn, River, Showdown)."""
        # Collect all current_bets into the main pot and reset for the new street
        for player in self.players.values():
            self.pot += player.current_bet # Add current round's bets to main pot
            player.current_bet = 0
            player.has_acted_this_round = False # Reset for the new street
        self.current_bet = 0 # Reset current bet for the new street
        self.last_raiser = None # Reset last raiser for the new street

        # Determine the first player to act in the new street (player after dealer or next active player)
        # For post-flop, the first active player after the dealer acts first.
        self.current_player_index = self._get_player_index_after_dealer(self.dealer_position)
        
        # If no active player found after dealer (e.g., all others folded/all-in),
        # try to find the first active player in the player list.
        if self.current_player_index == -1:
            players_ids = list(self.players.keys())
            for i in range(len(players_ids)):
                if self.players[players_ids[i]].can_act():
                    self.current_player_index = i
                    break
            # If still no active player, it means all remaining players are all-in or folded.
            # In this case, the betting round implicitly completes, and we move to showdown if it's river.
            if self.current_player_index == -1 and any(p.chips > 0 and not p.is_folded for p in self.players.values()):
                print("Warning: No active player found to start new street, but some players still have chips and are not folded.")
                # This might happen if all remaining players are all-in.
                # The game should proceed to dealing cards and then to showdown if it's the river.
                pass # Let the game state advance and game_loop handle the next step

        if self.game_state == GameState.PRE_FLOP:
            # Deal flop (3 cards)
            self.deck.pop()  # Burn card
            for _ in range(3):
                if self.deck:
                    self.community_cards.append(self.deck.pop())
            self.game_state = GameState.FLOP
            print("--- FLOP dealt ---")
        elif self.game_state == GameState.FLOP:
            # Deal turn (1 card)
            self.deck.pop()  # Burn card
            if self.deck:
                self.community_cards.append(self.deck.pop())
            self.game_state = GameState.TURN
            print("--- TURN dealt ---")
        elif self.game_state == GameState.TURN:
            # Deal river (1 card)
            self.deck.pop()  # Burn card
            if self.deck:
                self.community_cards.append(self.deck.pop())
            self.game_state = GameState.RIVER
            print("--- RIVER dealt ---")
        elif self.game_state == GameState.RIVER:
            self.game_state = GameState.SHOWDOWN
            print("--- SHOWDOWN ---")

    def evaluate_hand(self, player_cards: List[Card], community_cards: List[Card]) -> Tuple[int, List[int]]:
        """Evaluate poker hand strength. Returns (hand_rank, tiebreakers)"""
        all_cards = player_cards + community_cards
        all_cards.sort(key=lambda x: x.get_value(), reverse=True)
        
        # Count suits and ranks
        suits = {}
        ranks = {}
        for card in all_cards:
            suits[card.suit] = suits.get(card.suit, 0) + 1
            ranks[card.get_value()] = ranks.get(card.get_value(), 0) + 1
        
        # Check for flush
        is_flush = any(count >= 5 for count in suits.values())
        
        # Check for straight
        unique_ranks = sorted(list(set(card.get_value() for card in all_cards)), reverse=True)
        is_straight = False
        straight_high = 0
        
        # Check for regular straight
        for i in range(len(unique_ranks) - 4):
            if unique_ranks[i] - unique_ranks[i+4] == 4:
                is_straight = True
                straight_high = unique_ranks[i]
                break
        
        # Check for A-2-3-4-5 straight (wheel)
        if not is_straight and 14 in unique_ranks and 2 in unique_ranks and 3 in unique_ranks and 4 in unique_ranks and 5 in unique_ranks:
            is_straight = True
            straight_high = 5
        
        # Count pairs, trips, quads
        # Convert to list of (rank, count) tuples for easier processing of counts
        rank_counts = sorted(ranks.items(), key=lambda x: (x[1], x[0]), reverse=True)
        
        # Determine hand ranking (higher number = better hand)
        if is_straight and is_flush:
            # Check for royal flush specifically (10-J-Q-K-A of same suit)
            if all(r in unique_ranks for r in [10, 11, 12, 13, 14]) and is_flush and straight_high == 14:
                return (9, [14]) # Royal Flush
            else: # Straight Flush
                # Find the highest card of the straight flush
                flush_suit = None
                for suit, count in suits.items():
                    if count >= 5:
                        flush_suit = suit
                        break
                
                straight_flush_cards = sorted([card.get_value() for card in all_cards if card.suit == flush_suit], reverse=True)
                for i in range(len(straight_flush_cards) - 4):
                    if straight_flush_cards[i] - straight_flush_cards[i+4] == 4:
                        return (8, [straight_flush_cards[i]])
                # Handle A-5 straight flush
                if 14 in straight_flush_cards and 5 in straight_flush_cards and 4 in straight_flush_cards and 3 in straight_flush_cards and 2 in straight_flush_cards:
                    return (8, [5])
                return (0, [0]) # Should not happen if logic is correct
                
        elif rank_counts[0][1] == 4:  # Four of a kind
            return (7, [rank_counts[0][0], rank_counts[1][0]]) # Quad rank, then kicker
        elif rank_counts[0][1] == 3 and rank_counts[1][1] >= 2:  # Full house (at least a pair for the second part)
            # Ensure we pick the highest pair if there are multiple
            pair_rank = 0
            for i in range(1, len(rank_counts)):
                if rank_counts[i][1] >= 2:
                    pair_rank = rank_counts[i][0]
                    break
            return (6, [rank_counts[0][0], pair_rank])
        elif is_flush:  # Flush
            flush_suit = None
            for suit, count in suits.items():
                if count >= 5:
                    flush_suit = suit
                    break
            flush_cards = sorted([card.get_value() for card in all_cards if card.suit == flush_suit], reverse=True)[:5]
            return (5, flush_cards)
        elif is_straight:  # Straight
            return (4, [straight_high])
        elif rank_counts[0][1] == 3:  # Three of a kind
            kickers = sorted([rank for rank, count in rank_counts if count == 1], reverse=True)[:2]
            return (3, [rank_counts[0][0]] + kickers)
        elif rank_counts[0][1] == 2 and rank_counts[1][1] == 2:  # Two pair
            # Ensure pairs are in descending order
            pairs = sorted([rank_counts[0][0], rank_counts[1][0]], reverse=True)
            kicker = sorted([rank for rank, count in rank_counts if count == 1], reverse=True)
            return (2, pairs + (kicker[:1] if kicker else []))
        elif rank_counts[0][1] == 2:  # One pair
            kickers = sorted([rank for rank, count in rank_counts if count == 1], reverse=True)[:3]
            return (1, [rank_counts[0][0]] + kickers)
        else:  # High card
            return (0, sorted([card.get_value() for card in all_cards], reverse=True)[:5])

    def determine_winners(self) -> List[str]:
        """Determine the winner(s) of the hand considering side pots."""
        # Active players are those who haven't folded
        potential_winners = {pid: p for pid, p in self.players.items() if not p.is_folded}
        
        if len(potential_winners) == 0:
            return [] # No winners, perhaps all folded before blinds were paid
        
        if len(potential_winners) == 1:
            # If only one player left, they win the entire pot
            winner_id = list(potential_winners.keys())[0]
            self.players[winner_id].chips += self.pot
            print(f"Player {self.players[winner_id].name} wins the entire pot of ${self.pot} (all others folded).")
            self.pot = 0
            return [winner_id]

        player_hands = {}        
        for pid, player in potential_winners.items():
            hand_strength = self.evaluate_hand(player.cards, self.community_cards)
            player_hands[pid] = hand_strength
        
        # Calculate side pots
        # Collect all unique total_bet amounts in ascending order from players who are still in the hand
        all_bets = sorted(list(set(p.total_bet for p in potential_winners.values())), reverse=False)
        
        # Initialize side pots
        side_pots = []
        for i, bet_level in enumerate(all_bets):
            eligible_players_for_this_level = [p for p in potential_winners.values() if p.total_bet >= bet_level]
            if not eligible_players_for_this_level:
                continue

            pot_amount_for_level = 0
            # Calculate the contribution to this specific bet level
            contribution_per_player = bet_level - (all_bets[i-1] if i > 0 else 0)
            
            for player in eligible_players_for_this_level:
                # Add player's contribution to this side pot, capped at their total bet for this level
                player_contribution_to_level = min(contribution_per_player, player.total_bet - (all_bets[i-1] if i > 0 else 0))
                pot_amount_for_level += player_contribution_to_level
            
            side_pots.append({'amount': pot_amount_for_level, 'eligible_players': [p.id for p in eligible_players_for_this_level]})

        final_winners = []
        
        # Distribute pots from smallest to largest bet levels
        for pot_info in side_pots:
            current_pot_amount = pot_info['amount']
            eligible_pids = pot_info['eligible_players']
            
            # Filter player hands for eligible players for THIS side pot
            eligible_player_hands = {pid: strength for pid, strength in player_hands.items() if pid in eligible_pids}

            if not eligible_player_hands:
                continue

            best_strength = max(eligible_player_hands.values())
            current_pot_winners = [pid for pid, strength in eligible_player_hands.items() if strength == best_strength]
            
            # Distribute current_pot_amount among current_pot_winners
            if current_pot_winners:
                share = current_pot_amount // len(current_pot_winners)
                remainder = current_pot_amount % len(current_pot_winners) # For odd chips
                
                for idx, winner_id in enumerate(current_pot_winners):
                    winnings = share
                    if idx < remainder: # Distribute remainder chips one by one
                        winnings += 1
                    self.players[winner_id].chips += winnings
                    print(f"Player {self.players[winner_id].name} wins ${winnings} from a side pot.")
                    if winner_id not in final_winners:
                        final_winners.append(winner_id)
            
        self.pot = 0 # Pot is fully distributed

        return final_winners
    
    def get_game_state(self, player_id: Optional[str] = None) -> dict:
        """
        Returns the current game state, with player-specific card visibility.
        If player_id is provided, their cards are shown. During SHOWDOWN, all cards are shown.
        """
        players_data = {}
        players_list = list(self.players.keys())
        
        for pid, player in self.players.items():
            player_cards_data = []
            # Reveal cards only to the specific player or during showdown
            if player_id == pid or self.game_state == GameState.SHOWDOWN:
                player_cards_data = [{'suit': card.suit, 'rank': card.rank, 'image': card.get_image_name()} for card in player.cards]
            else: # Other players' cards are hidden
                for _ in player.cards: # Still send 2 card objects, but with back image
                    player_cards_data.append({'suit': 'back', 'rank': 'back', 'image': 'card_back.jpg'})

            players_data[pid] = {
                'name': player.name,
                'chips': player.chips,
                'current_bet': player.current_bet,
                'total_bet': player.total_bet,
                'is_folded': player.is_folded,
                'is_all_in': player.is_all_in,
                'cards': player_cards_data,
                'is_current_player': (players_list[self.current_player_index] == pid) if self.current_player_index != -1 else False
            }
        
        return {
            'game_state': self.game_state.value,
            'players': players_data,
            'community_cards': [{'suit': card.suit, 'rank': card.rank, 'image': card.get_image_name()} for card in self.community_cards],
            'pot': self.pot,
            'current_bet': self.current_bet,
            'current_player_id': players_list[self.current_player_index] if self.current_player_index != -1 else None,
            'dealer_player_id': players_list[self.dealer_position] if self.dealer_position != -1 else None,
            'small_blind': self.small_blind, # Send blind amounts to client for raise calculation
            'big_blind': self.big_blind
        }

class PokerServer:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.game = PokerGame()
        self.clients: Dict[str, socket.socket] = {} # Map player_id to client socket
        
    def start(self):
        """Starts the poker server, listening for connections and running the game loop."""
        self.socket.bind((self.host, self.port))
        self.socket.listen(6)
        print(f"Poker server started on {self.host}:{self.port}")
        
        # Start game logic loop in a separate thread
        game_loop_thread = threading.Thread(target=self.game_loop)
        game_loop_thread.daemon = True # Allow the main program to exit even if this thread is running
        game_loop_thread.start()

        while True:
            try:
                client_socket, address = self.socket.accept()
                print(f"New connection from {address}")
                # Client handling thread is responsible for receiving messages from this client
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()
            except Exception as e:
                print(f"Error accepting connection: {e}")
    
    def handle_client(self, client_socket, address):
        """Handles incoming messages from a single client connection."""
        player_id = None
        try:
            while True:
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    break # Client disconnected
                
                # Split data by newline to handle multiple JSON messages in one recv call
                messages = data.split('\n')
                for msg_str in messages:
                    if msg_str.strip(): # Process non-empty strings
                        try:
                            message = json.loads(msg_str)
                            # For 'join' message, we need to associate player_id with socket immediately
                            if message.get('type') == 'join':
                                player_id = message.get('player_id')
                                player_name = message.get('name')
                                if self.game.add_player(player_id, player_name, client_socket):
                                    self.clients[player_id] = client_socket # Store the socket
                                    response = {'type': 'join_success', 'message': 'Joined game successfully'}
                                    self.send_to_client(player_id, response) # Send response directly
                                    print(f"Player {player_name} ({player_id}) joined.")
                                    self.broadcast_game_state() # Broadcast initial state to all
                                else:
                                    response = {'type': 'join_failed', 'message': 'Game is full'}
                                    self.send_to_client(player_id, response)
                                    print(f"Player {player_name} ({player_id}) failed to join: Game full.")
                                continue # Skip further processing for join messages in this loop iteration

                            # Process other messages using the game instance
                            self.process_client_message(message, player_id)
                                
                        except json.JSONDecodeError:
                            print(f"Invalid JSON from {address}: {msg_str}")
                        except Exception as e:
                            print(f"Error processing message from {address}: {e}")
                            self.send_to_client(player_id, {'type': 'error', 'message': f"Server error: {e}"})
                            
        except Exception as e:
            print(f"Client handler error for {address}: {e}")
        finally:
            # Clean up on client disconnect
            if player_id:
                print(f"Player {player_id} disconnected.")
                self.game.remove_player(player_id)
                if player_id in self.clients:
                    del self.clients[player_id]
                self.broadcast_game_state() # Update all clients after disconnect
            client_socket.close()
    
    def process_client_message(self, message: dict, player_id: str):
        """Processes a message received from a client."""
        msg_type = message.get('type')
        
        if msg_type == 'start_game':
            # Only allow starting if in WAITING state and enough players
            if self.game.game_state == GameState.WAITING and len(self.game.players) >= 2:
                if self.game.start_new_hand():
                    print("Game started by a client.")
                    self.broadcast_game_state()
                else:
                    print("Failed to start game.")
                    self.send_to_client(player_id, {'type': 'error', 'message': 'Failed to start game'})
            else:
                self.send_to_client(player_id, {'type': 'error', 'message': 'Cannot start game (not enough players or game already in progress)'})
        
        elif msg_type == 'action':
            action_type = message.get('action')
            amount = message.get('amount', 0)
            
            # Ensure actions are only processed during active betting rounds
            if self.game.game_state in [GameState.PRE_FLOP, GameState.FLOP, GameState.TURN, GameState.RIVER]:
                players_list = list(self.game.players.keys())
                current_player_id = players_list[self.game.current_player_index] if self.game.current_player_index != -1 else None
                
                if player_id == current_player_id: # Check if it's the correct player's turn
                    if self.game.process_action(player_id, action_type, amount):
                        print(f"Player {self.game.players[player_id].name} took action: {action_type} {amount}")
                        
                        # After processing action, determine next step: round complete or next player's turn
                        if self.is_betting_round_complete():
                            print(f"Betting round for {self.game.game_state.value} is complete after {self.game.players[player_id].name}'s action.")
                            self.game.advance_to_next_street()
                            # If advancing to showdown, handle it immediately
                            if self.game.game_state == GameState.SHOWDOWN:
                                self.handle_showdown()
                        else:
                            self.advance_to_next_player() # Move to the next player's turn
                        
                        self.broadcast_game_state() # Broadcast after state change
                    else:
                        self.send_to_client(player_id, {'type': 'action_failed', 'message': 'Invalid action or amount. Please check your input and current game state.'})
                else:
                    self.send_to_client(player_id, {'type': 'action_failed', 'message': 'Not your turn. Please wait for your turn.'})
            else:
                self.send_to_client(player_id, {'type': 'action_failed', 'message': 'Actions not allowed in current game state.'})
        
        # Add other message types as needed
    
    def is_betting_round_complete(self):
        """
        Checks if the current betting round is complete.
        A round is complete if:
        1. Only one player remains active (others folded).
        2. All active players have matched the highest bet (current_bet) and have acted this round,
           or are all-in.
        """
        active_players_in_round = [p for p in self.game.players.values() if p.can_act()]
        
        if len(active_players_in_round) <= 1: # All but one folded, or no active players left
            return True
            
        # Check if all active players have either matched the highest bet or are all-in
        # and have acted since the last raise (or initial post-blinds for pre-flop)
        for player in active_players_in_round:
            # If a player is not all-in, they must have matched the current bet AND acted this round
            if not player.is_all_in:
                if player.current_bet < self.game.current_bet or not player.has_acted_this_round:
                    return False
            # If a player is all-in, they are considered to have completed their action for the round.
            # No further action is required from them.
        
        # Additional check: If the last raiser is the only one who has acted,
        # and everyone else has called or folded, the round is complete.
        # This prevents the round from looping back to the raiser unnecessarily.
        if self.game.last_raiser:
            raiser_player = self.game.players[self.game.last_raiser]
            # If the raiser has acted, and all other active players have matched their bet
            # and acted, the round is complete.
            all_others_matched_and_acted = True
            for player in active_players_in_round:
                if player.id == self.game.last_raiser:
                    continue # Skip the raiser for this check
                if not player.is_all_in and (player.current_bet < self.game.current_bet or not player.has_acted_this_round):
                    all_others_matched_and_acted = False
                    break
            if all_others_matched_and_acted:
                return True

        # If no one has raised (e.g., all checks/calls at current_bet 0), and everyone has acted, round is complete.
        if self.game.current_bet == 0: # This implies no raises, only checks
            if all(p.has_acted_this_round for p in active_players_in_round):
                return True

        return False
    
    def advance_to_next_player(self):
        """
        Advances the current_player_index to the next player who needs to act.
        This function is called after a player performs an action.
        """
        players_list = list(self.game.players.keys())
        num_players = len(players_list)
        if num_players == 0:
            self.game.current_player_index = -1
            return

        start_index = self.game.current_player_index # Remember who just acted
        
        # Loop through players starting from the one *after* the current one
        # to find the next player who needs to act.
        for _ in range(num_players): # Loop through all players once
            self.game.current_player_index = (self.game.current_player_index + 1) % num_players
            current_player_id = players_list[self.game.current_player_index]
            player = self.game.players[current_player_id]

            # A player needs to act if:
            # 1. They are eligible to act (`can_act()`).
            # 2. Their current bet is less than the highest bet (`self.game.current_bet`) OR
            #    they haven't acted this round (e.g., after a raise by someone else).
            if player.can_act() and (player.current_bet < self.game.current_bet or not player.has_acted_this_round):
                print(f"Next turn: {player.name} ({current_player_id})")
                return # Found the next player to act
        
        # If the loop finishes without returning, it implies no active player needs to act.
        # This means the betting round should be considered complete.
        print("No active player found who needs to act. Betting round should be complete.")
        # The game_loop will then detect this via is_betting_round_complete()
        # and advance the street.
        
    def game_loop(self):
        """The main server-side game logic loop."""
        while True:
            time.sleep(0.5) # Server tick rate

            # State: WAITING - Wait for clients to join and a 'start_game' message
            if self.game.game_state == GameState.WAITING:
                # Game start is usually triggered by a client, so keep waiting here
                pass
            
            # States: PRE_FLOP, FLOP, TURN, RIVER - Betting rounds
            elif self.game.game_state in [GameState.PRE_FLOP, GameState.FLOP, GameState.TURN, GameState.RIVER]:
                # The primary role here is to check for round completion.
                # Player turns are advanced by process_client_message after an action.
                if self.is_betting_round_complete():
                    print(f"Betting round for {self.game.game_state.value} is complete (via game_loop check).")
                    self.game.advance_to_next_street()
                    self.broadcast_game_state()
                    # If it's showdown after advancing, handle it
                    if self.game.game_state == GameState.SHOWDOWN:
                        self.handle_showdown()
                # Else, if round is not complete, we simply wait for a client action.
                # The turn advancement is handled by process_client_message.
            
            # State: SHOWDOWN - Determine winners and distribute pot
            elif self.game.game_state == GameState.SHOWDOWN:
                self.handle_showdown() # Ensure showdown logic runs
                time.sleep(5) # Allow clients to see showdown results
                # Reset has_acted_this_round for all players for the new hand
                for player in self.game.players.values():
                    player.has_acted_this_round = False
                self.game.start_new_hand()
                self.broadcast_game_state()
                
            # State: GAME_OVER - Not enough players or game ended
            elif self.game.game_state == GameState.GAME_OVER:
                print("Game is over. Waiting for players to join/restart.")
                # Logic to reset game or wait for more players
                pass

            # Check if only one player remains active in a hand (others folded)
            # This check should be done continuously during active game states
            active_players_in_hand = [p for p in self.game.players.values() if not p.is_folded and p.chips > 0]
            if self.game.game_state not in [GameState.WAITING, GameState.GAME_OVER, GameState.SHOWDOWN] and len(active_players_in_hand) == 1:
                winner_id = active_players_in_hand[0].id
                # Ensure pot is correctly assigned if others folded
                self.game.players[winner_id].chips += self.game.pot
                print(f"All players folded except {self.game.players[winner_id].name}. They win the pot of ${self.game.pot}.")
                self.game.pot = 0
                self.game.game_state = GameState.SHOWDOWN # Transition to showdown to trigger pot distribution/new hand
                self.broadcast_game_state()
                time.sleep(2) # Short delay to show winner
                # Reset has_acted_this_round for all players for the new hand
                for player in self.game.players.values():
                    player.has_acted_this_round = False
                self.game.start_new_hand()
                self.broadcast_game_state()


# In PokerServer.handle_showdown method:
    def handle_showdown(self):
        print("Handling showdown...")
        winners = self.game.determine_winners()
        
        winning_hand_type = "No Winner" # Default
        if winners:
            # Assuming determine_winners returns the best hand strength for the winner(s)
            # You'll need to re-evaluate the hand for the winner(s) to get the hand type string
            # Or, modify determine_winners to return the hand type directly.
            
            # For simplicity, let's assume the first winner's hand type is representative
            # A more robust solution would store winning hand type for each winner during determine_winners
            first_winner_id = winners[0]
            winner_player = self.game.players[first_winner_id]
            hand_strength_tuple = self.game.evaluate_hand(winner_player.cards, self.game.community_cards)
            
            # Map hand_rank (integer) to string
            hand_rank_map = {
                9: "Royal Flush",
                8: "Straight Flush",
                7: "Four of a Kind",
                6: "Full House",
                5: "Flush",
                4: "Straight",
                3: "Three of a Kind",
                2: "Two Pair",
                1: "One Pair",
                0: "High Card"
            }
            winning_hand_type = hand_rank_map.get(hand_strength_tuple[0], "Unknown Hand")

            winner_names = [self.game.players[pid].name for pid in winners]
            print(f"Winners of the hand: {', '.join(winner_names)} with a {winning_hand_type}")
            
            winning_message = {
                'type': 'game_result',
                'winners': winners,
                'message': f"The winner(s) are: {', '.join(winner_names)}!",
                'winning_hand_type': winning_hand_type # <-- This is the new field
            }
            self.broadcast(json.dumps(winning_message).encode('utf-8') + b'\n')
        else:
            print("No winners determined (e.g., all folded before showdown).")
        
        self.broadcast_game_state()
        
    def send_to_client(self, player_id: str, message: dict):
        """Sends a JSON message to a specific client."""
        if player_id in self.clients:
            try:
                self.clients[player_id].send(json.dumps(message).encode('utf-8') + b'\n') # Add newline for client parsing
            except Exception as e:
                print(f"Error sending message to client {player_id}: {e}")

    def broadcast_game_state(self):
        """Broadcasts the current game state to all connected clients, with player-specific card visibility."""
        # Send individual game state to each player (revealing their own cards)
        for player_id, client_socket in list(self.clients.items()):
            try:
                game_state_for_player = self.game.get_game_state(player_id)
                message = json.dumps({
                    'type': 'game_update',
                    'data': game_state_for_player
                })
                client_socket.send(message.encode('utf-8') + b'\n') # Add newline
            except Exception as e:
                print(f"Error broadcasting game state to {player_id}: {e}")
                # Remove disconnected client
                if player_id in self.clients:
                    del self.clients[player_id]
                self.game.remove_player(player_id) # Remove player from game if connection breaks
    
    def broadcast(self, message: bytes):
        """Broadcasts a raw byte message to all connected clients."""
        for player_id, client_socket in list(self.clients.items()):
            try:
                client_socket.send(message)
            except Exception as e:
                print(f"Error broadcasting to {player_id}: {e}")
                if player_id in self.clients:
                    del self.clients[player_id]
                self.game.remove_player(player_id)

if __name__ == '__main__':
    server = PokerServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServer shutting down...")
        server.socket.close()

