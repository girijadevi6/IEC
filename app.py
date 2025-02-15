from flask import Flask, render_template, request, redirect, session
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import random
import re
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Set a secret key for session management

def get_db_connection():
    conn = sqlite3.connect('ecommerce.db')
    conn.row_factory = sqlite3.Row
    return conn


# Load and clean your data
def clean_text(text):
    if pd.isnull(text):  # Check for NaN or missing values
        return "[missing data]"
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\.{3,}', '', text)
    text = text.capitalize()
    return text

# Assume you have your CSV loaded into `df`
data = pd.read_csv("cuisine_updated.csv", skipinitialspace=True)
df = pd.DataFrame(data)
df["ingredients"] = df["ingredients"].apply(clean_text)

@app.route('/')
def home():
    selected_category = request.args.get('category')  # Get the selected category from the query string
    conn = get_db_connection()

    # Fetch all items from the database
    query = """
    SELECT id, name, price, available_pieces, image_url, category
    FROM items
    """
    items = conn.execute(query).fetchall()

    # Fetch trending videos from the database
    trends_query = """
    SELECT video_url, item_name, item_link, thumbnail_url
    FROM trends
    """
    trends = conn.execute(trends_query).fetchall()

    conn.close()

    # Organize items by category
    categories = {}
    for item in items:
        if item['category'] not in categories:
            categories[item['category']] = []
        categories[item['category']].append(item)

    # Filter items for the selected category
    if selected_category:
        filtered_items = categories.get(selected_category, [])
    else:
        filtered_items = items  # Show all items if no category is selected

    # Cuisine, diet, and course dropdown options
    cuisines = df['cuisine'].unique().tolist()
    diets = df['diet'].unique().tolist()
    courses = ['Breakfast', 'Lunch', 'Dinner', 'Snack']  # Update this with more courses if needed

    return render_template(
        'index.html',
        categories=categories,
        items=filtered_items,
        selected_category=selected_category,
        logged_in='email' in session,
        cuisines=cuisines,
        diets=diets,
        courses=courses,
        trends=trends  # Pass the trends data
    )



def is_english(text):
    return bool(re.match(r'^[a-zA-Z0-9\s,.-]+$', text))

df = pd.DataFrame(data)

# Function to filter out non-English meals
df = df[df['name'].apply(is_english)]

@app.route('/select_cuisine', methods=['GET'])
def select_cuisine():
    # Fetch unique cuisines from the dataset
    cuisines = df['cuisine'].unique().tolist()
    return render_template('select_cuisine.html', cuisines=cuisines)

@app.route('/select_courses', methods=['POST'])
def select_courses():
    user_cuisine = request.form['cuisine']
    filtered_courses = df[df['cuisine'].str.lower() == user_cuisine.lower()]['course'].unique()
    return render_template('select_courses.html', courses=filtered_courses, cuisine=user_cuisine)



@app.route('/generate_meal_plan', methods=['POST'])
def generate_meal_plan():
    user_cuisine = request.form['cuisine']
    user_courses = request.form.getlist('course')  # Get the selected courses

    filtered_df = df[df['cuisine'].str.lower() == user_cuisine.lower()]

    if filtered_df.empty:
        return "No meals match your preferences. Please try different inputs."

    conn = get_db_connection()
    items = conn.execute('SELECT id, name FROM items').fetchall()
    conn.close()

    # Extract item names and their IDs (normalized to lowercase)
    item_mapping = {item['name'].strip().lower(): item['id'] for item in items}

    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    meal_plan = []

    for day in days:
        for course in user_courses:
            meal_options = filtered_df[filtered_df['course'].str.lower() == course.lower()]
            if not meal_options.empty:
                selected_meal = meal_options.sample(1).iloc[0]

                # Process ingredients to create links for available items
                ingredient_links = []
                for ingredient in selected_meal['ingredients'].split(', '):  # Assuming ingredients are comma-separated
                    words = ingredient.split()  # Split ingredient into individual words
                    ingredient_link_parts = []

                    for word in words:
                        # Remove any punctuation or extra spaces from each word
                        word = word.strip().lower()

                        # Check if the word exists in the item mapping
                        ingredient_id = item_mapping.get(word)

                        if ingredient_id:
                            # Create a clickable link for the matching item
                            ingredient_link_parts.append(f"<a href='/order/{ingredient_id}'>{word}</a>")
                        else:
                            # If no match, just display the word as is
                            ingredient_link_parts.append(word)

                    # Join the parts of the ingredient back together
                    ingredient_links.append(" ".join(ingredient_link_parts))

                meal_plan.append({
                    'Day': day,
                    'Course': course,
                    'Meal Name': selected_meal['name'],
                    'Description': selected_meal['description'],
                    'Prep Time (mins)': selected_meal['prep_time'],
                    'Ingredients': ', '.join(ingredient_links),  # Join links into a single string
                    'Instructions': selected_meal['instructions'],
                    'Image URL': selected_meal['image_url']
                })

    return render_template('meal_plan.html', meal_plan=meal_plan)


@app.route('/trends')
def trends():
    conn = get_db_connection()

    # Fetch all trend items from the trends table
    query = """
    SELECT video_url, item_name, item_link
    FROM trends
    """
    trends_data = conn.execute(query).fetchall()
    conn.close()

    # Prepare trends data for rendering
    trends = []
    for trend in trends_data:
        trends.append((trend['video_url'], trend['item_name'], trend['item_link']))

    return render_template('trends.html', trends=trends)

@app.route('/shorts_page')
def shorts_page():
    conn = get_db_connection()

    # Fetch all trend items from the trends table
    query = """
    SELECT video_url, item_name, item_link, thumbnail_url
    FROM trends
    """
    trends_data = conn.execute(query).fetchall()
    conn.close()

    # Prepare trends data for rendering
    shorts = []
    for trend in trends_data:
        shorts.append({
            'video_url': trend['video_url'],
            'item_name': trend['item_name'],
            'item_link': trend['item_link'],
            'thumbnail_url': trend['thumbnail_url']
        })

    return render_template('shorts.html', trends=shorts)


@app.route('/category/<category_name>')
def category_items(category_name):
    print(f"Category route: Selected category: {category_name}")  # Debug log
    items = get_items_by_category(category_name)
    categories = ["Men's Fashion", "Women's Fashion", "Grocery", "Beauty", "Sports"]
    return render_template(
        'index.html',
        categories=categories,
        items=items,
        selected_category=category_name,
        logged_in=session.get('email') is not None
    )

def get_items_by_category(category_name):
    print(f"Fetching items for category: {category_name}")  # Debug log
    conn = get_db_connection()
    query = "SELECT id, name, price, available_pieces, image_url, category FROM items WHERE category = ?"
    items = conn.execute(query, (category_name,)).fetchall()
    conn.close()
    print(f"Fetched items: {items}")  # Debug log
    return [dict(item) for item in items]  # Convert to dictionary


@app.route('/')
def index():
    category = request.args.get('category', "Men's Fashion")  # Default category
    print(f"Index route: Selected category: {category}")  # Debug log
    items = get_items_by_category(category)
    categories = ["Men's Fashion", "Women's Fashion", "Grocery", "Beauty", "Sports"]
    return render_template(
        'index.html',
        categories=categories,
        items=items,
        selected_category=category,
        logged_in=session.get('email') is not None
    )




@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        conn.execute('INSERT INTO users (email, password) VALUES (?, ?)', (email, password))
        conn.commit()
        conn.close()
        return redirect('/login')
    
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
        conn.close()

        if user:
            session['email'] = email
            return redirect('/')
        else:
            return 'Invalid credentials'

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect('/')


@app.route('/add', methods=['GET', 'POST'])
def add_item():
    if 'email' not in session or session['email'] != 'admin@gmail.com':
        return redirect('/login')

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        available_pieces = request.form['available_pieces']
        image_url = request.form['image_url']
        category = request.form['category']

        conn = get_db_connection()
        conn.execute(
            'INSERT INTO items (name, price, available_pieces, image_url, category) VALUES (?, ?, ?, ?, ?)',
            (name, price, available_pieces, image_url, category)
        )
        conn.commit()
        conn.close()

        return redirect('/')
    
    return render_template('add_item.html')


@app.route('/update/<int:item_id>', methods=['GET', 'POST'])
def update_item(item_id):
    if 'email' not in session or session['email'] != 'admin@gmail.com':
        return redirect('/login')  # Only admin can update items

    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()

    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        available_pieces = request.form['available_pieces']
        image_url = request.form['image_url']
        category=request.form['category']

        conn.execute('''
            UPDATE items 
            SET name = ?, price = ?, available_pieces = ?, image_url = ? ,category=?
            WHERE id = ?
        ''', (name, price, available_pieces, image_url,category, item_id))
        conn.commit()
        conn.close()
        return redirect('/')

    conn.close()
    return render_template('update_item.html', item=item)


@app.route('/delete/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    if 'email' not in session or session['email'] != 'admin@gmail.com':
        return redirect('/login')  # Only admin can delete items

    conn = get_db_connection()
    conn.execute('DELETE FROM items WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    return redirect('/')





def send_order_email(user_email, order_details):
    # SMTP server details (example: Gmail)
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # For TLS
    sender_email = "dgirija651@gmail.com"  # Your email address
    sender_password = "hslq iqzd keko jyxb"  # Your email password (or app password if using Gmail)
    
    # Create the email message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = user_email
    msg['Subject'] = "Your Order Confirmation"

    # Order details to send in the email body
    order_info = f"Hello,\n\nThank you for your order! Here are your order details:\n\n{order_details}\n\nBest Regards,\nYour Company"
    
    msg.attach(MIMEText(order_info, 'plain'))
    
    try:
        # Connect to the Gmail SMTP server and send the email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, user_email, text)
        server.quit()  # Terminate the session
        print("Email sent successfully!")
    except Exception as e:
        print(f"Error sending email: {e}")


@app.route('/order/<int:item_id>', methods=['GET', 'POST'])
def place_order(item_id):
    if 'email' not in session:
        return redirect('/login')  # Ensure the user is logged in before ordering

    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()

    if not item:
        conn.close()
        return "Item not found."

    if request.method == 'POST':
        email = session['email']
        quantity = int(request.form['quantity'])

        if item['available_pieces'] < quantity:
            conn.close()
            return "Not enough items in stock."

        total_price = item['price'] * quantity

        # Insert the order into the orders table
        conn.execute(''' 
            INSERT INTO orders (email, item_name, quantity, total_price)
            VALUES (?, ?, ?, ?)
        ''', (email, item['name'], quantity, total_price))

        # Update the available pieces in the items table
        conn.execute('''
            UPDATE items SET available_pieces = available_pieces - ? WHERE id = ?
        ''', (quantity, item_id))

        conn.commit()

        # Prepare order details to send in email
        order_details = f"""
        Order Number: #12345 (or generate dynamically)
        Product: {item['name']}
        Quantity: {quantity}
        Total Price: ${total_price}
        """

        # Send email to the user with order details
        try:
            send_order_email(email, order_details)
            print("Email sent successfully!")
        except Exception as e:
            print(f"Failed to send email: {e}")

        conn.close()
        return redirect('/')

    conn.close()
    return render_template('order_form.html', item=item)


@app.route('/my_orders')
def my_orders():
    if 'email' not in session:
        return redirect('/login') # Ensure the user is logged in

    email = session['email']

    conn = get_db_connection()
    orders = conn.execute('SELECT * FROM orders WHERE email = ?', (email,)).fetchall()
    conn.close()

    total_price = sum(order['total_price'] for order in orders)
    
    return render_template('my_orders.html', orders=orders, total_price=total_price)



if __name__ == '__main__':
    app.run(debug=True)
