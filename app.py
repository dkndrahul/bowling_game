import os
from flask import Flask, render_template, request, jsonify
import sqlite3
import datetime

app = Flask(__name__)

# Define the path for the SQLite database file
DATABASE = 'bowling_game.db'

# Function to get a database connection
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # This allows accessing columns by name
    return conn

# --- Bowling Scoring Logic ---
# This function calculates the bowling score based on a list of all rolls made so far.
# It returns the total score, a detailed breakdown of each frame's score, and if the game is over.
def calculate_bowling_score(rolls):
    """
    Calculates the bowling score for a given list of rolls.

    Args:
        rolls (list): A list of integers representing the pins knocked down in each roll.

    Returns:
        dict: A dictionary containing:
            - 'total_score': The cumulative score of all completed frames.
            - 'frame_scores': A list of dictionaries, each representing a frame's details
                              (frame number, rolls made, mark, and score).
            - 'game_over': A boolean indicating if the 10-frame game is complete.
    """
    total_score = 0
    frame_scores_detail = []
    roll_pointer = 0 # Pointer to the current roll in the 'rolls' list

    # Iterate through 10 frames
    for frame_num in range(1, 11): # Frame 1 to 10
        frame_rolls_in_current_attempt = [] # Rolls made within the current frame's attempt
        frame_mark = ""
        current_frame_score = 0
        
        # If there are no more rolls to process for this frame, break the loop.
        # This handles incomplete games where not all 20-21 rolls have been made.
        if roll_pointer >= len(rolls):
            break

        # --- Scoring Logic for Frames 1-9 ---
        if frame_num < 10:
            # Check for Strike (first roll of the frame is 10 pins)
            if rolls[roll_pointer] == 10:
                frame_rolls_in_current_attempt.append(10)
                frame_mark = "Strike"
                
                # A strike's score includes 10 + the next two rolls.
                bonus_score = 0
                if roll_pointer + 1 < len(rolls):
                    bonus_score += rolls[roll_pointer + 1]
                if roll_pointer + 2 < len(rolls):
                    bonus_score += rolls[roll_pointer + 2]
                
                # If we don't have enough bonus rolls yet, this frame cannot be fully scored.
                if roll_pointer + 2 >= len(rolls):
                    current_frame_score = 0 # Score is pending
                    frame_mark = "Incomplete"
                else:
                    current_frame_score = 10 + bonus_score
                
                roll_pointer += 1 # A strike consumes only one roll in the sequence
            
            # Check for Spare (first two rolls sum to 10, and first roll is not 10)
            elif roll_pointer + 1 < len(rolls) and (rolls[roll_pointer] + rolls[roll_pointer + 1] == 10):
                frame_rolls_in_current_attempt.extend([rolls[roll_pointer], rolls[roll_pointer + 1]])
                frame_mark = "Spare"
                
                # A spare's score includes 10 + the next one roll.
                bonus_score = 0
                if roll_pointer + 2 < len(rolls):
                    bonus_score = rolls[roll_pointer + 2]
                
                # If we don't have enough bonus rolls yet, this frame cannot be fully scored.
                if roll_pointer + 2 >= len(rolls):
                    current_frame_score = 0 # Score is pending
                    frame_mark = "Incomplete"
                else:
                    current_frame_score = 10 + bonus_score
                    
                roll_pointer += 2 # A spare consumes two rolls in the sequence
            
            # Check for Open Frame (first two rolls sum to less than 10)
            elif roll_pointer + 1 < len(rolls): # Ensure at least two rolls are available for an open frame
                frame_rolls_in_current_attempt.extend([rolls[roll_pointer], rolls[roll_pointer + 1]])
                frame_mark = "Open"
                current_frame_score = rolls[roll_pointer] + rolls[roll_pointer + 1]
                roll_pointer += 2 # An open frame consumes two rolls
            else:
                # If only one roll is made in a non-10th frame and it's not a strike,
                # the frame is incomplete as it's waiting for the second roll.
                frame_rolls_in_current_attempt.append(rolls[roll_pointer])
                frame_mark = "Incomplete"
                current_frame_score = 0 # Cannot score yet
                # Do not advance roll_pointer fully here, as the frame is not complete
                # The next submission from client will add more rolls and we'll re-evaluate.
                break # Stop processing further frames, as current is incomplete

        # --- Scoring Logic for the 10th Frame ---
        else: # This is the 10th frame (frame_num == 10)
            # The 10th frame can have 2 or 3 rolls.
            # We need at least two rolls to determine its initial score and mark.
            if roll_pointer >= len(rolls) - 1: # Not even enough rolls for the first two rolls of 10th frame
                # If only one roll is supplied for the 10th frame, it's incomplete.
                if roll_pointer < len(rolls):
                    frame_rolls_in_current_attempt.append(rolls[roll_pointer])
                frame_mark = "Incomplete"
                current_frame_score = 0
                break # Cannot score fully yet, stop processing

            roll1 = rolls[roll_pointer]
            frame_rolls_in_current_attempt.append(roll1)

            roll2 = rolls[roll_pointer + 1]
            frame_rolls_in_current_attempt.append(roll2)
            
            pins_sum_first_two = roll1 + roll2

            if roll1 == 10: # Strike in 10th frame
                frame_mark = "Strike"
                # A strike in 10th frame grants 2 bonus rolls.
                if roll_pointer + 2 < len(rolls):
                    roll3 = rolls[roll_pointer + 2]
                    frame_rolls_in_current_attempt.append(roll3)
                    current_frame_score = roll1 + roll2 + roll3
                else:
                    frame_mark = "Incomplete" # Waiting for the third roll
                    current_frame_score = 0
            elif pins_sum_first_two == 10: # Spare in 10th frame
                frame_mark = "Spare"
                # A spare in 10th frame grants 1 bonus roll.
                if roll_pointer + 2 < len(rolls):
                    roll3 = rolls[roll_pointer + 2]
                    frame_rolls_in_current_attempt.append(roll3)
                    current_frame_score = roll1 + roll2 + roll3
                else:
                    frame_mark = "Incomplete" # Waiting for the third roll
                    current_frame_score = 0
            else: # Open frame in 10th
                frame_mark = "Open"
                current_frame_score = roll1 + roll2
            
            # Advance roll_pointer based on how many rolls were actually part of the 10th frame's scoring.
            if frame_mark != "Incomplete":
                roll_pointer += len(frame_rolls_in_current_attempt)
            else: # If 10th frame is incomplete, we still process the initial rolls and break.
                roll_pointer += len(frame_rolls_in_current_attempt) # Advance by rolls processed so far
                break


        # Add the current frame's result to the detail list
        frame_scores_detail.append({
            "frame": frame_num,
            "rolls": frame_rolls_in_current_attempt,
            "mark": frame_mark,
            "score": current_frame_score
        })
        
        # If the current frame couldn't be fully scored (e.g., waiting for bonus rolls),
        # we stop processing further frames until more rolls are provided by the client.
        if frame_mark == "Incomplete":
            break

    # Calculate the final total score by summing up scores of completed frames.
    # If a frame's mark is "Incomplete", its score is not yet final, and thus
    # not added to the running total until it can be fully calculated.
    final_total_score = sum(f["score"] for f in frame_scores_detail if f["mark"] != "Incomplete")
    
    # Determine if the game is over (all 10 frames are played and fully scored)
    game_over = False
    if len(frame_scores_detail) == 10:
        # Check if the last frame is fully scored (not "Incomplete")
        if frame_scores_detail[9]["mark"] != "Incomplete":
            game_over = True

    return {
        "total_score": final_total_score,
        "frame_scores": frame_scores_detail,
        "game_over": game_over
    }

# --- Flask Routes ---

@app.route('/')
def index():
    """Renders the main HTML page for the bowling game."""
    return render_template('index.html')

@app.route('/start_game', methods=['POST'])
def start_game():
    """
    Initializes a new game session in the database.
    Returns the new game_id to the client.
    """
    conn = None
    game_id = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        # Insert a new game record with start time
        cursor.execute("INSERT INTO games (start_time) VALUES (?)", (datetime.datetime.now(),))
        conn.commit()
        game_id = cursor.lastrowid # Get the ID of the newly inserted game
        return jsonify({"success": True, "game_id": game_id})
    except Exception as e:
        print(f"Error starting game: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/calculate_score', methods=['POST'])
def calculate_score_route():
    """
    Receives all rolls made so far from the client, calculates the score,
    and returns the updated game state including total score, frame scores,
    and whether the game is over.
    """
    data = request.json
    game_id = data.get('game_id')
    # rolls_so_far is expected to be a list of integers from the frontend
    rolls_so_far = data.get('rolls', []) 

    # Input validation: ensure rolls are valid (0-10)
    for roll in rolls_so_far:
        if not isinstance(roll, int) or not (0 <= roll <= 10):
            return jsonify({"success": False, "error": "Invalid roll value. Rolls must be integers between 0 and 10."}), 400

    game_state = calculate_bowling_score(rolls_so_far)
    
    # If the game is over, update the final score and end time in the database.
    if game_state['game_over']:
        conn = None
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE games SET end_time = ?, final_score = ? WHERE id = ?",
                (datetime.datetime.now(), game_state['total_score'], game_id)
            )
            conn.commit()
        except Exception as e:
            print(f"Error updating game result: {e}")
            # Log error but don't prevent the score from being returned to user
        finally:
            if conn:
                conn.close()

    return jsonify({"success": True, "game_state": game_state})

# --- Database Initialization (for development/first run) ---
# This function creates the 'games' table if it doesn't exist.
def create_db_tables():
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT DEFAULT CURRENT_TIMESTAMP,
                end_time TEXT NULL,
                final_score INTEGER NULL
            )
        """)
        conn.commit()
        print("Database tables created/verified successfully.")
    except Exception as e:
        print(f"Error creating database tables: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Ensure database tables are created before starting the app
    create_db_tables()
    app.run(debug=True, host='0.0.0.0')
