from kivy.uix.screenmanager import Screen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton
from kivymd.uix.relativelayout import MDRelativeLayout
from kivymd.app import MDApp
from kivymd.uix.menu import MDDropdownMenu
from kivymd.uix.label import MDLabel
from kivymd.uix.list import OneLineIconListItem
from kivymd.icon_definitions import md_icons
from kivy.metrics import dp
from kivy.properties import StringProperty, NumericProperty, Property

import os
from functools import partial

from session import Session
from constants import PROJECT_DIR, USERS_PATH
from database import retrieve_passwords, retrieve_password_by_title, save_password, delete_password_by_title, update_password_by_title
from utils import logout, get_keyring, decode_b64, get_settings, update_settings
from threads import ThreadedFunctionRunner
from encryption import Security

class CustomOneLineIconListItem(OneLineIconListItem):
    icon = StringProperty()

class IconSelector(MDRelativeLayout):
    def set_list_md_icons(self, text="", search=False):
        '''Builds a list of icons for the screen MDIcons.'''

        def add_icon_item(name_icon):
            self.ids.rv.data.append(
                {
                    "viewclass": "CustomOneLineIconListItem",
                    "icon": name_icon,
                    "text": name_icon,
                    "callback": lambda x: x,
                }
            )

        self.ids.rv.data = []
        for name_icon in md_icons.keys():
            if search:
                if text in name_icon:
                    add_icon_item(name_icon)
            else:
                add_icon_item(name_icon)

class PasswordButton(MDRelativeLayout):
    text = StringProperty()
    icon = StringProperty()
    height_p = NumericProperty(60)
    callback = Property(None)

class FilterButton(MDRelativeLayout):
    text = StringProperty()
    icon = StringProperty()

class PasswordTextFieldM(MDRelativeLayout):
    text = StringProperty()
    hint_text = StringProperty()

class MainScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

        self.title = ""
        self.value = 5
        self.segment_type = 'view'

        self.icon_main = "key-variant"
        self.icon_disabled = False
        self.icon_disabled_icon = 'cancel'
        self.icon_disabled_icon_icon = ''
        self.icon_list = [
            'key-variant',
            'home',
            'briefcase',
            'school'
        ]

        self.segment_buttons = {"view": self.ids['view_button'], "add": self.ids['add_button']}

        self.app = MDApp.get_running_app()
        
        filter_list = os.listdir(f'{USERS_PATH}\\{Session.USER_UUID}\\data')

        first_filter = (filter_list[0].split(".")[0]).capitalize()

        if not get_settings('session', 'filter'):
            update_settings('session', 'filter', first_filter)
            Session.FILTER = first_filter
        else:
            Session.FILTER = get_settings('session', 'filter')

        self.menu_items_filter = [
            {
                "text": (i.split(".")[0]).capitalize(),
                "viewclass": "OneLineListItem",
                "height": dp(55),
                "on_release": lambda x=i: self.menu_filter_callback(x),
            } for i in filter_list
        ]

        self.menu_filter = MDDropdownMenu(
            caller=self.ids['filter_container'].ids['filter_button'],
            items=self.menu_items_filter,
            position="bottom",
            width_mult=4,
        )

        self.ids['filter_container'].text = Session.FILTER.capitalize()
    
    def _handle_keyboard(self, instance, key, *args):
        if self.manager.current == 'main':
            if key == 275 or key == 273:
                self.cycle_icon('left')
            if key == 276 or key == 274:
                self.cycle_icon('right')
    
    def on_pre_enter(self, *args):
        if not Session.USER_UUID:
            self.goto_screen('login', 'down')
        if get_settings('session', 'filter') == "":
            filter_list = os.listdir(f'{USERS_PATH}\\{Session.USER_UUID}\\data')
            first_filter = (filter_list[0].split(".")[0]).capitalize()
            update_settings('session', 'filter', first_filter)
        Session.FILTER = get_settings('session', 'filter')
        print(f'Filter: {Session.FILTER}')
        self.ids['account_button_long'].text = Session.NAME
        self.clear_text(True)
        self.update_slider(self.value)
        return super().on_pre_enter(*args)

    def on_enter(self, *args):
        self.app.theme_cls.theme_style = get_settings('color', 'theme')
        self.app.theme_cls.primary_palette = get_settings('color', 'primary')
        self.app.theme_cls.primary_hue = get_settings('color', 'hue')
        self.change_type('View')
        self.load_passwords()
        self.update_filter_menu()
        return super().on_enter(*args)

    def on_leave(self, *args):
        scroll_container = self.ids['scroll_container']
        scroll_container_children = self.ids['scroll_container'].children
        for child in scroll_container_children:
            scroll_container.remove_widget(child)
        return super().on_leave(*args)
    
    def open_menu(self):
        self.menu.open()

    def menu_filter_callback(self, text_item):
        self.menu_filter.dismiss()
        self.update_filter_menu()
        self.ids['filter_container'].ids['filter_button'].text = (text_item.split(".")[0]).capitalize()
        Session.FILTER = (text_item.split(".")[0]).lower()
        update_settings('session', 'filter', Session.FILTER)
        self.change_type('View')
        self.update_slider(5)
        self.update_slider_text(5)
        self.load_passwords()
    
    def update_filter_menu(self):
        filter_list = os.listdir(f'{USERS_PATH}\\{Session.USER_UUID}\\data')

        self.ids['filter_container'].ids['filter_button'].text = (filter_list[0].split(".")[0]).capitalize()

        self.menu_items_filter = [
            {
                "text": (i.split(".")[0]).capitalize(),
                "viewclass": "OneLineListItem",
                "height": dp(55),
                "on_release": lambda x=i: self.menu_filter_callback(x),
            } for i in filter_list
        ]

        self.menu_filter.items = self.menu_items_filter
    
    def start_remove_filter(self):
        self.filter_list_len = len(os.listdir(f'{USERS_PATH}\\{Session.USER_UUID}\\data'))
        
        if self.filter_list_len > 1:
            self.show_dialog("Are you sure?", "Are you sure you want to delete this filter?\nThis action will remove any saved passwords in the filter.", [["Cancel", self.close_dialog], ["Delete", self.remove_filter]], False)
        else:
            print("One password is required!")
            return
    
    def remove_filter(self, *args):
        self.close_dialog()
        try:
            os.remove(f'{USERS_PATH}\\{Session.USER_UUID}\\data\\{Session.FILTER}.db')
            filter_list = os.listdir(f'{USERS_PATH}\\{Session.USER_UUID}\\data')
            Session.FILTER = (filter_list[0].split(".")[0]).capitalize()
            update_settings('session', 'filter', Session.FILTER)
        except:
            print(f"Failed to delete filter! Try again! Filter: {Session.FILTER}.db")
        self.update_filter_menu()
        self.load_passwords()
    
    def show_dialog(self, title, text, buttons, dismiss_button):
        all_buttons = []
        if dismiss_button:
            dismiss_btn = MDFlatButton(text="Close", on_release=self.close_dialog)
            all_buttons.append(dismiss_btn)
        for button in buttons:
            new_button = MDFlatButton(text=button[0], on_release=button[1])
            all_buttons.append(new_button)
        self.dialog = MDDialog(title=title, text=text, size_hint=(0.7, None), size_hint_max_x=550, height=150, buttons=all_buttons)
        self.dialog.open()
    
    def close_dialog(self, *args):
        self.dialog.dismiss()
    
    def update_text(self, title, username, password):
        self.title = str(title)
        self.ids['title_text'].text = str(title)
        self.ids['username_text'].text = str(username)
        self.ids['password_text'].ids['text_field'].text = str(password)
    
    def clear_text(self, clear_title):
        if clear_title:
            self.title = ""
        self.ids['title_text'].text = ""
        self.ids['username_text'].text = ""
        self.ids['password_text'].ids['text_field'].text = ""
    
    def update_slider(self, value):
        slider = self.ids['enc_lvl_slider']
        slider_range = slider.range

        if not slider_range[0] <= value <= slider_range[1]:
            return

        slider.value = value
        update_settings('encryption', 'level', value)
        self.update_slider_text(value)

    def update_slider_text(self, value):
        slider_text = self.ids['slider_text']

        if value <= 3:
            slider_text.text = f'Level: {value} (Bad)'
        elif value <= 7:
            slider_text.text = f'Level: {value} (Good)'
        else:
            slider_text.text = f'Level: {value} (Super)'
    
    def update_button_premissions(self, save_disable, delete_disable):
        self.ids['save_button'].disabled = save_disable
        self.ids['delete_button'].disabled = delete_disable
    
    def cycle_icon(self, dir):
        if self.icon_disabled:
            return
        button = self.ids['icon_select']
        total_len = len(self.icon_list)-1
        index = self.icon_list.index(self.icon_main)
        if dir == 'right':
            if index < 0:
                index = total_len+1
            self.icon_main = self.icon_list[index-1]
            button.icon = self.icon_main
            return

        if dir == 'left':
            if index == total_len:
                index = -1
            self.icon_main = self.icon_list[index+1]
            button.icon = self.icon_main
            return

    def disable_icon(self):
        button = self.ids['icon_select']
        if self.icon_disabled:
            button.icon = self.icon_list[self.icon_list.index(self.icon_main)]
            self.icon_disabled = False
        else:
            button.icon = self.icon_disabled_icon
            self.icon_disabled = True
    
    def open_icon_select(self, caller):
        pass
    
    def change_type(self, button_text):
        self.clear_text(False)
        self.segment_type = button_text.lower()
        on_color = self.app.theme_cls.primary_color
        off_color = self.app.theme_cls.bg_normal

        active_button = self.segment_buttons[button_text.lower()]
        active_button.md_bg_color = on_color
        active_button.text_color = off_color

        for _button in self.segment_buttons:
            if _button == button_text.lower():
                continue
            _button = self.segment_buttons[_button]
            _button.md_bg_color = off_color
            _button.text_color = on_color

        if button_text == 'View':
            self.update_button_premissions(True, True)
            self.ids['save_button'].text = "Save"
        elif button_text == 'Add':
            self.update_button_premissions(False, True)
            self.ids['save_button'].text = "Add"


    def check_empty_pass(self):
        self.container = self.ids['scroll_container']
        children = self.container.children

        if children != []:
            return
        
        text = MDLabel(
            size_hint=(1, 1),
            text="You have not saved any passwords yet!",
            font_style='Body1',
            halign='center',
            valign='center',
            theme_text_color='Hint'
        )

        self.container.add_widget(text)

        self.update_button_premissions(True, True)
    
    def load_passwords(self):
        self.clear_text(True)
        self.update_slider(5)
        self.update_slider_text(5)
        passwords = retrieve_passwords((Session.FILTER).lower(), Session.USER_UUID)
        self.container = self.ids['scroll_container']
        self.container.clear_widgets()
        for pw in passwords:
            button = PasswordButton(
                text=pw[0],
                icon=pw[3],
                callback=partial(self.show_password, pw[0])
            )
            self.container.add_widget(button)
        
        self.check_empty_pass()
    
    def show_password(self, title):
        self.title = title
        if self.segment_type == 'add':
            self.change_type('View')
        info = retrieve_password_by_title(Session.FILTER, Session.USER_UUID, self.title)[0]

        title = info[0]
        username = info[1]
        password = info[2]

        b64password = get_keyring(f'KeyKeeper - {Session.USER_UUID}', Session.USER_UUID)
        decode_pw = decode_b64(b64password, 'ascii')
        lvl = info[4]

        def decrypt(text, password):
            dec = Security(lvl)

            try:
                decrypted_pw = dec.decrypt(text, password)
                return decrypted_pw
            except:
                return ""
        
        keep_args = [title, lvl]
        runner_args = [('username', username, decode_pw), ('password', password, decode_pw)]

        runner = ThreadedFunctionRunner(decrypt, keep_args, runner_args, self.view_callback)
        runner.start()
    
    def delete_password(self):
        delete_password_by_title(Session.FILTER, Session.USER_UUID, self.title)
        self.clear_text(True)
        self.load_passwords()
    
    def check_save_type(self):
        if self.segment_type == 'add' and self.ids['title_text'].text == "" and self.ids['username_text'].text == "" and self.ids['password_text'].ids['text_field'].text == "":
            print("Not all fields are filled")
            return
        if self.segment_type == 'view':
            if not self.title:
                print("Title not found!")
                print(f"Title: {self.title}")
                return
            
            info = retrieve_password_by_title(Session.FILTER, Session.USER_UUID, self.title)[0]

            title = info[0]
            username = info[1]
            password = info[2]

            new_title = self.ids['title_text'].text
            new_username = self.ids['username_text'].text
            new_password = self.ids['password_text'].ids['text_field'].text
            new_lvl = int(self.ids['enc_lvl_slider'].value)

            b64password = get_keyring(f'KeyKeeper - {Session.USER_UUID}', Session.USER_UUID)
            decode_pw = decode_b64(b64password, 'ascii')
            lvl = info[4]

            def encrypt(text, password):
                enc = Security(new_lvl)

                try:
                    encrypted_pw = enc.encrypt(text, password)
                    return encrypted_pw
                except:
                    return ""
            
            def update_with_new_info(result):
                keep_result = result[0]
                result.pop(0)
                update_password_by_title(Session.FILTER, Session.USER_UUID, title, keep_result[0], result[0]['username'], result[0]['password'], "", new_lvl)
                self.update_button_premissions(True, True)
                self.load_passwords()
            
            keep_args = [new_title, new_lvl]
            runner_args = [('username', new_username, decode_pw), ('password', new_password, decode_pw)]

            runner = ThreadedFunctionRunner(encrypt, keep_args, runner_args, update_with_new_info)
            runner.start()

        elif self.segment_type == 'add':
            title = self.ids['title_text'].text
            username = self.ids['username_text'].text
            password = self.ids['password_text'].ids['text_field'].text

            if title == "" or username == "" or password == "":
                print("Some inputs are empty!")
                return

            if_exists_password = retrieve_password_by_title(Session.FILTER, Session.USER_UUID, title)

            if if_exists_password != None:
                print("That name is already taken! Please choose a different name.")
                return False

            b64password = get_keyring(f'KeyKeeper - {Session.USER_UUID}', Session.USER_UUID)
            decode_pw = decode_b64(b64password, 'ascii')
            lvl = get_settings('encryption', 'level')

            def encrypt(text, password):
                enc = Security(lvl)

                try:
                    encrypted_pw = enc.encrypt(text, password)
                    return encrypted_pw
                except:
                    return ""

            keep_args = [title, lvl]
            runner_args = [('username', username, decode_pw), ('password', password, decode_pw)]

            runner = ThreadedFunctionRunner(encrypt, keep_args, runner_args, self.add_callback)
            runner.start()
                
        else:
            print("No segment type detected!")

    def view_callback(self, result):
        self.load_passwords()
        self.update_text(result[0][0], result[1]['username'], result[1]['password'])
        self.update_slider(int(result[0][1]))
        self.update_slider_text(int(result[0][1]))
        self.update_button_premissions(False, False)

    def add_callback(self, result):
        keep_result = result[0]
        result.pop(0)
        save_password(Session.FILTER, Session.USER_UUID, keep_result[0], result[0]['username'], result[0]['password'], "", keep_result[1])
        self.load_passwords()
    
    def new_password(self, *args):
        self.goto_screen('newpassword', 'right')
    
    def new_filter(self, *args):
        self.goto_screen('newfilter', 'right')
    
    def settings(self, *args):
        self.goto_screen('settings', 'up')

    def log_out(self, *args):
        logout()
        self.goto_screen('login', 'down')

    def goto_screen(self, screen, side='left'):
        self.manager.set_current(screen, side)

    pass
