import os
import sqlite3
import cv2
import face_recognition
import numpy as np
from datetime import datetime

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from pywin32_testutil import non_admin_error_codes

try:
    from plyer import vibrator, notification, gps
except ImportError:
    vibrator=None
    notification=None
    gps=None

def init_db():
    conn=sqlite3.connect('dementia_assistant.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS safe_people(
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        name TEXT NOT NULL,
        relation TEXT NOT NULL,
        photo_path TEXT NOT NULL,
        encoding BLOB NOT NULL
    )
    ''')#Safe Man Table

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reminders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        time_str TEXT NOT NULL,
        type TEXT NOT NULL
    )
    ''') #Medications and Routines

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    ''') #Safe Zone/Radius
    conn.commit()
    conn.close()
init_db()