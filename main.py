from flask import Flask, render_template, request, flash, redirect, url_for, session
import mysql.connector
from datetime import datetime
app = Flask(__name__)
app.secret_key = "lol"

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="amrit505",
        database="dbms")

print("Connected to MySQL!")

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
def auth():
    username = request.form['name']
    password = request.form['email']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM account WHERE name = %s AND email = %s", (username, password))
    user = cursor.fetchone()

    if user:
        session['user_id'] = user['user_ID']
        session['name'] = user['name']
        cursor.execute("SELECT profile_ID, prof_name FROM Profile WHERE user_ID = %s", (user['user_ID'],))
        profiles = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('select_profile.html', profiles=profiles)
    else:
        cursor.close()
        conn.close()
        flash("Invalid username or password.")
        return redirect(url_for('login'))

@app.route('/select-profile', methods=['GET', 'POST'])
def select_profile():
    if request.method == 'POST':
        profile_id = request.form['profile_id']
        session['profile_id'] = profile_id
        return redirect(url_for('homepage'))
    else:
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('login'))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT profile_ID, prof_name FROM Profile WHERE user_ID = %s", (user_id,))
        profiles = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('select_profile.html', profiles=profiles)


@app.route('/admin')
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT genre_ID, genre_name FROM Genre")
    genres = cursor.fetchall()  # Fetch all genres

    cursor.close()
    conn.close()

    return render_template('admin_dashboard.html', genres=genres)


@app.route('/watch/<int:id>')
def watch_content(id):
    if 'profile_id' not in session:
        return redirect(url_for('login'))

    profile_id = session['profile_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    # Try treating it as a movie (content_ID)
    cursor.execute("SELECT url FROM Content WHERE content_ID = %s", (id,))
    result = cursor.fetchone()
    is_episode = False

    # If not found, treat it as an episode (episode_ID)
    if not result or not result[0]:
        cursor.execute("SELECT url, content_ID FROM Episode WHERE episode_ID = %s", (id,))
        result = cursor.fetchone()
        is_episode = True

    if result and result[0]:
        # Use correct content_ID for watch history
        actual_content_id = id if not is_episode else result[1]

        # Check if already in history
        cursor.execute("""
            SELECT 1 FROM profile_watch_history
            WHERE profile_id = %s AND content_id = %s
        """, (profile_id, actual_content_id))
        exists = cursor.fetchone()

        if not exists:
            cursor.execute("""
                INSERT INTO profile_watch_history (profile_id, content_id, watched_timestamp)
                VALUES (%s, %s, NOW())
            """, (profile_id, actual_content_id))  # `actual_content_id` should always be correct here.

        # If everything is working correctly, the URL should be returned, and the watch history should be updated for both movies and episodes.

        conn.commit()
        cursor.close()
        conn.close()
        return redirect(result[0])

    cursor.close()
    conn.close()
    return "Content not found or URL missing", 404


@app.route('/home', methods=['GET', 'POST'])
def homepage():
    if 'profile_id' not in session:
        return redirect(url_for('login'))

    selected_genre = request.args.get('genre')  # From dropdown

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch all distinct genres linked to either movies or series in content_genre
    cursor.execute("""
        SELECT DISTINCT g.genre_name
        FROM Genre g
        JOIN Content_Genre cg ON g.genre_ID = cg.genre_ID
    """)
    genres = [row['genre_name'] for row in cursor.fetchall()]

    # Query for Movies based on genre
    if selected_genre and selected_genre != "All":
        cursor.execute("""
            SELECT c.content_ID, c.title, c.description, c.url
            FROM Content c
            JOIN Content_Genre cg ON c.content_ID = cg.content_ID
            JOIN Genre g ON cg.genre_ID = g.genre_ID
            WHERE c.content_type = 'Movie' AND g.genre_name = %s AND c.url IS NOT NULL
        """, (selected_genre,))
    else:
        cursor.execute("""
            SELECT content_ID, title, description, url 
            FROM Content 
            WHERE content_type = 'Movie' AND url IS NOT NULL
        """)
    movies = cursor.fetchall()

    # Query for Series based on genre
    if selected_genre and selected_genre != "All":
        cursor.execute("""
            SELECT c.content_ID, c.title, c.description
            FROM Content c
            JOIN Content_Genre cg ON c.content_ID = cg.content_ID
            JOIN Genre g ON cg.genre_ID = g.genre_ID
            WHERE c.content_type = 'Series' AND g.genre_name = %s
        """, (selected_genre,))
        print("selected series before linking")
    else:
        cursor.execute("""
            SELECT content_ID, title, description 
            FROM Content 
            WHERE content_type = 'Series'
        """)
    series_raw = cursor.fetchall()

    series_list = []
    for s in series_raw:
        # Create a new cursor for episode query to avoid unread result issue
        cursor2 = conn.cursor(dictionary=True)
        cursor2.execute("""
            SELECT episode_ID, content_ID, episode_name, episode_num, season_num, url, description
            FROM Episode
            WHERE content_ID = %s
        """, (s['content_ID'],))

        episodes = cursor2.fetchall()
        cursor2.close()

        series_list.append({
            'content_ID': s['content_ID'],  # <-- this is the fix
            'title': s['title'],
            'description': s['description'],
            'episodes': episodes
        })


    return render_template('homepage.html', movies=movies, series_list=series_list, genres=genres, selected_genre=selected_genre)

#-----------sign up page-----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        dob = request.form.get('dob')
        subs_id = request.form.get('subs_id')
        reg_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        try:
            # Get last user_id
            cursor.execute("SELECT MAX(user_id) AS max_id FROM account")
            result = cursor.fetchone()
            next_user_id = (result['max_id'] or 0) + 1

            # Insert user data with manual user_id
            cursor.execute("""
                INSERT INTO account (user_id, name, email, dob, reg_date, subs_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (next_user_id, name, email, dob, reg_date, subs_id))
            conn.commit()

            flash('Signup successful! Please log in.')
            return redirect(url_for('login'))

        except mysql.connector.Error as err:
            flash(f"Error: {err}")
            return redirect(url_for('signup'))

    # Fetch subscriptions for dropdown
    try:
        cursor.execute("SELECT subs_id, subs_type FROM subscriptions")
        subscriptions = cursor.fetchall()
    except mysql.connector.Error as err:
        flash(f"Error fetching subscriptions: {err}")
        subscriptions = []

    cursor.close()
    conn.close()

    return render_template('signup.html', subscriptions=subscriptions)
#------------------------------------------------

@app.route('/create-profile', methods=['GET', 'POST'])
def create_profile():
    if request.method == 'POST':
        prof_name = request.form['prof_name']
        user_id = session.get('user_id')

        if not user_id:
            return redirect(url_for('login'))

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(profile_ID) FROM Profile")
        last_id = cursor.fetchone()[0]
        new_id = 1 if last_id is None else last_id + 1

        cursor.execute("INSERT INTO Profile (profile_ID, user_ID, prof_name) VALUES (%s, %s, %s)",
                       (new_id, user_id, prof_name))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('select_profile'))

    return render_template('create_profile.html')


@app.route('/top-viewers')
def top_viewers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.user_ID, a.name, (
            SELECT COUNT(w.content_ID)
            FROM Profile p
            LEFT JOIN Profile_Watch_History w ON p.profile_ID = w.profile_ID
            WHERE p.user_ID = a.user_ID
        ) AS total_watched
        FROM Account a
        ORDER BY total_watched DESC;
    """)
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('top_viewers.html', users=users)

@app.route('/expired')
def show_expired_subscriptions():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.user_ID, a.name, s.subs_type AS Subscription_Type, a.reg_date AS Registration_Date, 
            CONCAT(CAST(s.validity_period AS CHAR), ' days') AS Validity_Period,
            DATE_ADD(a.reg_date, INTERVAL s.validity_period DAY) AS Expiry_Date
        FROM Account a
        JOIN Subscriptions s ON a.subs_id = s.subs_id
        WHERE DATE_ADD(a.reg_date, INTERVAL s.validity_period DAY) < NOW()
    """)
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('expired.html', expired_accounts=data)

@app.route('/watchlist')
def watchlist():
    profile_id = session.get('profile_id')
    if not profile_id:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.content_ID, c.title, c.description, c.url
        FROM Content c
        JOIN Watchlist_Content wc ON c.content_ID = wc.content_ID
        WHERE wc.profile_ID = %s
    """, (profile_id,))

    watchlist_content = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('watchlist.html', watchlist_content=watchlist_content)


@app.route('/maxed-profiles')
def show_maxed_profiles():
    conn=get_db_connection()
    cursor=conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT a.user_ID, a.name, COUNT(p.profile_ID) AS profile_count, s.max_profiles
        FROM Account a
        JOIN Subscriptions s ON a.subs_id = s.subs_id
        LEFT JOIN Profile p ON a.user_ID = p.user_ID
        GROUP BY a.user_ID, a.name, s.max_profiles
        HAVING COUNT(p.profile_ID) >= s.max_profiles;
    """)
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('maxprofiles.html', maxed_accounts=data)

@app.route('/genres-explored')
def genres_explored():
    conn =get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            A.user_ID AS Account_ID,
            A.name AS Account_Name,
            COUNT(DISTINCT CG.genre_ID) AS Genres_Explored
        FROM Account A
        LEFT JOIN Profile P ON A.user_ID = P.user_id
        LEFT JOIN Profile_Watch_History W ON P.profile_ID = W.profile_ID
        LEFT JOIN Content_Genre CG ON W.content_ID = CG.content_ID
        GROUP BY A.user_ID, A.name;
    """)
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('genres_explored.html', accounts=data)


@app.route('/genre-viewers', methods=['GET', 'POST'])
def genre_viewers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        genre_id = request.form['genre_id']
    else:
        genre_id = 2 #hardcodingg

    cursor.execute("""
        SELECT p.profile_id, p.prof_name
        FROM Profile p
        WHERE p.profile_id IN (
            SELECT pwh.profile_ID
            FROM Profile_Watch_History pwh
            WHERE pwh.content_ID IN (
                SELECT cg.content_ID
                FROM Content_genre cg
                WHERE cg.genre_ID = %s
            )
        )
        ORDER BY p.prof_name;
    """, (genre_id,))

    profiles = cursor.fetchall()

    cursor.execute("SELECT genre_ID, genre_name FROM Genre")
    genres = cursor.fetchall()  # Fetch all available genres for the dropdown

    cursor.close()
    conn.close()

    return render_template('genre_viewers_kanu.html', profiles=profiles, genre_id=genre_id, genres=genres)
@app.route('/add-to-watchlist', methods=['POST'])
def add_to_watchlist():
    profile_id = session.get('profile_id')
    content_id = request.form.get('content_id')

    if not profile_id or not content_id:
        flash("You must be logged in with a profile to add to watchlist.")
        return redirect(url_for('homepage'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Prevent duplicates
    cursor.execute("""
        SELECT 1 FROM Watchlist_Content
        WHERE profile_ID = %s AND content_ID = %s
    """, (profile_id, content_id))
    exists = cursor.fetchone()

    if not exists:
        cursor.execute("""
            INSERT INTO Watchlist_Content (profile_ID, content_ID)
            VALUES (%s, %s)
        """, (profile_id, content_id))
        conn.commit()
        flash("Added to watchlist!")

    else:
        flash("Already in watchlist.")

    cursor.close()
    conn.close()

    return redirect(url_for('homepage'))


@app.route('/watch-history/<int:profile_id>')
def watch_history(profile_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT 
            p.prof_name,
            c.title,
            g.genre_name,
            pwh.watched_timestamp
        FROM Profile p
        JOIN Profile_Watch_History pwh ON p.profile_ID = pwh.profile_ID
        JOIN Content c ON pwh.content_ID = c.content_ID
        JOIN Content_genre cg ON c.content_ID = cg.content_ID
        JOIN Genre g ON cg.genre_ID = g.genre_ID
        WHERE p.profile_ID = %s
        ORDER BY pwh.watched_timestamp DESC;
    """, (profile_id,))
    
    history = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('watch_history_kanu.html', history=history, profile_id=profile_id)

@app.route('/content-analytics')
def content_analytics():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            c.content_type,
            g.genre_name,
            COUNT(DISTINCT c.content_ID) AS content_count,
            AVG(c.duration) AS avg_duration,
            COUNT(pwh.content_ID) AS total_views
        FROM Content c
        JOIN Content_genre cg ON c.content_ID = cg.content_ID
        JOIN Genre g ON cg.genre_ID = g.genre_ID
        LEFT JOIN Profile_Watch_History pwh ON c.content_ID = pwh.content_ID
        GROUP BY c.content_type, g.genre_name
        ORDER BY total_views DESC, avg_duration DESC;
    """)
    
    stats = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('content_analytics.html', stats=stats)

@app.route('/no-subscription-users')
def no_subscription_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.user_id, a.name
        FROM Account a
        LEFT JOIN Subscriptions s ON a.subs_id = s.subs_id
        WHERE COALESCE(s.subs_type, 'UNKNOWN') = 'UNKNOWN';
    """)
    
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('no_subscriptions_users.html', users=users)

@app.route('/watch-log')
def watch_log():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT p.prof_name, c.title, wh.watched_timestamp
FROM Profile_Watch_History wh
JOIN Profile p ON wh.profile_id = p.profile_id
JOIN Content c ON wh.content_id = c.content_id
WHERE p.profile_ID = %s
ORDER BY wh.watched_timestamp DESC;

    """,(session['profile_id'],))
    
    log = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('watch_log.html', log=log)

@app.route('/profile-count')
def profile_count():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.user_id, a.name, COUNT(p.profile_id) AS total_profiles
        FROM Account a
        LEFT JOIN Profile p ON a.user_id = p.user_id
        GROUP BY a.user_id, a.name
        ORDER BY total_profiles DESC;
    """)

    profiles = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('profile_count.html', profiles=profiles)

@app.route('/inactive-profiles')
def inactive_profiles():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.name
        FROM Account a
        WHERE a.user_id IN (
            SELECT p.user_id
            FROM Profile p
            WHERE p.profile_id NOT IN (
                SELECT wh.profile_id
                FROM Profile_Watch_History wh
            )
        );
    """)

    accounts = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('inactive_profiles.html', accounts=accounts)

@app.route('/watch-history-2profiles')
def watch_history_2profiles():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT a.name AS account_name, p.prof_name AS profile_name, c.title AS content_title, wh.watched_timestamp
        FROM Account a
        JOIN Profile p ON a.user_id = p.user_id
        JOIN Profile_Watch_History wh ON p.profile_id = wh.profile_id
        JOIN Content c ON wh.content_id = c.content_id
        WHERE a.user_id IN (
            SELECT p.user_id
            FROM Profile p
            GROUP BY p.user_id
            HAVING COUNT(p.profile_id) = 2
        )
        ORDER BY a.name, p.prof_name, wh.watched_timestamp;
    """)

    data = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('watch_history_2profiles.html', data=data)


if __name__ == '__main__':
    app.run(debug=True)

