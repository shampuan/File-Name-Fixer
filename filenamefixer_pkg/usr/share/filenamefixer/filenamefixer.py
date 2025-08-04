#!/usr/bin/env python3

import os
import re
import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QLabel, QFileDialog, QHBoxLayout, QMessageBox, QCheckBox,
    QLineEdit, QFormLayout # QFormLayout, etiket ve girdi kutularını hizalamak için kullanışlı
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QIntValidator, QIcon # Sayısal girdi doğrulaması için

# --- Sabitler ve Fonksiyonlar ---

INVALID_WINDOWS_CHARS = r'[<>:"/\\|?*]'
# MAX_FILENAME_LENGTH artık sabit değil, kullanıcıdan alınacak.
# Varsayılan değeri uygulama içinde ayarlanacak.

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

def shorten_filename(filepath, max_len): # max_len artık bir parametre olarak geliyor
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
            print(f"Uyarı: {filepath} için benzersiz isim bulunamadı. Orijinal kısaltılmışı döndürüldü.")
            return original_shortened_name 

    return new_name

# --- Arka Plan Tarama İş Parçacığı ---
class FileScannerThread(QThread):
    signal_found_item = pyqtSignal(str, str, str, str) # full_path, old_name, new_name, type ('file'/'dir')
    signal_scan_finished = pyqtSignal()
    signal_error = pyqtSignal(str)

    def __init__(self, start_path, include_dirs=True, max_len=200): # max_len buraya da eklendi
        super().__init__()
        self.start_path = start_path
        self.include_dirs = include_dirs
        self.max_len = max_len # max_len burada saklanıyor
        self.stop_scan = False

    def run(self):
        try:
            for root, dirs, files in os.walk(self.start_path):
                if self.stop_scan:
                    break

                # Klasörleri işle
                if self.include_dirs:
                    for dirname in dirs:
                        if self.stop_scan: break
                        full_path = os.path.join(root, dirname)
                        original_name = dirname
                        
                        # max_len parametresini shorten_filename'e geçiyoruz
                        proposed_new_name = shorten_filename(full_path, self.max_len)

                        if proposed_new_name != original_name or len(original_name) > self.max_len or \
                           re.search(INVALID_WINDOWS_CHARS, original_name) or \
                           original_name.endswith(' ') or original_name.endswith('.'):
                            
                            self.signal_found_item.emit(full_path, original_name, proposed_new_name, 'Dizin')

                # Dosyaları işle
                for filename in files:
                    if self.stop_scan:
                        break

                    full_path = os.path.join(root, filename)
                    original_name = filename
                    
                    # max_len parametresini shorten_filename'e geçiyoruz
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
        self.setWindowTitle("FileName Fixer")
        self.setGeometry(100, 100, 400, 500) 
        
        # <<< BURADAKİ SATIR GÜNCELLENDİ >>>
        # İkon dosyasının tam yolunu belirtin.
        # İkonun /usr/share/filenamefixer/namefixer.png yolunda olduğunu varsayıyoruz.
        icon_path = "/usr/share/filenamefixer/namefixer.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            # Eğer ikon belirtilen yolda bulunamazsa bir uyarı mesajı yazdırın
            print(f"Uyarı: İkon dosyası bulunamadı: {icon_path}")
            # Opsiyonel: Varsayılan bir ikon ayarlayın veya ikon olmadan devam edin
        # <<< GÜNCELLEME SONU >>>

        self.selected_directory = ""
        self.anomalous_items = []
        self.scan_thread = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        form_layout = QFormLayout() # Yeni form düzeni

        # Dizin Seçimi Bölümü
        dir_selection_layout = QHBoxLayout()
        self.path_label = QLabel("Seçilen Dizin: Henüz Seçilmedi")
        self.select_dir_button = QPushButton("Dizin Seç")
        self.select_dir_button.clicked.connect(self.select_directory)
        dir_selection_layout.addWidget(self.path_label)
        dir_selection_layout.addWidget(self.select_dir_button)
        main_layout.addLayout(dir_selection_layout)

        # Karakter Uzunluğu Giriş Kutusu
        self.max_len_input = QLineEdit(self)
        self.max_len_input.setPlaceholderText("Maksimum karakter uzunluğu (varsayılan: 200)")
        self.max_len_input.setText("200") # Varsayılan değer
        self.max_len_input.setValidator(QIntValidator(1, 255, self)) # 1 ile 255 arası tam sayı doğrulayıcı
        form_layout.addRow("Maks. Ad Uzunluğu:", self.max_len_input)

        # Klasörleri de tara seçeneği
        self.include_dirs_checkbox = QCheckBox("Klasör Adlarını da Tara")
        self.include_dirs_checkbox.setChecked(True) 
        form_layout.addRow(self.include_dirs_checkbox) # Checkbox'ı forma ekle

        main_layout.addLayout(form_layout) # Form düzenini ana düzene ekle

        # Tarama Butonu
        self.scan_button = QPushButton("Tara")
        self.scan_button.clicked.connect(self.start_scan)
        self.scan_button.setEnabled(False) 
        main_layout.addWidget(self.scan_button)

        # Sonuç Listesi
        self.result_list_widget = QListWidget()
        main_layout.addWidget(self.result_list_widget)

        # Düzelt Butonu
        self.fix_button = QPushButton("Seçilenleri Düzelt")
        self.fix_button.clicked.connect(self.fix_selected_items)
        self.fix_button.setEnabled(False) 
        main_layout.addWidget(self.fix_button)

        # Hakkında Butonu
        self.about_button = QPushButton("Hakkında")
        self.about_button.clicked.connect(self.show_about_dialog) # Yeni metodu bağla
        main_layout.addWidget(self.about_button) # Butonu ana düzene ekle


        self.setLayout(main_layout)

    def get_max_length_from_input(self):
        """Kullanıcının girdiği maksimum uzunluğu alır ve doğrular."""
        try:
            max_len_str = self.max_len_input.text()
            if not max_len_str: # Boşsa varsayılanı kullan
                return 200
            
            max_len = int(max_len_str)
            
            # Windows'un genel yol uzunluğu limiti göz önüne alınarak
            # dosya adı için 255 karakter genellikle maksimumdur.
            # Ancak tam yol uzunluğu da önemli olduğundan 200-240 arası değerler önerilir.
            if not (1 <= max_len <= 255):
                QMessageBox.warning(self, "Geçersiz Giriş", 
                                    "Maksimum ad uzunluğu 1 ile 255 arasında bir sayı olmalıdır.")
                return -1 # Hata durumunu belirtmek için negatif değer

            return max_len
        except ValueError:
            QMessageBox.warning(self, "Geçersiz Giriş", 
                                "Maksimum ad uzunluğu için geçerli bir sayı girin.")
            return -1

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Dizin Seç", os.path.expanduser("~"))
        if directory:
            self.selected_directory = directory
            self.path_label.setText(f"Seçilen Dizin: {directory}")
            self.scan_button.setEnabled(True)
            self.result_list_widget.clear()
            self.anomalous_items = []
            self.fix_button.setEnabled(False)

    def start_scan(self):
        if not self.selected_directory:
            QMessageBox.warning(self, "Uyarı", "Lütfen önce bir dizin seçin!")
            return
        
        # Kullanıcıdan alınan maksimum uzunluğu doğrula
        max_len = self.get_max_length_from_input()
        if max_len == -1: # Geçersiz giriş
            return

        self.result_list_widget.clear()
        self.anomalous_items = []
        self.fix_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.select_dir_button.setEnabled(False)
        self.include_dirs_checkbox.setEnabled(False)
        self.max_len_input.setEnabled(False) # Girişi de devre dışı bırak
        self.path_label.setText(f"Seçilen Dizin: {self.selected_directory} (Taranıyor...)")

        self.scan_thread = FileScannerThread(self.selected_directory, 
                                            include_dirs=self.include_dirs_checkbox.isChecked(),
                                            max_len=max_len) # max_len'i iş parçacığına gönder
        self.scan_thread.signal_found_item.connect(self.add_to_list)
        self.scan_thread.signal_scan_finished.connect(self.scan_finished)
        self.scan_thread.signal_error.connect(self.handle_error)
        self.scan_thread.start()

    def add_to_list(self, full_path, original_name, proposed_new_name, item_type):
        self.anomalous_items.append((full_path, original_name, proposed_new_name, item_type))
        display_text = f"Türü: {item_type}\nOrijinal: {original_name}\nÖnerilen: {proposed_new_name}\nTam Yol: {full_path}\n"
        self.result_list_widget.addItem(display_text)
        self.fix_button.setEnabled(True) 

    def scan_finished(self):
        self.scan_button.setEnabled(True)
        self.select_dir_button.setEnabled(True)
        self.include_dirs_checkbox.setEnabled(True)
        self.max_len_input.setEnabled(True) # Girişi tekrar etkinleştir
        self.path_label.setText(f"Seçilen Dizin: {self.selected_directory} (Tarama Tamamlandı)")
        if not self.anomalous_items:
            QMessageBox.information(self, "Bilgi", "Seçilen dizinde anormal dosya/dizin adı bulunamadı.")
            self.fix_button.setEnabled(False)

    def handle_error(self, message):
        QMessageBox.critical(self, "Hata", message)
        self.scan_finished() 

    def fix_selected_items(self):
        if not self.anomalous_items:
            QMessageBox.warning(self, "Uyarı", "Düzeltilecek öğe yok.")
            return

        # Düzeltme yapmadan önce tekrar maksimum uzunluğu doğrula
        max_len = self.get_max_length_from_input()
        if max_len == -1: # Geçersiz giriş
            return

        reply = QMessageBox.question(self, 'Onay',
                                     "Seçili dosya ve dizin adlarını düzeltmek istediğinizden emin misiniz? "
                                     "Bu işlem geri alınamaz!",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            fixed_count = 0
            failed_count = 0
            self.fix_button.setEnabled(False) 
            self.result_list_widget.clear() 

            sorted_items = sorted(self.anomalous_items, key=lambda x: len(x[0]), reverse=True)

            for full_path, original_name, proposed_new_name, item_type in sorted_items:
                current_directory, current_item_name = os.path.split(full_path)
                
                # Önerilen yeni adı güncel maksimum uzunluğa göre tekrar hesapla
                # Bu, kullanıcı taradıktan sonra max_len'i değiştirirse önemlidir.
                recalculated_new_name = shorten_filename(full_path, max_len)
                new_full_path = os.path.join(current_directory, recalculated_new_name)

                # Eğer orijinal dosya adı zaten düzeltilmişse veya artık yoksa atla
                if not os.path.exists(full_path):
                    # print(f"UYARI: '{full_path}' mevcut değil (önceden değişmiş veya silinmiş olabilir), atlandı.")
                    failed_count += 1
                    continue # Bir sonraki öğeye geç

                # Eğer yeni isim orijinal isimle aynıysa, zaten düzeltilmiş veya kısa demektir
                if full_path == new_full_path:
                    # print(f"BİLGİ: '{full_path}' zaten uygun isimde, yeniden adlandırma yapılmadı.")
                    continue

                try:
                    os.rename(full_path, new_full_path)
                    fixed_count += 1
                    # print(f"Başarıyla yeniden adlandırıldı: {full_path} -> {new_full_path}")
                except OSError as e: 
                    failed_count += 1
                    print(f"HATA OSErr: '{full_path}' yeniden adlandırılamadı: {e}")
                    QMessageBox.warning(self, "Hata", f"'{full_path}' yeniden adlandırılamadı: {e}\nDetay: {e.strerror} ({e.errno})")
                except Exception as e: 
                    failed_count += 1
                    print(f"HATA GENEL: '{full_path}' yeniden adlandırılamadı: {e}")
                    QMessageBox.warning(self, "Hata", f"'{full_path}' yeniden adlandırılamadı: {e}")
            
            QMessageBox.information(self, "Bilgi",
                                    f"{fixed_count} öğe başarıyla düzeltildi, "
                                    f"{failed_count} öğe düzeltilemedi.")
            self.anomalous_items = [] 
            self.scan_button.setEnabled(True) 
            self.max_len_input.setEnabled(True) # Girişi tekrar etkinleştir

    # Yeni Hakkında Diyalog Metodu
    def show_about_dialog(self):
        about_text = """
        <b>FileName Fixer</b><br><br>
        Lisans: GNU GPLv3<br>
        Geliştirici: A. Serhat KILIÇOĞLU<br>
        Github: <a href="https://www.github.com/shampuan">www.github.com/shampuan</a><br><br>
        Hatalı ve uzun dosya adlarını Windows'ta sorun çıkmaması için düzeltir.<br>
        Bu program hiçbir garanti getirmez.
        """
        QMessageBox.about(self, "Hakkında: FileName Fixer", about_text)


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
