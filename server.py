
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
