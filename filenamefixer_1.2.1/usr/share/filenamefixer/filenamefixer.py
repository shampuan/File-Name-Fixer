#!/usr/bin/env python3

import os
import re
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QLabel, QFileDialog, QHBoxLayout, QMessageBox, QCheckBox,
    QLineEdit, QFormLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIntValidator, QIcon

# --- Sabitler ve Fonksiyonlar ---

INVALID_WINDOWS_CHARS = r'[<>:"/\\|?*]'
VERSION = "1.2.1"

def clean_filename(filename):
    """
    Windows'un dosya/klasör adlarında izin vermediği karakterleri temizler ve
    adın sonundaki nokta veya boşluğu kaldırır.
    """
    base, ext = os.path.splitext(filename)
    cleaned_base = re.sub(INVALID_WINDOWS_CHARS, '', base)
    cleaned_base = cleaned_base.rstrip(' .')

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

    base, ext = os.path.splitext(name) if not is_directory else (name, '')

    cleaned_name = clean_filename(name)
    
    if is_directory:
        cleaned_base = cleaned_name
        ext = ''
    else:
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
        self.selected_directory = ""
        self.anomalous_items = []
        self.scan_thread = None
        self.current_lang = 'tr'
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
            self.fix_button.setText("Seçilenleri Düzelt")
            self.about_button.setText("Hakkında")
            # Dinamik durum mesajları
            if self.selected_directory:
                if self.scan_thread and self.scan_thread.isRunning():
                    self.path_label.setText(f"Seçilen Dizin: {self.selected_directory} (Taranıyor...)")
                else:
                    self.path_label.setText(f"Seçilen Dizin: {self.selected_directory} (Tarama Tamamlandı)")

        elif self.current_lang == 'en':
            self.setWindowTitle(f"FileName Fixer v{VERSION}")
            self.path_label.setText("Selected Directory: Not Selected Yet")
            self.select_dir_button.setText("Select Directory")
            self.max_len_label.setText("Max. Name Length:")
            self.max_len_input.setPlaceholderText("Maximum character length (default: 200)")
            self.include_dirs_checkbox.setText("Scan Folder Names Too")
            self.scan_button.setText("Scan")
            self.fix_button.setText("Fix Selected")
            self.about_button.setText("About")
            # Dinamik durum mesajları
            if self.selected_directory:
                if self.scan_thread and self.scan_thread.isRunning():
                    self.path_label.setText(f"Selected Directory: {self.selected_directory} (Scanning...)")
                else:
                    self.path_label.setText(f"Selected Directory: {self.selected_directory} (Scan Complete)")

    def init_ui(self):
        main_layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.setGeometry(100, 100, 400, 500)
        
        icon_path = "/usr/share/filenamefixer/namefixer.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Dizin Seçimi Bölümü
        dir_selection_layout = QHBoxLayout()
        self.path_label = QLabel()
        self.select_dir_button = QPushButton()
        self.select_dir_button.clicked.connect(self.select_directory)
        dir_selection_layout.addWidget(self.path_label)
        dir_selection_layout.addWidget(self.select_dir_button)
        main_layout.addLayout(dir_selection_layout)

        # Karakter Uzunluğu Giriş Kutusu
        self.max_len_label = QLabel()
        self.max_len_input = QLineEdit(self)
        self.max_len_input.setText("200")
        self.max_len_input.setValidator(QIntValidator(1, 255, self))
        form_layout.addRow(self.max_len_label, self.max_len_input)

        # Klasörleri de tara seçeneği
        self.include_dirs_checkbox = QCheckBox()
        self.include_dirs_checkbox.setChecked(True) 
        form_layout.addRow(self.include_dirs_checkbox)

        main_layout.addLayout(form_layout)

        # Tarama Butonu
        self.scan_button = QPushButton()
        self.scan_button.clicked.connect(self.start_scan)
        self.scan_button.setEnabled(False)
        main_layout.addWidget(self.scan_button)

        # Sonuç Listesi
        self.result_list_widget = QListWidget()
        main_layout.addWidget(self.result_list_widget)

        # Düzelt Butonu
        self.fix_button = QPushButton()
        self.fix_button.clicked.connect(self.fix_selected_items)
        self.fix_button.setEnabled(False) 
        main_layout.addWidget(self.fix_button)

        # <<< YENİ DİL DEĞİŞTİRME BUTONU EKLEMESİ >>>
        self.language_button = QPushButton("Language")
        self.language_button.clicked.connect(self.toggle_language)
        main_layout.addWidget(self.language_button)
        # <<< YENİ DİL DEĞİŞTİRME BUTONU EKLEMESİ SONU >>>

        # Hakkında Butonu
        self.about_button = QPushButton()
        self.about_button.clicked.connect(self.show_about_dialog)
        main_layout.addWidget(self.about_button)

        self.setLayout(main_layout)

    def toggle_language(self):
        """Dili Türkçe ve İngilizce arasında değiştirir."""
        if self.current_lang == 'tr':
            self.current_lang = 'en'
        else:
            self.current_lang = 'tr'
        
        self.retranslateUi()

    def get_max_length_from_input(self):
        """Kullanıcının girdiği maksimum uzunluğu alır ve doğrular."""
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
        self.select_dir_button.setEnabled(False)
        self.include_dirs_checkbox.setEnabled(False)
        self.max_len_input.setEnabled(False)
        self.retranslateUi()

        self.scan_thread = FileScannerThread(self.selected_directory, 
                                            include_dirs=self.include_dirs_checkbox.isChecked(),
                                            max_len=max_len)
        self.scan_thread.signal_found_item.connect(self.add_to_list)
        self.scan_thread.signal_scan_finished.connect(self.scan_finished)
        self.scan_thread.signal_error.connect(self.handle_error)
        self.scan_thread.start()

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

    def scan_finished(self):
        self.scan_button.setEnabled(True)
        self.select_dir_button.setEnabled(True)
        self.include_dirs_checkbox.setEnabled(True)
        self.max_len_input.setEnabled(True)
        self.retranslateUi()
        if not self.anomalous_items:
            title = "Bilgi" if self.current_lang == 'tr' else "Info"
            text = "Seçilen dizinde anormal dosya/dizin adı bulunamadı." if self.current_lang == 'tr' else "No anomalous file/directory names found in the selected folder."
            QMessageBox.information(self, title, text)
            self.fix_button.setEnabled(False)

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
        reply = QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            fixed_count = 0
            failed_count = 0
            self.fix_button.setEnabled(False)
            self.result_list_widget.clear()

            sorted_items = sorted(self.anomalous_items, key=lambda x: len(x[0]), reverse=True)

            for full_path, original_name, proposed_new_name, item_type in sorted_items:
                current_directory, current_item_name = os.path.split(full_path)
                
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
                except OSError as e:
                    failed_count += 1
                    error_text = f"'{full_path}' yeniden adlandırılamadı: {e.strerror}" if self.current_lang == 'tr' else f"Could not rename '{full_path}': {e.strerror}"
                    QMessageBox.warning(self, title, error_text)
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
        if self.current_lang == 'tr':
            about_text = f"""
            <b>FileName Fixer v{VERSION}</b><br><br>
            Lisans: GNU GPLv3<br>
            Geliştirici: A. Serhat KILIÇOĞLU<br>
            Github: <a href="https://www.github.com/shampuan">www.github.com/shampuan</a><br><br>
            Hatalı ve uzun dosya adlarını Windows'ta sorun çıkmaması için düzeltir.<br>
            Bu program hiçbir garanti getirmez.
            """
            title = "Hakkında: FileName Fixer"
        else:
            about_text = f"""
            <b>FileName Fixer v{VERSION}</b><br><br>
            License: GNU GPLv3<br>
            Developer: A. Serhat KILIÇOĞLU<br>
            Github: <a href="https://www.github.com/shampuan">www.github.com/shampuan</a><br><br>
            Fixes invalid and long file names to prevent issues on Windows.<br>
            This program comes with no warranty.
            """
            title = "About: FileName Fixer"
        QMessageBox.about(self, title, about_text)

    def closeEvent(self, event):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_thread.wait()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LongFileNameFixerApp()
    window.show()
    sys.exit(app.exec_())
