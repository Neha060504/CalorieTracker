"""
File: app.py - Main Application Controller for Bhukad Neha (MyFitness Buddy)

WHAT IT DOES:
- Initializes the Flask web application and binds database connections to MariaDB.
- Manages user sessions, authentication (login, signup with PBKDF2 password hashing, logout).
- Handles daily meal tracking, water consumption logging, and physical activity/calorie-burn calculations.
- Provides interactive nutrition dashboards and graphical trend reports.
- Integrates Google Gemini AI ('Chef Naya' and 'Gemini Coach') for personalized Indian recipe generation
  and 7-day health insight coaching tailored to user allergies, dietary preferences, and medical conditions.
- Exposes RESTful APIs for food library auto-completion and asynchronous coaching history.

WHY IT IS USED:
- Serves as the central server-side brain for the Bhukad Neha fitness and diet tracking ecosystem.
"""

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response, stream_with_context
import mysql.connector
from mysql.connector import Error
from passlib.hash import pbkdf2_sha256
from database_setup import setup_database
from datetime import datetime
from google import genai
from google.genai import types
import csv
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super_secret_key_for_calorie_tracker')

# Database configuration
db_config = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'port': int(os.environ.get('DB_PORT', 3308)),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', 'Shriyash@11'),
    'database': os.environ.get('DB_NAME', 'calorieapp')
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None

# Ensure database and tables are created on startup
setup_database()

# Food Data CSV Configuration
FOOD_DATA_CSV = 'food_data.csv'

def get_food_library():
    food_library = {}
    if os.path.exists(FOOD_DATA_CSV):
        try:
            with open(FOOD_DATA_CSV, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    food_library[row['food_name'].lower()] = int(row['calories'])
        except Exception as e:
            print(f"Error reading CSV: {e}")
    return food_library

def save_to_food_library(name, calories):
    library = get_food_library()
    if name.lower() not in library:
        file_exists = os.path.exists(FOOD_DATA_CSV)
        try:
            with open(FOOD_DATA_CSV, mode='a', newline='', encoding='utf-8') as f:
                fieldnames = ['food_name', 'calories']
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                if not file_exists:
                    writer.writeheader()
                writer.writerow({'food_name': name, 'calories': calories})
        except Exception as e:
            print(f"Error writing to CSV: {e}")

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            conn.close()
            
            if user and pbkdf2_sha256.verify(password, user['password']):
                session['user_id'] = user['id']
                session['username'] = user['username']
                return redirect(url_for('dashboard'))
            else:
                return render_template('login.html', error="Invalid username or password")
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        target_calories = request.form.get('target_calories', 2000)
        
        hashed_password = pbkdf2_sha256.hash(password)
        
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, email, password, target_calories) VALUES (%s, %s, %s, %s)",
                             (username, email, hashed_password, target_calories))
                conn.commit()
                conn.close()
                return redirect(url_for('login', success="Account created successfully!"))
            except Error as e:
                return render_template('login.html', signup_error=f"User already exists or error occurred: {e}")
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    today = datetime.now().strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        cursor.execute("SELECT * FROM meals WHERE user_id = %s AND date = %s", (user_id, today))
        meals = cursor.fetchall()
        total_calories = sum(m['calories'] for m in meals)
        
        cursor.execute("SELECT SUM(amount_ml) as total_water FROM water_intake WHERE user_id = %s AND date = %s", (user_id, today))
        water_data = cursor.fetchone()
        total_water = water_data['total_water'] if water_data['total_water'] else 0
        
        cursor.execute("SELECT SUM(calories_burned) as total_burned FROM activities WHERE user_id = %s AND date = %s", (user_id, today))
        activity_data = cursor.fetchone()
        total_burned = activity_data['total_burned'] if activity_data['total_burned'] else 0
        
        # Water Trends (Amount + Frequency)
        cursor.execute("SELECT date, SUM(amount_ml) as total, COUNT(*) as logs FROM water_intake WHERE user_id = %s GROUP BY date ORDER BY date DESC LIMIT 7", (user_id,))
        water_trends = cursor.fetchall()
        
        # Hourly Distribution (For today)
        cursor.execute("SELECT HOUR(timestamp) as hour, SUM(amount_ml) as total FROM water_intake WHERE user_id = %s AND date = %s GROUP BY hour ORDER BY hour ASC", (user_id, today))
        hourly_data = cursor.fetchall()
        
        # Recent Water Logs (For text display)
        cursor.execute("""
            SELECT amount_ml, DATE_FORMAT(timestamp, '%h:%i %p') as time 
            FROM water_intake 
            WHERE user_id = %s AND date = %s 
            ORDER BY timestamp DESC LIMIT 5
        """, (user_id, today))
        recent_water_logs = cursor.fetchall() or []
        
        total_logs = sum(d['logs'] for d in water_trends if str(d['date']) == str(today)) if water_trends else 0
        
        conn.close()
        
        return render_template('dashboard.html', 
                             user=user, 
                             meals=meals, 
                             total_calories=total_calories, 
                             total_water=total_water, 
                             total_burned=total_burned,
                             total_logs=total_logs,
                             water_trends=water_trends[::-1],
                             hourly_data=hourly_data,
                             recent_water_logs=recent_water_logs,
                             active_page='dashboard')
    return redirect(url_for('login'))

@app.route('/meals')
def meals():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM meals WHERE user_id = %s ORDER BY date DESC, id DESC", (user_id,))
        all_meals = cursor.fetchall()
        
        # Breakdown by meal type for pie chart
        cursor.execute("""
            SELECT meal_type, SUM(calories) as total FROM meals 
            WHERE user_id = %s GROUP BY meal_type
        """, (user_id,))
        breakdown_data = cursor.fetchall()
        
        # Top 5 high calorie meals
        cursor.execute("""
            SELECT meal_name, calories FROM meals 
            WHERE user_id = %s ORDER BY calories DESC LIMIT 5
        """, (user_id,))
        top_meals = cursor.fetchall()
        
        conn.close()
        return render_template('meals.html', 
                             meals=all_meals, 
                             breakdown_data=breakdown_data,
                             top_meals=top_meals,
                             active_page='meals')
    return redirect(url_for('login'))

@app.route('/activities')
def activities():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM activities WHERE user_id = %s ORDER BY date DESC, id DESC", (user_id,))
        all_activities = cursor.fetchall()
        
        # Duration by activity type
        cursor.execute("""
            SELECT activity_name, SUM(duration_mins) as total_mins FROM activities 
            WHERE user_id = %s GROUP BY activity_name
        """, (user_id,))
        activity_dist = cursor.fetchall()
        
        # Weekly burn trend
        cursor.execute("""
            SELECT date, SUM(calories_burned) as daily_burn FROM activities 
            WHERE user_id = %s GROUP BY date ORDER BY date DESC LIMIT 7
        """, (user_id,))
        burn_trend = cursor.fetchall()
        
        conn.close()
        return render_template('activities.html', 
                             activities=all_activities, 
                             activity_dist=activity_dist,
                             burn_trend=burn_trend[::-1],
                             active_page='activities')
    return redirect(url_for('login'))

@app.route('/reports')
def reports():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # 1. Weekly Calorie Balance (Consumed vs Burned)
        cursor.execute("""
            SELECT m.date, SUM(m.calories) as consumed, 
            (SELECT SUM(calories_burned) FROM activities WHERE user_id = %s AND date = m.date) as burned
            FROM meals m WHERE m.user_id = %s GROUP BY m.date ORDER BY m.date DESC LIMIT 7
        """, (user_id, user_id))
        balance_data = cursor.fetchall()
        
        # 2. Meal Type Distribution (Today)
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT meal_type, SUM(calories) as total FROM meals 
            WHERE user_id = %s AND date = %s GROUP BY meal_type
        """, (user_id, today))
        distribution_data = cursor.fetchall()
        
        # 3. Hydration Trend
        cursor.execute("""
            SELECT date, SUM(amount_ml) as total_ml FROM water_intake 
            WHERE user_id = %s GROUP BY date ORDER BY date DESC LIMIT 7
        """, (user_id,))
        hydration_data = cursor.fetchall()
        
        conn.close()
        return render_template('reports.html', 
                             balance_data=balance_data[::-1], 
                             distribution_data=distribution_data,
                             hydration_data=hydration_data[::-1],
                             active_page='reports')
    return redirect(url_for('login'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    if request.method == 'POST':
        email = request.form['email']
        target_calories = request.form['target_calories']
        gemini_api_key = request.form.get('gemini_api_key')
        allergies = request.form.get('allergies', '')
        favorite_foods = request.form.get('favorite_foods', '')
        diseases = request.form.get('diseases', '')
        health_issues = request.form.get('health_issues', '')
        disability = request.form.get('disability', '')
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET email = %s, target_calories = %s, gemini_api_key = %s,
                    allergies = %s, favorite_foods = %s, diseases = %s, 
                    health_issues = %s, disability = %s 
                WHERE id = %s
            """, (email, target_calories, gemini_api_key, allergies, favorite_foods, diseases, health_issues, disability, user_id))
            conn.commit()
            conn.close()
            return redirect(url_for('settings', success="Profile and AI configuration updated!"))
            
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return render_template('settings.html', user=user, active_page='settings')
    return redirect(url_for('login'))

@app.route('/api/food')
def get_food_api():
    library = get_food_library()
    # Convert to list of dicts for frontend datalist
    return jsonify([{'name': name.title(), 'calories': cal} for name, cal in library.items()])

@app.route('/add_meal', methods=['POST'])
def add_meal():
    if 'user_id' in session:
        meal_name = request.form['meal_name']
        meal_type = request.form['meal_type']
        calories = int(request.form['calories'])
        user_id = session['user_id']
        
        # Save to CSV if it's a unique item
        save_to_food_library(meal_name, calories)
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO meals (user_id, meal_name, meal_type, calories) VALUES (%s, %s, %s, %s)",
                         (user_id, meal_name, meal_type, calories))
            conn.commit()
            conn.close()
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/add_water', methods=['POST'])
def add_water():
    if 'user_id' in session:
        amount_ml = request.form.get('amount_ml')
        custom_amount = request.form.get('custom_amount_ml')
        
        # Use custom amount if provided, otherwise use the preset button value
        final_amount = int(custom_amount) if custom_amount and custom_amount.strip() else int(amount_ml) if amount_ml else 0
        
        if final_amount > 0:
            user_id = session['user_id']
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("INSERT INTO water_intake (user_id, amount_ml) VALUES (%s, %s)",
                             (user_id, final_amount))
                conn.commit()
                conn.close()
    return redirect(url_for('dashboard'))

@app.route('/add_activity', methods=['POST'])
def add_activity():
    if 'user_id' in session:
        activity_name = request.form['activity_name']
        calories_burned = int(request.form['calories_burned'])
        duration = int(request.form['duration'])
        user_id = session['user_id']
        
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO activities (user_id, activity_name, calories_burned, duration_mins) VALUES (%s, %s, %s, %s)",
                         (user_id, activity_name, calories_burned, duration))
            conn.commit()
            conn.close()
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/ai_coach')
def ai_coach():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user_id = session['user_id']
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        # We don't generate the insights automatically on load to save API costs.
        # Instead, the template will have a button that triggers a POST request to generate it.
        conn.close()
        return render_template('ai_coach.html', user=user, active_page='ai_coach')
    return redirect(url_for('login'))

@app.route('/recipes')
def recipes():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('recipes.html', active_page='recipes')

@app.route('/generate_recipes', methods=['POST'])
def generate_recipes():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    data = request.json
    ingredients_list = data.get('ingredients', [])
    special_notes = data.get('notes', '')
    cuisine = data.get('cuisine', 'Indian')
    focus = data.get('focus', 'Balanced')
    
    if not ingredients_list:
        return jsonify({'error': 'Please provide at least one ingredient.'}), 400
        
    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
        
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user or not user.get('gemini_api_key'):
            return jsonify({'error': 'Please configure your Gemini API Key in Settings.'}), 400
            
        api_key = user['gemini_api_key']
        client = genai.Client(api_key=api_key)
        
        # Build user profile string for prompt
        profile_context = f"""
        USER PROFILE & CONSTRAINTS:
        - Allergies: {user.get('allergies') or 'None'}
        - Favorite Foods: {user.get('favorite_foods') or 'Any'}
        - Medical Conditions: {user.get('diseases') or 'None'}
        - Health Concerns: {user.get('health_issues') or 'None'}
        - Physical Constraints: {user.get('disability') or 'None'}
        """
        
        ingredients_str = ", ".join(ingredients_list)
        prompt = f"""
        You are 'Chef Naya', an AI health expert specialized in {cuisine} cuisine with a focus on {focus}.
        
        {profile_context}
        
        Available Ingredients: {ingredients_str}
        Taste Customization: {special_notes if special_notes else 'None'}
        
        Task: Recommend 2 healthy dishes that respect the USER PROFILE constraints.
        IMPORTANT: If the user has allergies, NEVER include those ingredients. If they have diseases like Diabetes, ensure low glycemic index.
        
        For each dish, include:
        1. Dish Name (Inside <h3>)
        2. Description & Health Context (Inside <p>)
        3. Ingredients (Inside <ul>)
        4. Preparation Steps (Inside <ol>)
        5. Estimated Calories (Inside a <b> tagged section)
        6. Health Benefits (Inside a <ul> tagged section, mention specific benefits for Indian bodies)
        
        OUTPUT FORMATTING RULES:
        - Use ONLY these HTML tags: <h3>, <p>, <b>, <ul>, <li>, <ol>, <hr>.
        - Do NOT include Markdown code blocks (e.g. ```html). Just raw HTML text.
        - Tone: Sophisticated, health-conscious, and encouraging.
        - Focus on using authentic Indian spices while keeping oil/sugar low.
        """
        
        def generate():
            full_text = ""
            response = client.models.generate_content_stream(
                model='gemini-3-flash-preview',
                contents=prompt
            )
            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    yield chunk.text
            
            # Save history
            if full_text:
                try:
                    save_conn = get_db_connection()
                    if save_conn:
                        save_cursor = save_conn.cursor()
                        # Save both ingredients and notes combined in the history field for now
                        history_ingredients = f"Ingredients: {ingredients_str}"
                        if special_notes:
                            history_ingredients += f" | Notes: {special_notes}"
                            
                        save_cursor.execute("INSERT INTO recipe_history (user_id, ingredients, recipe_text) VALUES (%s, %s, %s)", 
                                         (user_id, history_ingredients, full_text))
                        save_conn.commit()
                        save_conn.close()
                except Exception as e:
                    print(f"Failed to save recipe history: {e}")
        
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/generate_insights', methods=['POST'])
def generate_insights():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
        
    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
        
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        
        if not user_data or not user_data.get('gemini_api_key'):
            return jsonify({'error': 'No API key configured.'}), 400
            
        # Get 7-day data
        cursor.execute("SELECT date, SUM(calories) as cal FROM meals WHERE user_id = %s GROUP BY date ORDER BY date DESC LIMIT 7", (user_id,))
        meals = cursor.fetchall()
        
        cursor.execute("SELECT date, SUM(calories_burned) as burn FROM activities WHERE user_id = %s GROUP BY date ORDER BY date DESC LIMIT 7", (user_id,))
        activities = cursor.fetchall()
        
        cursor.execute("SELECT date, SUM(amount_ml) as ml FROM water_intake WHERE user_id = %s GROUP BY date ORDER BY date DESC LIMIT 7", (user_id,))
        water = cursor.fetchall()
        
        # Build profile context
        profile_context = f"""
        USER PROFILE:
        - Allergies: {user_data.get('allergies') or 'None'}
        - Medical Conditions: {user_data.get('diseases') or 'None'}
        - Health Concerns: {user_data.get('health_issues') or 'None'}
        - Physical Constraints: {user_data.get('disability') or 'None'}
        """
        
        prompt = f"""
        You are 'Coach Naya', an expert fitness and nutrition coach specialized in Indian dietary habits and physiology.
        Analyze the last 7 days of my health data and provide insights tailored for my profile.
        
        {profile_context}
        
        My Target Calories: {user_data['target_calories']} kcal/day.
        
        Recent Meals: {meals}
        Recent Activities: {activities}
        Recent Hydration: {water}
        
        Provide 3-4 clear, actionable points regarding my diet (considering Indian dishes), hydration, and exercise. 
        Mention specific health benefits for common Indian ingredients if they appear in my log.
        Use simple HTML formatting (<b>, <ul>, <li>) for a premium dashboard look.
        """
        
        api_key = user_data['gemini_api_key']
        client = genai.Client(api_key=api_key)
        
        def generate():
            full_text = ""
            response = client.models.generate_content_stream(
                model='gemini-3-flash-preview',
                contents=prompt
            )
            for chunk in response:
                if chunk.text:
                    full_text += chunk.text
                    yield chunk.text
                    
            # Save history
            if full_text:
                try:
                    save_conn = get_db_connection()
                    if save_conn:
                        save_cursor = save_conn.cursor()
                        save_cursor.execute("INSERT INTO coach_history (user_id, analysis_text) VALUES (%s, %s)", (user_id, full_text))
                        save_conn.commit()
                        save_conn.close()
                except Exception as e:
                    print(f"Failed to save coach history: {e}")
                    
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/ai_chat', methods=['POST'])
def ai_chat():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_message = request.json.get('message', '')
    if not user_message:
        return jsonify({'error': 'Empty message'}), 400
        
    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
        
    try:
        cursor = conn.cursor(dictionary=True)
        # Fetch API key
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_record = cursor.fetchone()
        
        if not user_record or not user_record.get('gemini_api_key'):
            return jsonify({'error': 'Please configure your Gemini API Key in Settings.'}), 400
            
        api_key = user_record['gemini_api_key']
        
        # Profile Context
        profile_context = f"Allergies: {user_record.get('allergies') or 'None'}, Diseases: {user_record.get('diseases') or 'None'}, Issues: {user_record.get('health_issues') or 'None'}, Disability: {user_record.get('disability') or 'None'}"
        
        # Gather Context
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Today's Meals
        cursor.execute("SELECT SUM(calories) as cal FROM meals WHERE user_id = %s AND date = %s", (user_id, today))
        meals_res = cursor.fetchone()
        cals_consumed = meals_res['cal'] if meals_res and meals_res['cal'] else 0
        
        # Today's Water
        cursor.execute("SELECT SUM(amount_ml) as ml FROM water_intake WHERE user_id = %s AND date = %s", (user_id, today))
        water_res = cursor.fetchone()
        water_consumed = water_res['ml'] if water_res and water_res['ml'] else 0
        
        # Today's Activities
        cursor.execute("SELECT SUM(calories_burned) as burn FROM activities WHERE user_id = %s AND date = %s", (user_id, today))
        act_res = cursor.fetchone()
        cals_burned = act_res['burn'] if act_res and act_res['burn'] else 0
        
        client = genai.Client(api_key=api_key)
        
        system_prompt = f"""You are 'Gemini Coach', an expert health AI specialized in Indian nutrition for 'MyFitness Buddy'.
USER PROFILE: {profile_context}
User's Stats for Today:
- Calories consumed: {cals_consumed} kcal
- Water drank: {water_consumed} ml
- Calories burned: {cals_burned} kcal
Keep answers short, supportive, and strictly respect allergies/diseases. Under 3 sentences."""
        
        def generate():
            response = client.models.generate_content_stream(
                model='gemini-3-flash-preview',
                contents=f"{system_prompt}\n\nUser Question: {user_message}"
            )
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        return Response(stream_with_context(generate()), mimetype='text/event-stream')
    except Exception as e:
        return jsonify({'error': 'Failed to communicate with AI model. Check your API key.'}), 500
    finally:
        conn.close()

@app.route('/api/recipe_history', methods=['GET'])
def get_recipe_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
        
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM recipe_history WHERE user_id = %s ORDER BY timestamp DESC LIMIT 5", (user_id,))
        history = cursor.fetchall()
        # Ensure timestamps are serialized correctly for JSON
        for h in history:
            if h.get('timestamp'):
                h['timestamp'] = h['timestamp'].isoformat()
        return jsonify({'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/coach_history', methods=['GET'])
def get_coach_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user_id = session['user_id']
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database error'}), 500
        
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM coach_history WHERE user_id = %s ORDER BY timestamp DESC LIMIT 5", (user_id,))
        history = cursor.fetchall()
        # Ensure timestamps are serialized correctly for JSON
        for h in history:
            if h.get('timestamp'):
                h['timestamp'] = h['timestamp'].isoformat()
        return jsonify({'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    app.run(debug=True)
