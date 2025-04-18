
from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from werkzeug.utils import secure_filename
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    # Создание таблицы пользователей
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role INTEGER NOT NULL DEFAULT 1
        )
    ''')

    # Создание таблицы объявлений с добавленным полем для площади
    c.execute('''
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image TEXT,
            price INTEGER,
            rooms INTEGER,
            district TEXT,
            description TEXT,
            details TEXT,
            type TEXT,
            city TEXT,
            area INTEGER
        )
    ''')

    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, авторизуйтесь', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()

    if user and check_password_hash(user[2], password):
        session['user_id'] = user[0]
        session['username'] = user[1]
        session['role'] = user[3]
        if user[3] == 0:
            return redirect('/admin')
        else:
            return redirect('/rent')
    else:
        flash('Неверные учетные данные.', 'danger')
        return redirect(url_for('index'))
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
