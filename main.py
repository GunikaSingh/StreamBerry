from flask import Flask, render_template, request, flash, redirect, url_for
import mysql.connector

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="amrit505",
        database="dbms")

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
        return f"Welcome, {username}!"
    else:
        flash("Invalid username or password.")
        return redirect(url_for('login'))
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

if __name__ == '__main__':
    app.run(debug=True)

if __name__ == '__main__':
    app.run(debug=True)
