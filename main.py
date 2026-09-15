import os
import sqlite3
from math import remainder
from msilib import text

import cv2
import face_recognition
import numpy as np
from datetime import datetime

from face_recognition import face_locations
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

try:
    from plyer import vibrator, notification, gps, orientation
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

    def update_frame(self, dt):
        ret, frame=self.capture.read()
        if not ret:
            return

        rgb_frame=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        small_frame=cv2.resize(rgb_frame, (0, 0), fx=0.25, fy=0.25)
        face_locations= face_recognition.face_locations(small_frame)
        face_encodings= face_recognition.face_encodings(small_frame, face_locations)

        found_person=False
        for face_encodings in face_encodings:
            matches=face_recognition.compare_faces(self.known_encodings, face_encodings, tolerance=0.5)
            if True in matches:
                match_index=matches.index(True)
                name=self.known_names[match_index]
                relation=self.known_relations[match_index]

                self.info_label.text = f"SAFE PERSON DETECTED!\nName: {name}\nRelation: {relation}"
                found_person=True

                if vibrator:
                    try: vibrator.vibrate(1)
                    except Exception: pass
                break
            if not found_person:
                self.info_label.txt="Scanning surroundings..."

            buffer = cv2.flip(frame, 0).tobytes()
            texture= Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            texture.blit_buffer(buffer, colorfmt='bgr', bufferfmt='ubyte')
            self.img_widget.texture=texture

    def check_reminders(self, dt):
        now_str=datetime.now().strftime("%H:%M")
        conn=sqlite3.connect("dementia_assistant.db")
        cursor=conn.cursor()
        cursor.execute("SELECT title, type FROM reminders WHERE time_str = ?", (now_str,))
        reminders=cursor.fetchall()
        conn.close()

        for title, r_type in reminders:
            if notification:
                notification.notify(
                    title=f"Reminder: {r_type}",
                    message=title,
                    timeout=10
                )
            if vibrator:
                vibrator.vibrate(2)

    def go_back(self, instance):
        self.manager.current='select_mode'

#-----------------------------------------------
#Safe Man mode
class SafeManModeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout=BoxLayout(orientation='vertical', padding=10, spacing=10)
        lbl=Label(text="Safe Man Control Panel", font_size='20sp', bold=True)

        self.input_name= TextInput(hint_text="Full Name", multiline=False)
        self.input_relation= TextInput(hint_text="Relation to Patient (e.g. Son, Doctor)", multiline=False)
        self.input_photo_path= TextInput(hint_text="Attach photo", multiline=False)
        btn_register=Button(text="Register Safe Man", background_color=(0.2,0.7,0.3,1))
        btn_register.bind(on_press=self.register_person)

        self.input_rem_title= TextInput(hint_text="Reminder Title (e.g. Take Aspirin)", multiline=False)
        self.input_rem_time=  TextInput(hint_text="Time (HH:MM 24hr format)", multiline=False)
        btn_add_rem= Button(text="Add Medication/Routine Reminder", background_color=(0.8, 0.5, 0.2, 1))
        btn_add_rem.bind(on_press=self.add_reminder)

        btn_back=Button(text="Back to menu")
        btn_back.bind(on_press=self.go_back)

        layout.add_widget(lbl)
        layout.add_widget(self.input_name)
        layout.add_widget(self.input_relation)
        layout.add_widget(self.input_photo_path)
        layout.add_widget(btn_register)
        layout.add_widget(self.input_rem_title)
        layout.add_widget(self.input_rem_time)
        layout.add_widget(btn_add_rem)
        layout.add_widget(btn_back)

        self.add_widget(layout)

    def register_person(self, instance):
        name=self.input_name.text.strip()
        relation=self.input_relation.text.strip()
        path=self.input_photo_path.text.strip()

        if not (name and relation and os.path.exists(path)):
            print("Invalid inputs or image file missing")
            return
        image=face_recognition.load_image_file(path)
        encoding=face_recognition.face_encodings(image)
        if len(encoding)>0:
            encoding_bytes=encoding[0].tobytes()
            conn = sqlite3.connect("dementia_assistant.db")
            cursor=conn.cursor()
            cursor.execute("INSERT INTO safe_people (name, relation, photo_path, encoding) VALUES (?, ?, ?, ?)",
                           (name, relation, path, encoding_bytes))
            conn.commit()
            conn.close()
            print(f"Successfully registered {name}")
            self.input_name.text=""
            self.input_relation.text=""
            self.input_photo_path.text=""
        else:
                print("No face detected in the provided image")

    def add_reminder(self, instance):
        title=self.input_rem_title.text.strip()
        time_str=self.input_rem_time.text.strip()

        if title and time_str:
            conn=sqlite3.connect("dementia_assistant.db")
            cursor=conn.cursor()
            cursor.execute("INSERT INTO reminders (title, time_str, type) VALUES (?, ?, ?)",
                           (title, time_str, "Routine"))
            conn.commit()
            conn.close()
            print(f"SAdded reminder: {title} at {time_str}")
            self.input_rem_title.text=""
            self.input_rem_time.text=""

    def go_back(self, instance):
        self.manager.current='select_mode'

#-------------------------------------------------
#Main .apk
class DementiaCareApp(App):
    def build(self):
        sm=ScreenManager()
        sm.add_widget(ModeSelectionScreen(name='select_mode'))
        sm.add_widget(PatientModeScreen(name='patient_mode'))
        sm.add_widget(SafeManModeScreen(name='safeman_mode'))
        return sm

if __name__ == '__main__':
    DementiaCareApp().run()