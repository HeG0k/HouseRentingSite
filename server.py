
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
def admin():
    if session.get('role') != 0:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('rent'))

    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Фильтрация пользователей по имени
    search_username = request.args.get('search', '')
    if search_username:
        c.execute('SELECT * FROM users WHERE username LIKE ?', ('%' + search_username + '%',))
    else:
        c.execute('SELECT * FROM users')
    
    users = c.fetchall()

    # Добавление нового объявления
    if request.method == 'POST':
        if request.form.get('action') == 'add':
            # Загружаем изображение
            image = None
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(image_path)
                    image = f"/static/uploads/{filename}"

            price = int(request.form['price'])
            rooms = int(request.form['rooms'])
            district = request.form['district']
            description = request.form['description']
            details = request.form['details']
            listing_type = request.form['type']
            city = request.form['city']
            area = int(request.form['area'])

            c.execute('''
                INSERT INTO listings (image, price, rooms, district, description, details, type, city, area)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (image, price, rooms, district, description, details, listing_type, city, area))
            conn.commit()
            flash('Объявление добавлено.', 'listing')

        elif request.form.get('action') == 'delete':
            listing_id = int(request.form['listing_id'])
            c.execute('DELETE FROM listings WHERE id = ?', (listing_id,))
            conn.commit()
            flash('Объявление удалено.', 'listing')

        elif request.form.get('action') == 'create_user':
            username = request.form['username']
            password = request.form['password']
            role = int(request.form['role'])

            c.execute('''
                INSERT INTO users (username, password, role)
                VALUES (?, ?, ?)
            ''', (username, password, role))
            conn.commit()
            flash('Пользователь создан.', 'user')

        elif request.form.get('action') == 'delete_user':
            user_id = int(request.form['user_id'])
            c.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            flash('Пользователь удален.', 'user')
    conn.close()

    return render_template('admin.html', username=session.get('username'), listings=listings, users=users, sort_by=sort_by, order=order)

@app.route('/admin/create_user', methods=['POST'])
@login_required
def create_user():
    if session.get('role') != 0:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('admin'))

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    username = request.form['username']
    password = request.form['password']
    role = int(request.form['role'])

    c.execute('''
        INSERT INTO users (username, password, role)
        VALUES (?, ?, ?)
    ''', (username, password, role))
    conn.commit()
    conn.close()

    flash('Пользователь создан.', 'user')
    return redirect(url_for('admin'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if session.get('role') != 0:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('admin'))

    conn = sqlite3.connect('users.db')
    c = conn.cursor()

    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    flash('Пользователь удален.', 'user')
    return redirect(url_for('admin'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = request.form['password']

    if ' ' in username or ' ' in password:
        flash('Пробелы запрещены в имени пользователя и пароле.', 'danger')
        return render_template('index.html', show_register=True)

    if not (1 <= len(username) <= 32):
        flash('Имя пользователя должно быть от 1 до 32 символов.', 'danger')
        return render_template('index.html', show_register=True)

    if not (8 <= len(password) <= 32):
        flash('Пароль должен быть от 8 до 32 символов.', 'danger')
        return render_template('index.html', show_register=True)

    hashed_password = generate_password_hash(password)

    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, 1)", (username, hashed_password))
        conn.commit()

        # Получаем ID нового пользователя
        c.execute("SELECT id, role FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        # Сохраняем в сессию
        session['user_id'] = user[0]
        session['username'] = username
        session['role'] = user[1]

        return redirect('/rent' if user[1] == 1 else '/admin')

    except sqlite3.IntegrityError:
        flash('Имя пользователя уже существует.', 'danger')
        return redirect(url_for('index'))
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
