from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3  # Для работы с базой данных SQLite
from werkzeug.security import generate_password_hash, check_password_hash  # Для хеширования и проверки паролей
from functools import wraps  # Для создания декораторов
import os  # Для работы с операционной системой (например, пути к файлам)
from werkzeug.utils import secure_filename  # Для безопасной обработки имен файлов

# Инициализация Flask приложения
app = Flask(__name__)
# Секретный ключ для сессий Flask (важно для безопасности)
app.secret_key = 'your_secret_key'
# Разрешенные расширения для загружаемых файлов
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
# Папка для сохранения загруженных файлов
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# ---------- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ----------
# Функции и код, связанные с созданием и настройкой базы данных.

def init_db():
    """
    Инициализирует базу данных, создает таблицы, если они еще не существуют.
    """
    # Устанавливаем соединение с файлом базы данных 'users.db'
    conn = sqlite3.connect('users.db')
    # Создаем курсор для выполнения SQL-запросов
    c = conn.cursor()

    # Включаем поддержку внешних ключей для соединения (важно для SQLite для обеспечения целостности данных)
    c.execute("PRAGMA foreign_keys = ON")

    # Создание таблицы 'users' для хранения информации о пользователях
    # Поля: id (первичный ключ), username (уникальный), password (хешированный),
    # role (роль пользователя, по умолчанию 1 - обычный пользователь),
    # display_name (отображаемое имя), profile_image (путь к изображению профиля).
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role INTEGER NOT NULL DEFAULT 1,
            display_name TEXT,          -- <--- ДОБАВЛЕНО (Отображаемое имя пользователя)
            profile_image TEXT          -- <--- ДОБАВЛЕНО (Путь к аватару пользователя)
        )
    ''')

    # Создание таблицы 'listings' для хранения информации об объявлениях
    # Поля: id (первичный ключ), image (путь к изображению), price (цена),
    # rooms (количество комнат), description (описание), details (детали),
    # deal_type (тип сделки: аренда/продажа), housing_type (тип жилья: дом/квартира/комната),
    # city (город), area (площадь), phone (телефон), user_id (внешний ключ к таблице users).
    # При удалении пользователя, объявления этого пользователя получают user_id = NULL.
    c.execute('''
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image TEXT,
            price INTEGER,
            rooms INTEGER,
            description TEXT,
            details TEXT,
            deal_type TEXT,      -- rent/sale (Тип сделки: аренда/продажа)
            housing_type TEXT,   -- дом/квартира/комната (Тип жилья)
            city TEXT,
            area INTEGER,
            phone TEXT,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
    ''')

    # Создание таблицы 'favorites' для хранения избранных объявлений пользователей
    # Поля: id (первичный ключ), user_id (внешний ключ к таблице users),
    # listing_id (внешний ключ к таблице listings).
    # Пара (user_id, listing_id) должна быть уникальной.
    # При удалении пользователя или объявления, соответствующие записи в избранном также удаляются (ON DELETE CASCADE).
    c.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            listing_id INTEGER NOT NULL,
            UNIQUE(user_id, listing_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE
        )
    ''')
    
    # Сохраняем изменения в базе данных
    conn.commit()
    # Закрываем соединение с базой данных
    conn.close()


# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
# Общие утилиты и декораторы, используемые в приложении.

@app.context_processor
def inject_user():
    """
    Внедряет 'user_id' в контекст шаблонов Jinja2.
    Это позволяет проверять, залогинен ли пользователь, прямо в шаблонах.
    """
    return dict(user_id=session.get('user_id'))

def login_required(f):
    """
    Декоратор для ограничения доступа к маршрутам только для аутентифицированных пользователей.
    Если пользователь не вошел в систему, он перенаправляется на страницу входа.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Пожалуйста, войдите в аккаунт.')  # Сообщение для пользователя
            return redirect(url_for('login'))  # Перенаправление на страницу входа
        return f(*args, **kwargs)  # Выполнение исходной функции, если пользователь аутентифицирован
    return decorated

def allowed_file(filename):
    """
    Проверяет, имеет ли загружаемый файл разрешенное расширение.
    """
    # Проверяем наличие точки в имени файла и соответствие расширения списку ALLOWED_EXTENSIONS
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# ---------- ОБЪЯВЛЕНИЯ ----------
# Маршруты и функции, связанные с отображением, добавлением и управлением объявлениями.

@app.route('/rent', methods=['GET', 'POST'])
def rent():
    """
    Отображает страницу с объявлениями об аренде.
    Позволяет фильтровать объявления по цене, количеству комнат, городу и типу жилья.
    """
    # Устанавливаем соединение с базой данных
    conn = sqlite3.connect('users.db')
    # Устанавливаем row_factory для доступа к данным по именам колонок
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Базовый SQL-запрос для выборки объявлений об аренде
    query = "SELECT * FROM listings WHERE deal_type = 'rent'"
    filters = []  # Список для хранения условий фильтрации
    values = []   # Список для хранения значений для SQL-запроса

    # Инициализация переменных для сохранения значений фильтров (чтобы передать их обратно в шаблон)
    housing_type = ''
    rooms = ''

    # Если запрос методом POST (т.е. пользователь применил фильтры)
    if request.method == 'POST':
        # Получаем значения фильтров из формы
        min_price = request.form.get('min_price')
        max_price = request.form.get('max_price')
        rooms = request.form.get('rooms')
        city = request.form.get('city')
        housing_type = request.form.get('housing_type')

        # Добавляем условия в запрос в зависимости от заполненных полей фильтра
        if min_price:
            filters.append("price >= ?")
            values.append(int(min_price))
        if max_price:
            filters.append("price <= ?")
            values.append(int(max_price))
        if housing_type:
            filters.append("housing_type = ?")
            values.append(housing_type)
            # Если выбран тип жилья "комната", то фильтр по количеству комнат игнорируется
            if housing_type == 'комната':
                rooms = '' # Сбрасываем значение rooms, чтобы оно не учитывалось
        if rooms and rooms.isdigit(): # Проверяем, что rooms указано и является числом
            filters.append("rooms = ?")
            values.append(int(rooms))
        if city:
            filters.append("city = ?")
            values.append(city)
             # Если выбрана "комната" — фильтруем только по housing_type, rooms игнорируем
        if housing_type != 'комната' and rooms: # Если не комната и указано количество комнат
            filters.append("rooms = ?")
            values.append(int(rooms))


    # Если есть активные фильтры, добавляем их к SQL-запросу
    if filters:
        query += " AND " + " AND ".join(filters)

    # Выполняем SQL-запрос с параметрами
    c.execute(query, values)
    listings = c.fetchall()  # Получаем все отфильтрованные объявления
    conn.close()  # Закрываем соединение с базой данных

    # Отображаем шаблон 'rent.html', передавая список объявлений и текущие значения фильтров
    return render_template('rent.html', listings=listings, housing_type=housing_type, rooms=rooms)


@app.route('/sale', methods=['GET', 'POST'])
def sale():
    """
    Отображает страницу с объявлениями о продаже.
    Позволяет фильтровать объявления по цене, количеству комнат и городу.
    """
    # Аналогично функции rent(), но для объявлений о продаже
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Базовый SQL-запрос для выборки объявлений о продаже
    query = "SELECT * FROM listings WHERE deal_type  = 'sale'"
    filters = []
    values = []

    if request.method == 'POST':
        min_price = request.form.get('min_price')
        max_price = request.form.get('max_price')
        rooms = request.form.get('rooms')
        city = request.form.get('city')

        if min_price:
            filters.append("price >= ?")
            values.append(int(min_price))
        if max_price:
            filters.append("price <= ?")
            values.append(int(max_price))
        if rooms:
            filters.append("rooms = ?")
            values.append(int(rooms))
        if city:
            filters.append("city = ?")
            values.append(city)
        
    if filters:
        query += " AND " + " AND ".join(filters)

    c.execute(query, values)
    listings = c.fetchall()
    conn.close()

    return render_template('sale.html', listings=listings)

@app.route('/add', methods=['GET', 'POST'])
@login_required  # Доступ только для аутентифицированных пользователей
def add_listing():
    """
    Обрабатывает добавление нового объявления.
    При GET-запросе отображает форму добавления.
    При POST-запросе сохраняет данные нового объявления в базу данных.
    """
    if request.method == 'POST':
        # Обработка загрузки изображения
        image = None
        if 'image' in request.files:
            file = request.files['image']
            # Если файл выбран и имеет разрешенное расширение
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)  # Безопасное имя файла
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)  # Сохранение файла
                image = f"/static/uploads/{filename}"  # Путь к файлу для сохранения в БД

        # Получение данных из формы
        price = int(request.form['price'])
        housing_type = request.form.get('housing_type', '') # Тип жилья

        # Если тип жилья "комната", количество комнат устанавливается в 1
        if housing_type == 'комната':
            rooms = 1
        else:
            rooms_raw = request.form.get('rooms')
            try:
                # Преобразование количества комнат в целое число, если оно указано
                rooms = int(rooms_raw) if rooms_raw else 0
            except ValueError:
                rooms = 0 # Если не удалось преобразовать, считаем 0 комнат
        
        description = request.form['description']
        details = request.form['details']
        housing_type_form = request.form['housing_type'] # Повторное получение, возможно для другой логики (переменная housing_type уже есть)
        deal_type = request.form['deal_type']
        city = request.form['city']
        area = int(request.form['area'])
        phone = request.form['phone']
        user_id = session.get('user_id') # ID текущего пользователя из сессии

        # Получение координат с карты (если они переданы)
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')

        # Попытка преобразовать координаты в float
        try:
            latitude = float(latitude) if latitude else None
            longitude = float(longitude) if longitude else None
        except ValueError:
            latitude = None
            longitude = None

        # Повторная логика установки количества комнат для "комнаты"
        if housing_type_form == 'комната': # Используется housing_type_form
            rooms = 1
        else:
            rooms = int(request.form['rooms']) # Прямое преобразование из формы

        # Сохранение объявления в базу данных
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO listings 
            (image, price, rooms, description, details, deal_type, housing_type, city, area, phone, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (image, price, rooms, description, details, deal_type, housing_type_form, city, area, phone, user_id))
        conn.commit()
        conn.close()

        flash("Объявление добавлено!")  # Сообщение об успехе
        return redirect(url_for('profile'))  # Перенаправление на страницу профиля

    # Если метод GET, отображаем форму добавления объявления
    return render_template('add_listing.html')


@app.route('/listing/<int:listing_id>')
def listing_detail(listing_id):
    """
    Отображает детальную информацию о конкретном объявлении.
    Включает информацию о продавце (display_name, profile_image).
    """
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # SQL-запрос для получения данных объявления и информации о пользователе, его разместившем
    c.execute('''
        SELECT l.*, u.display_name, u.profile_image
        FROM listings l
        LEFT JOIN users u ON l.user_id = u.id
        WHERE l.id = ?
    ''', (listing_id,))
    listing = c.fetchone()  # Получаем одно объявление
    conn.close()

    # Если объявление не найдено, показываем сообщение и перенаправляем
    if not listing:
        flash("Объявление не найдено.", "danger")
        return redirect(url_for('rent'))

    # Отображаем шаблон с деталями объявления
    return render_template('listing_detail.html', listing=listing)


# ---------- ИЗБРАННОЕ ----------
# Маршруты и функции для управления списком избранных объявлений пользователя.

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
@app.route('/favorites')
@login_required # Доступ только для аутентифицированных пользователей
def favorites():
    """
    Отображает страницу с избранными объявлениями текущего пользователя.
    """
    user_id = session['user_id']  # ID текущего пользователя
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # SQL-запрос для получения всех объявлений, добавленных пользователем в избранное
    c.execute('''
        SELECT l.*
        FROM listings l
        JOIN favorites f ON l.id = f.listing_id
        WHERE f.user_id = ?
    ''', (user_id,))
    favorites = c.fetchall()  # Получаем список избранных объявлений
    conn.close()
    return render_template('favorites.html', favorites=favorites)

@app.route('/add_favorite/<int:item_id>', methods=['POST'])
@login_required # Доступ только для аутентифицированных пользователей
def add_favorite(item_id):
    """
    Добавляет объявление в список избранного для текущего пользователя.
    """
    user_id = session['user_id']
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        # Пытаемся добавить запись в таблицу favorites.
        c.execute('INSERT OR IGNORE INTO favorites (user_id, listing_id) VALUES (?, ?)', (user_id, item_id))
        conn.commit()
        flash('Добавлено в избранное!')
    except sqlite3.Error: # Более общая обработка ошибок SQLite
        flash('Ошибка добавления в избранное.')
    finally:
        conn.close()
    # Перенаправляем пользователя на предыдущую страницу или на страницу аренды
    return redirect(request.referrer or url_for('rent'))

@app.route('/remove_favorite/<int:item_id>', methods=['POST'])
@login_required # Доступ только для аутентифицированных пользователей
def remove_favorite(item_id):
    """
    Удаляет объявление из списка избранного для текущего пользователя.
    """
    user_id = session['user_id']
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        # Удаляем запись из таблицы favorites
        c.execute('DELETE FROM favorites WHERE user_id = ? AND listing_id = ?', (user_id, item_id))
        conn.commit()
        flash('Удалено из избранного.', 'success')
    except sqlite3.Error: # Более общая обработка ошибок SQLite
        flash('Ошибка удаления.', 'danger')
    finally:
        conn.close()
    # Перенаправляем пользователя на предыдущую страницу или на страницу избранного
    return redirect(request.referrer or url_for('favorites'))


# ---------- АДМИНКА ----------
# Маршруты и функции для административной панели.

@app.route('/admin')
@login_required # Требуется вход в систему
def admin_index():
    """
    Главная страница административной панели.
    Перенаправляет на управление пользователями, если пользователь - админ.
    """
    # Проверка, является ли пользователь администратором (role == 0)
    if session.get('role') != 0:
        flash('Доступ запрещен.', 'danger') # Сообщение об ошибке доступа
        return redirect(url_for('rent')) # Перенаправление на страницу аренды
    return redirect(url_for('admin_users')) # Перенаправление на страницу управления пользователями

@app.route('/admin/users', methods=['GET'])
@login_required # Требуется вход в систему
def admin_users():
    """
    Страница управления пользователями в админ-панели.
    Позволяет просматривать и искать пользователей.
    """
    # Проверка роли администратора
    if session.get('role') != 0:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('rent'))

    # Получение параметра поиска из GET-запроса
    search_username = request.args.get('search', '')
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Если есть поисковый запрос, фильтруем пользователей по имени
    if search_username:
        c.execute('SELECT * FROM users WHERE username LIKE ?', ('%' + search_username + '%',))
    else:
        # Иначе получаем всех пользователей
        c.execute('SELECT * FROM users')
    users = c.fetchall()
    conn.close()

    # Отображаем шаблон с пользователями
    return render_template('admin_users.html', username=session.get('username'), users=users, title="Пользователи")

@app.route('/admin/users/create', methods=['POST'])
@login_required # Требуется вход в систему
def create_user():
    """
    Создание нового пользователя администратором.
    """
    # Проверка роли администратора
    if session.get('role') != 0:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('rent'))

    # Получение данных нового пользователя из формы
    username = request.form['username']
    password = request.form['password']
    role = int(request.form['role'])

    # Хеширование пароля
    hashed_password = generate_password_hash(password)

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # Вставка нового пользователя в базу данных
    c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, hashed_password, role))
    conn.commit()
    conn.close()

    flash('Пользователь создан.', 'user') # Сообщение об успехе
    return redirect(url_for('admin_users')) # Перенаправление на страницу управления пользователями

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required # Требуется вход в систему
def delete_user(user_id):
    """
    Удаление пользователя администратором.
    """
    # Проверка роли администратора
    if session.get('role') != 0:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('rent'))

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # Удаление пользователя из базы данных по ID
    c.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()

    flash('Пользователь удален.', 'user') # Сообщение об успехе
    return redirect(url_for('admin_users')) # Перенаправление на страницу управления пользователями

@app.route('/admin/listings', methods=['GET'])
@login_required # Требуется вход в систему
def admin_listings():
    """
    Страница управления объявлениями в админ-панели.
    Позволяет фильтровать и сортировать объявления.
    """
    # Проверка роли администратора
    if session.get('role') != 0:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('rent'))

    # Получение параметров фильтрации и сортировки из GET-запроса
    city = request.args.get('city', '').strip()
    rooms = request.args.get('rooms', '').strip()
    housing_type = request.args.get('housing_type', '').strip()
    deal_type = request.args.get('deal_type', '').strip()  # новый параметр для типа сделки

    # Параметры сортировки
    sort_by = request.args.get('sort_by', 'id') # Поле для сортировки
    order = request.args.get('order', 'asc') # Порядок сортировки (asc/desc)
    # Валидация параметров сортировки
    if sort_by not in ['id', 'price', 'rooms', 'housing_type']:
        sort_by = 'id'
    if order not in ['asc', 'desc']:
        order = 'asc'

    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Базовый SQL-запрос для выборки объявлений с информацией о пользователе
    query = '''
        SELECT listings.*, users.username 
        FROM listings 
        LEFT JOIN users ON listings.user_id = users.id
        WHERE 1=1
    ''' 
    params = [] # Список параметров для SQL-запроса

    # Добавление условий фильтрации в запрос
    if city:
        query += ' AND city LIKE ?'
        params.append(f'%{city}%')
    if rooms and rooms.isdigit():
        query += ' AND rooms = ?'
        params.append(int(rooms))
    if housing_type:
        query += ' AND housing_type  = ?'
        params.append(housing_type)
    if deal_type:
        query += ' AND deal_type = ?'
        params.append(deal_type)

    # Добавление сортировки в запрос
    query += f' ORDER BY {sort_by} {order.upper()}'

    c.execute(query, params)
    listings = c.fetchall()
    conn.close()

    # Отображение шаблона с отфильтрованными и отсортированными объявлениями
    return render_template('admin_listings.html', username=session.get('username'),
                           listings=listings, sort_by=sort_by, order=order,
                           city=city, rooms=rooms, housing_type=housing_type, deal_type=deal_type)


@app.route('/admin/listings/delete', methods=['POST'])
@login_required # Требуется вход в систему
def delete_listing():
    """
    Удаление объявления администратором.
    """
    # Проверка роли администратора
    if session.get('role') != 0:
        flash('Доступ запрещен.', 'danger')
        return redirect(url_for('rent'))

    # Получение ID объявления для удаления из формы
    listing_id = int(request.form['listing_id'])

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # Удаление объявления из базы данных по ID
    c.execute('DELETE FROM listings WHERE id = ?', (listing_id,))
    conn.commit()
    conn.close()

    flash('Объявление удалено.', 'listing') # Сообщение об успехе
    return redirect(url_for('admin_listings')) # Перенаправление на страницу управления объявлениями


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

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из аккаунта.', 'success')
    return redirect(url_for('index'))

@app.route('/rent', methods=['GET', 'POST'])
def rent():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = "SELECT * FROM listings WHERE 1"
    filters = []
    values = []

    if request.method == 'POST':
        min_price = request.form.get('min_price')
        max_price = request.form.get('max_price')
        rooms = request.form.get('rooms')
        district = request.form.get('district')
        type_of_property = request.form.get('type')

        if min_price:
            filters.append("price >= ?")
            values.append(int(min_price))
        if max_price:
            filters.append("price <= ?")
            values.append(int(max_price))
        if rooms:
            filters.append("rooms = ?")
            values.append(int(rooms))
        if district:
            filters.append("district = ?")
            values.append(district)
        if type_of_property:
            filters.append("type = ?")
            values.append(type_of_property)

    city = request.args.get('city')
    if city:
        filters.append("city = ?")
        values.append(city)

    if filters:
        query += " AND " + " AND ".join(filters)

    c.execute(query, values)
    listings = c.fetchall()
    conn.close()

    return render_template('rent.html', listings=listings)
@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', username=session.get('username'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
