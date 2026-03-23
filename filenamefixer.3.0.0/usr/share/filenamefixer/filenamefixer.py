#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys

# Linux/Debian tabanlı sistemler için X11 zorlaması
os.environ['QT_QPA_PLATFORM'] = 'xcb' 

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QLabel, QFileDialog, QHBoxLayout, QMessageBox, QCheckBox,
    QLineEdit, QFormLayout, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIntValidator, QIcon

# --- Sabitler ve Fonksiyonlar ---

INVALID_WINDOWS_CHARS = r'[<>:"/\\|?*]'
VERSION = "3.0.0"

def clean_filename(filename):
    """
    Windows yasaklı karakterlerini, emojileri ve sembolleri temizler.
    Türkçe karakterleri (ğ, ü, ş, ı, ö, ç) ve standart ASCII karakterleri korur.
    """
    base, ext = os.path.splitext(filename)
    
    # regex açıklaması:
    # ^ : Belirtilen karakterler dışındakileri seç demektir.
    # a-zA-Z0-9 : Standart Latin harfleri ve rakamlar.
    # . \- _ : Nokta, tire ve alt tire.
    # çÇğĞıİöÖşŞüÜ : Türkçe karakterler.
    # \s : Boşluk karakteri.
    
    pattern = r'[^a-zA-Z0-9.\-_çÇğĞıİöÖşŞüÜ\s]'
    
    # Belirtilenler dışındaki her şeyi (emojiler dahil) boşlukla değiştir
    cleaned_base = re.sub(pattern, '', base)
    
    # Dosya adının sonundaki nokta veya boşlukları temizle (Windows sevmez)
    cleaned_base = cleaned_base.strip(' .')

    if not cleaned_base:
        cleaned_base = "unnamed" 
        
    return f"{cleaned_base}{ext}"

def shorten_filename(filepath, max_len):
    """
    Dosya/klasör adını (uzantı hariç) belirtilen maksimum uzunluğa kadar kısaltır ve
    gerekirse çakışmaları önlemek için sayı ekler.
    """
    directory, name = os.path.split(filepath)
    is_directory = os.path.isdir(filepath)

    if is_directory:
        cleaned_name = clean_filename(name)
        cleaned_base = cleaned_name
        ext = ''
    else:
        cleaned_name = clean_filename(name)
        cleaned_base, ext = os.path.splitext(cleaned_name)

    if len(cleaned_base) <= max_len:
        return cleaned_name 

    shortened_base = cleaned_base[:max_len]
    new_name = f"{shortened_base}{ext}"

    counter = 1
    original_shortened_name = new_name
    while os.path.exists(os.path.join(directory, new_name)) and \
          os.path.join(directory, new_name) != filepath: 
        new_name = f"{shortened_base}_{counter}{ext}"
        counter += 1
        if counter > 999:
            return original_shortened_name 

    return new_name

# --- Arka Plan Tarama İş Parçacığı ---
class FileScannerThread(QThread):
    signal_found_item = pyqtSignal(str, str, str, str)
    signal_scan_finished = pyqtSignal()
    signal_error = pyqtSignal(str)

    def __init__(self, start_path, include_dirs=True, max_len=200):
        super().__init__()
        self.start_path = start_path
        self.include_dirs = include_dirs
        self.max_len = max_len
        self.stop_scan = False

    def run(self):
        try:
            for root, dirs, files in os.walk(self.start_path):
                if self.stop_scan:
                    break

                if self.include_dirs:
                    for dirname in dirs:
                        if self.stop_scan: break
                        full_path = os.path.join(root, dirname)
                        original_name = dirname
                        
                        proposed_new_name = shorten_filename(full_path, self.max_len)

                        if proposed_new_name != original_name or len(original_name) > self.max_len or \
                           re.search(INVALID_WINDOWS_CHARS, original_name) or \
                           original_name.endswith(' ') or original_name.endswith('.'):
                            
                            self.signal_found_item.emit(full_path, original_name, proposed_new_name, 'Dizin')

                for filename in files:
                    if self.stop_scan:
                        break

                    full_path = os.path.join(root, filename)
                    original_name = filename
                    
                    proposed_new_name = shorten_filename(full_path, self.max_len)

                    if proposed_new_name != original_name or len(original_name) > self.max_len or \
                       re.search(INVALID_WINDOWS_CHARS, original_name) or \
                       original_name.endswith(' ') or original_name.endswith('.'):

                        self.signal_found_item.emit(full_path, original_name, proposed_new_name, 'Dosya')

        except Exception as e:
            self.signal_error.emit(f"Tarama sırasında bir hata oluştu: {e}")
        finally:
            self.signal_scan_finished.emit()

    def stop(self):
        self.stop_scan = True

# --- Ana GUI Uygulaması ---
class LongFileNameFixerApp(QWidget):
    def __init__(self):
        super().__init__()
        QApplication.setStyle("Fusion")
        self.selected_directory = ""
        self.anomalous_items = []
        self.scan_thread = None
        self.current_lang = 'tr'
        self.progress_dialog = None
        self.init_ui()
        self.retranslateUi()

    def retranslateUi(self):
        """Tüm arayüz elemanlarının metinlerini günceller."""
        if self.current_lang == 'tr':
            self.setWindowTitle(f"FileName Fixer v{VERSION}")
            self.path_label.setText("Seçilen Dizin: Henüz Seçilmedi")
            self.select_dir_button.setText("Dizin Seç")
            self.max_len_label.setText("Maks. Ad Uzunluğu:")
            self.max_len_input.setPlaceholderText("Maksimum karakter uzunluğu (varsayılan: 200)")
            self.include_dirs_checkbox.setText("Klasör Adlarını da Tara")
            self.scan_button.setText("Tara")
            self.stop_button.setText("Durdur")
            self.fix_button.setText("Seçilenleri Düzelt")
            self.about_button.setText("Hakkında")
            if self.selected_directory:
                if self.scan_thread and self.scan_thread.isRunning():
                    self.path_label.setText(f"Seçilen Dizin: {self.selected_directory} (Taranıyor...)")
                else:
                    self.path_label.setText(f"Seçilen Dizin: {self.selected_directory}")

        elif self.current_lang == 'en':
            self.setWindowTitle(f"FileName Fixer v{VERSION}")
            self.path_label.setText("Selected Directory: Not Selected Yet")
            self.select_dir_button.setText("Select Directory")
            self.max_len_label.setText("Max. Name Length:")
            self.max_len_input.setPlaceholderText("Maximum character length (default: 200)")
            self.include_dirs_checkbox.setText("Scan Folder Names Too")
            self.scan_button.setText("Scan")
            self.stop_button.setText("Stop")
            self.fix_button.setText("Fix Selected")
            self.about_button.setText("About")
            if self.selected_directory:
                if self.scan_thread and self.scan_thread.isRunning():
                    self.path_label.setText(f"Selected Directory: {self.selected_directory} (Scanning...)")
                else:
                    self.path_label.setText(f"Selected Directory: {self.selected_directory}")

        self.stop_button.setStyleSheet("background-color: darkred; color: white;")


    def init_ui(self):
        main_layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.setGeometry(100, 100, 450, 550)
        
        icon_path = "/usr/share/filenamefixer/namefixer.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        dir_selection_layout = QHBoxLayout()
        self.path_label = QLabel()
        self.select_dir_button = QPushButton()
        self.select_dir_button.clicked.connect(self.select_directory)
        dir_selection_layout.addWidget(self.path_label)
        dir_selection_layout.addWidget(self.select_dir_button)
        main_layout.addLayout(dir_selection_layout)

        self.max_len_label = QLabel()
        self.max_len_input = QLineEdit(self)
        self.max_len_input.setText("200")
        self.max_len_input.setValidator(QIntValidator(1, 255, self))
        form_layout.addRow(self.max_len_label, self.max_len_input)

        self.include_dirs_checkbox = QCheckBox()
        self.include_dirs_checkbox.setChecked(True) 
        form_layout.addRow(self.include_dirs_checkbox)

        main_layout.addLayout(form_layout)
        
        scan_stop_layout = QHBoxLayout()
        self.scan_button = QPushButton()
        self.scan_button.clicked.connect(self.start_scan)
        self.scan_button.setEnabled(False)
        
        self.stop_button = QPushButton()
        self.stop_button.clicked.connect(self.stop_scan)
        self.stop_button.setEnabled(False)
        
        scan_stop_layout.addWidget(self.scan_button)
        scan_stop_layout.addWidget(self.stop_button)
        main_layout.addLayout(scan_stop_layout)

        self.result_list_widget = QListWidget()
        main_layout.addWidget(self.result_list_widget)

        self.fix_button = QPushButton()
        self.fix_button.clicked.connect(self.fix_selected_items)
        self.fix_button.setEnabled(False) 
        main_layout.addWidget(self.fix_button)

        self.language_button = QPushButton("Language")
        self.language_button.clicked.connect(self.toggle_language)
        main_layout.addWidget(self.language_button)

        self.about_button = QPushButton()
        self.about_button.clicked.connect(self.show_about_dialog)
        main_layout.addWidget(self.about_button)

        self.setLayout(main_layout)

    def toggle_language(self):
        if self.current_lang == 'tr':
            self.current_lang = 'en'
        else:
            self.current_lang = 'tr'
        self.retranslateUi()

    def get_max_length_from_input(self):
        try:
            max_len_str = self.max_len_input.text()
            if not max_len_str:
                return 200
            max_len = int(max_len_str)
            if not (1 <= max_len <= 255):
                title = "Geçersiz Giriş" if self.current_lang == 'tr' else "Invalid Input"
                text = "Maksimum ad uzunluğu 1 ile 255 arasında bir sayı olmalıdır." if self.current_lang == 'tr' else "Maximum name length must be a number between 1 and 255."
                QMessageBox.warning(self, title, text)
                return -1
            return max_len
        except ValueError:
            title = "Geçersiz Giriş" if self.current_lang == 'tr' else "Invalid Input"
            text = "Maksimum ad uzunluğu için geçerli bir sayı girin." if self.current_lang == 'tr' else "Please enter a valid number for maximum name length."
            QMessageBox.warning(self, title, text)
            return -1

    def select_directory(self):
        title = "Dizin Seç" if self.current_lang == 'tr' else "Select Directory"
        directory = QFileDialog.getExistingDirectory(self, title, os.path.expanduser("~"))
        if directory:
            self.selected_directory = directory
            self.retranslateUi()
            self.scan_button.setEnabled(True)
            self.result_list_widget.clear()
            self.anomalous_items = []
            self.fix_button.setEnabled(False)

    def start_scan(self):
        if not self.selected_directory:
            title = "Uyarı" if self.current_lang == 'tr' else "Warning"
            text = "Lütfen önce bir dizin seçin!" if self.current_lang == 'tr' else "Please select a directory first!"
            QMessageBox.warning(self, title, text)
            return
        
        max_len = self.get_max_length_from_input()
        if max_len == -1:
            return

        self.result_list_widget.clear()
        self.anomalous_items = []
        self.fix_button.setEnabled(False)
        
        self.scan_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.select_dir_button.setEnabled(False)
        self.include_dirs_checkbox.setEnabled(False)
        self.max_len_input.setEnabled(False)
        self.retranslateUi()

        self.progress_dialog = QProgressDialog(
            "Taranıyor..." if self.current_lang == 'tr' else "Scanning...",
            None, 0, 0, self
        )
        self.progress_dialog.setWindowTitle("Tarama Durumu" if self.current_lang == 'tr' else "Scan Status")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.scan_thread = FileScannerThread(self.selected_directory, 
                                            include_dirs=self.include_dirs_checkbox.isChecked(),
                                            max_len=max_len)
        self.scan_thread.signal_found_item.connect(self.add_to_list)
        self.scan_thread.signal_scan_finished.connect(self.scan_finished)
        self.scan_thread.signal_error.connect(self.handle_error)
        self.scan_thread.start()
        
    def stop_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_thread.wait()
            self.scan_finished(interrupted=True)

    def add_to_list(self, full_path, original_name, proposed_new_name, item_type):
        self.anomalous_items.append((full_path, original_name, proposed_new_name, item_type))
        if self.current_lang == 'tr':
            item_type_text = "Dizin" if item_type == 'Dizin' else "Dosya"
            display_text = f"Türü: {item_type_text}\nOrijinal: {original_name}\nÖnerilen: {proposed_new_name}\nTam Yol: {full_path}\n"
        else:
            item_type_text = "Directory" if item_type == 'Dizin' else "File"
            display_text = f"Type: {item_type_text}\nOriginal: {original_name}\nProposed: {proposed_new_name}\nFull Path: {full_path}\n"
        self.result_list_widget.addItem(display_text)
        self.fix_button.setEnabled(True) 

    def scan_finished(self, interrupted=False):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
            
        self.scan_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.select_dir_button.setEnabled(True)
        self.include_dirs_checkbox.setEnabled(True)
        self.max_len_input.setEnabled(True)
        self.retranslateUi()
        
        title = "Bilgi" if self.current_lang == 'tr' else "Info"
        if not interrupted:
            if self.anomalous_items:
                text = f"Tarama tamamlandı. {len(self.anomalous_items)} anormal öğe bulundu." if self.current_lang == 'tr' else f"Scan complete. {len(self.anomalous_items)} anomalous items found."
                QMessageBox.information(self, title, text)
            else:
                text = "Tarama tamamlandı. Anormal dosya/dizin adı bulunamadı." if self.current_lang == 'tr' else "Scan complete. No anomalous file/directory names found."
                QMessageBox.information(self, title, text)
                self.fix_button.setEnabled(False)
        else:
            text = "Tarama kullanıcı tarafından durduruldu." if self.current_lang == 'tr' else "Scan interrupted by the user."
            QMessageBox.information(self, title, text)
            
    def handle_error(self, message):
        title = "Hata" if self.current_lang == 'tr' else "Error"
        QMessageBox.critical(self, title, message)
        self.scan_finished() 

    def fix_selected_items(self):
        if not self.anomalous_items:
            title = "Uyarı" if self.current_lang == 'tr' else "Warning"
            text = "Düzeltilecek öğe yok." if self.current_lang == 'tr' else "No items to fix."
            QMessageBox.warning(self, title, text)
            return

        max_len = self.get_max_length_from_input()
        if max_len == -1:
            return

        title = "Onay" if self.current_lang == 'tr' else "Confirmation"
        text = "Seçili dosya ve dizin adlarını düzeltmek istediğinizden emin misiniz? Bu işlem geri alınamaz!" if self.current_lang == 'tr' else "Are you sure you want to fix the selected file and directory names? This action cannot be undone!"
        reply = QMessageBox.question(self, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            fixed_count = 0
            failed_count = 0
            self.fix_button.setEnabled(False)
            self.result_list_widget.clear()

            sorted_items = sorted(self.anomalous_items, key=lambda x: len(x[0]), reverse=True)

            for full_path, original_name, proposed_new_name, item_type in sorted_items:
                current_directory, _ = os.path.split(full_path)
                recalculated_new_name = shorten_filename(full_path, max_len)
                new_full_path = os.path.join(current_directory, recalculated_new_name)

                if not os.path.exists(full_path):
                    failed_count += 1
                    continue
                if full_path == new_full_path:
                    continue

                try:
                    os.rename(full_path, new_full_path)
                    fixed_count += 1
                except Exception as e:
                    failed_count += 1
                    error_text = f"'{full_path}' yeniden adlandırılamadı: {e}" if self.current_lang == 'tr' else f"Could not rename '{full_path}': {e}"
                    QMessageBox.warning(self, title, error_text)
            
            info_title = "Bilgi" if self.current_lang == 'tr' else "Info"
            info_text = f"{fixed_count} öğe başarıyla düzeltildi, {failed_count} öğe düzeltilemedi." if self.current_lang == 'tr' else f"{fixed_count} items fixed successfully, {failed_count} items failed to be fixed."
            QMessageBox.information(self, info_title, info_text)
            self.anomalous_items = []
            self.scan_button.setEnabled(True)
            self.max_len_input.setEnabled(True)

    def show_about_dialog(self):
        copyright_line = "Telif Hakkı © 2025 A. Serhat KILIÇOĞLU"
        if self.current_lang == 'tr':
            about_text = f"""
            <b>FileName Fixer v{VERSION}</b><br><br>
            Lisans: GNU GPLv3<br>
            Geliştirici: A. Serhat KILIÇOĞLU<br>
            Github: <a href="https://www.github.com/shampuan">www.github.com/shampuan</a><br><br>
            Hatalı ve uzun dosya adlarını Windows'ta sorun çıkmaması için düzeltir.<br>
            Bu program hiçbir garanti getirmez.<br><br>
            {copyright_line}
            """
            title = "Hakkında: FileName Fixer"
        else:
            about_text = f"""
            <b>FileName Fixer v{VERSION}</b><br><br>
            License: GNU GPLv3<br>
            Developer: A. Serhat KILIÇOĞLU<br>
            Github: <a href="https://www.github.com/shampuan">www.github.com/shampuan</a><br><br>
            Fixes invalid and long file names to prevent issues on Windows.<br>
            This program comes with no warranty.<br><br>
            Copyright © 2025 A. Serhat KILIÇOĞLU
            """
            title = "About: FileName Fixer"
        QMessageBox.about(self, title, about_text)

    def closeEvent(self, event):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_thread.wait()
        if self.progress_dialog:
            self.progress_dialog.close()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LongFileNameFixerApp()
    window.show()
    sys.exit(app.exec())
