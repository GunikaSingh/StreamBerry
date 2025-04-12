from flask import Flask, render_template, request, flash, redirect, url_for
import mysql.connector

app = Flask(__name__)
app.secret_key = "lol"

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="kanu@1234",
        database="StreamBerry")

print("Connected to MySQL!")

app = Flask(__name__)

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/auth', methods=['POST'])
def auth():
    username = request.form['name']
    password = request.form['email']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM account WHERE name = %s AND email = %s", (username, password))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user:
        return redirect(url_for('homepage'))
    else:
        flash("Invalid username or password.")
        return redirect(url_for('login'))


@app.route('/home')
def homepage():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get Movies
    cursor.execute("""
        SELECT content_ID, title, description, url 
        FROM Content 
        WHERE content_type = 'Movie' AND url IS NOT NULL
    """)
    movies = cursor.fetchall()

    # Get TV Series
    cursor.execute("""
        SELECT content_ID, title, description 
        FROM Content 
        WHERE content_type = 'Series'
    """)
    series_raw = cursor.fetchall()

    series_list = []
    for s in series_raw:
        # For each series, fetch episodes
        cursor.execute("""
            SELECT episode_name, episode_num, season_num, url, description
            FROM Episode
            WHERE content_ID = %s
        """, (s['content_ID'],))
        episodes = cursor.fetchall()
        series_list.append({
            'title': s['title'],
            'description': s['description'],
            'episodes': episodes
        })

    cursor.close()
    conn.close()

    return render_template('homepage.html', movies=movies, series_list=series_list)


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


@app.route('/genre-viewers')
def genre_viewers():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    genre_id = 2  
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
    cursor.close()
    conn.close()
    return render_template('genre_viewers_kanu.html', profiles=profiles, genre_id=genre_id)

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


if __name__ == '__main__':
    app.run(debug=True)

if __name__ == '__main__':
    app.run(debug=True)
