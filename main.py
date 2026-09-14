import os
import sqlite3
from msilib import text

import cv2
import face_recognition
import numpy as np
from datetime import datetime

from kivy.app import App
from kivy.uix import label
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

#--------------------------------------------
#Basic UI
class ModeSelectionScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout=BoxLayout(orientation='vertical', spacing=20, padding=20)
        lbl= Label(text='Dementia Care Assistant', font_size='24sp', bold=True)
        btn_patient=Button(text='Enter Patient Mode', size_hint=(1,0.4), background_color=(0.2, 0.6, 1, 1))
        btn_safeman=Button(text='Enter Safe Man Mode', size_hint=(1,0.4), background_color=(0.2, 0.8, 0.4, 1))
        btn_patient.bind(on_press=self.go_patient)
        btn_safeman.bind(on_press=self.go_safeman)
        self.add_widget(layout)
    def go_patient(self, instance):
        self.manager.current='patient_mode'
    def go_safeman(self, instance):
        self.manager.current='safeman_mode'

#---------------------------------------------
#Patient Mode
class PatientModeScreen(Screen):
    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.layout=BoxLayout(orientation='vertical', spacing=10, padding=10)
        self.img_widget= Image(size_hint=(1,0.6))
        self.info_label= Label(text='Scanning for registered caregivers...', font_size='18sp', size_hint=(1,0.2))

        btn_back= Button(text="Back to Menu", size_hint=(1, 0.1))
        btn_back.bind(on_press=self.go_back)

        self.layout.add_widget(self.img_widget)
        self.layout.add_widget(self.info_label)
        self.layout.add_widget(btn_back)
        self.add_widget(self.layout)

        self.capture = None
        self.known_encodings=[]
        self.known_names=[]
        self.known_relations=[]

    def on_enter(self):
        self.load_known_faces()
        self.capture = cv2.VideoCapture(0)
        Clock.schedule_interval(self.update_frame, 1.0/30.0)
        Clock.schedule_interval(self.check_reminders, 30.0)
    def on_leave(self):
        if self.capture:
            self.capture.release()
        Clock.unschdule(self.update_frame)
        Clock.unschdule(self.check_reminders)
    def load_known_faces(self):
        self.known_encodings.clear()
        self.known_names.clear()
        self.known_relations.clear()

        conn=sqlite3.connect('dementia_assistant.db')
        cursor=conn.cursor()
        cursor.execute("SELECT name, relation, encoding FROM safe_people")
        rows=cursor.fetchall()
        for name, relation, enc_bytes in rows:
            encoding=np.frombuffer(enc_bytes, dtype=np.float64)
            self.known_names.append(name)
            self.known_relations.append(relation)
            self.known_encodings.append(encoding)
        conn.close()