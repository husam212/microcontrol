"""
Adding new languages for better user preferences

To add a new language, create a new class that inherits from the Translation base class
and update the get_translations function to include the new language.
The class should contain all the translations for the new language.

Usage in tab files:
    from utils.translations import Translation

    class SomeTab(Gtk.Box):
        def __init__(self, logging: Logger, txt: Translation):
            # Use txt for translations
"""

import os
from logging import Logger
from typing import Protocol, Optional

from utils.logger import LogLevel

class Translation(Protocol):
    """Base protocol for all translations in the application.

    This provides type hints without needing to import all language classes.
    All language classes should implement these properties and methods.
    """
    # Common properties that all translations must have
    msg_desc: str
    msg_app_url: str
    msg_usage: str

    # Tab names
    msg_tab_volume: str
    msg_tab_wifi: str
    msg_tab_bluetooth: str
    msg_tab_battery: str
    msg_tab_display: str

    # Common UI elements
    loading: str
    loading_tabs: str
    close: str
    enable: str
    disable: str

class English:
    """English language translation for the application"""

    def __init__(self):
        # app description
        self.msg_desc = "A sleek GTK-themed control panel for Linux."

        # USB notifications
        self.msg_app_url = "https://github.com/husam212/microcontrol"
        self.msg_usage = "Usage"

        # for args
        self.msg_args_help = "Prints this message"
        self.msg_args_battery = "Starts with the battery tab open"
        self.msg_args_bluetooth = "Starts with the bluetooth tab open"
        self.msg_args_display = "Starts with the display tab open"
        self.msg_args_force = "Makes the app force to have all dependencies installed"
        self.msg_args_volume = "Starts with the volume tab open"
        self.msg_args_volume_v = "Also starts with the volume tab open"
        self.msg_args_wifi = "Starts with the wifi tab open"

        self.msg_args_log = "The program will either log to a file if given a file path,\n or output to stdout based on the log level if given a value between 0, and 3."
        self.msg_args_redact = "Redact sensitive information from logs (network names, device IDs, etc.)"
        self.msg_args_size = "Sets a custom window size"

        # commonly used
        self.connect = "Connect"
        self.connected = "Connected"
        self.connecting = "Connecting..."
        self.disconnect = "Disconnect"
        self.disconnected = "Disconnected"
        self.disconnecting = "Disconnecting..."
        self.enable = "Enable"
        self.disable = "Disable"
        self.close = "Close"
        self.show = "Show"
        self.loading = "Loading..."
        self.loading_tabs = "Loading tabs..."

        # for tabs
        self.refresh = "Refresh"
        self.allow = "Allow"
        self.block = "Block"
        self.msg_tab_battery = "Battery"
        self.msg_tab_bluetooth = "Bluetooth"
        self.msg_tab_display = "Display"
        self.msg_tab_volume = "Audio"
        self.msg_tab_wifi = "Wi-Fi"

        # Battery tab translations
        self.battery_power_saving = "Power Saving"
        self.battery_balanced = "Balanced"
        self.battery_performance = "Performance"
        self.battery_no_batteries = "No battery detected"

        # Bluetooth tab translations
        self.bluetooth_scan_devices = "Scan for Devices"
        self.bluetooth_scanning = "Scanning..."
        self.bluetooth_power = "Bluetooth"
        self.bluetooth_available_devices = "Available Devices"
        self.bluetooth_connect_failed = "Failed to connect to device"
        self.bluetooth_disconnect_failed = "Failed to disconnect from device"
        self.bluetooth_try_again = "Please try again later."

        # Bluetooth forget button translations
        self.bluetooth_forget_failed = "Failed to forget device"
        self.forget = "Forget"
        self.forget_in_progress = "Forgetting..."
        self.rename = "Rename"
        self.bluetooth_rename_failed = "Failed to rename device"
        self.bluetooth_rename_hint = "Leave empty to use the device's own name."

        # Display tab translations
        self.display_brightness = "Brightness"
        self.display_blue_light = "Blue Light"
        self.display_scale = 'Scale'

        # Multiple displays
        self.display_multi_title = 'Layout'
        self.display_mode_join = 'Join'
        self.display_mode_mirror = 'Mirror'
        self.display_mode_single = 'Single'
        self.display_primary = 'Primary Display'
        self.display_active = 'Active Display'
        self.display_builtin = 'Built-in Display'
        self.display_mirror_unavailable = 'Mirroring on Sway requires wl-mirror to be installed.'
        self.display_mirror_unsupported = "Mirroring isn't supported on this compositor yet."
        self.display_off = "This display is off."
        self.display_resolution = "Resolution"
        self.display_refresh_rate = "Refresh Rate"
        self.display_keep_changes = 'Keep these display settings?'
        self.display_revert = 'Revert'
        self.display_keep = 'Keep Changes'
        self.display_reverting_in = 'Settings will be reverted in {seconds} seconds.'
        self.display_orientation = "Orientation"
        self.display_default = "Default"
        self.display_left = "Left"
        self.display_right = "Right"
        self.display_inverted = "Inverted"

        self.display_rotation = "Rotation Options"
        self.display_simple_rotation = "Quick Rotation"
        self.display_specific_orientation = "Specific Orientation"
        self.display_flip_controls = "Display Flipping"
        self.display_rotate_cw = "Rotate Clockwise"
        self.display_rotate_ccw = "Rotate Counter-clockwise"
        self.display_rotation_help = "Rotation applies right away. It’ll reset if you don’t confirm in 10 seconds."

        # Volume tab translations
        self.volume_title = "Volume Settings"
        self.volume_speakers = "Speakers"
        self.volume_tab_tooltip = "Speakers Settings"
        self.volume_output_device = "Output Device"
        self.volume_speaker_volume = "Speaker Volume"
        self.volume_mute_speaker = "Mute Speakers"
        self.volume_unmute_speaker = "Unmute Speakers"
        self.volume_output_combo_tooltip = "Select output device for this application"

        # Volume tab microphone translations
        self.microphone_tab_microphone = "Microphone"
        self.microphone_tab_input_device = "Input Device"
        self.microphone_tab_volume = "Microphone Volume"
        self.microphone_tab_mute_microphone = "Mute Microphone"
        self.microphone_tab_unmute_microphone = "Unmute Microphone"
        self.microphone_tab_tooltip = "Microphone Settings"

        # Volume tab App output translations
        self.app_output_title = "App Output"
        self.app_output_mute = "Mute"
        self.app_output_unmute = "Unmute"
        self.app_output_tab_tooltip = "Application Output Settings"
        self.app_output_no_apps = "No applications playing audio"
        self.app_output_dropdown_tooltip = "Select output device for this application"

        # Volume tab App input translations
        self.app_input_title = "App Input"
        self.volume_configuration = 'Configuration'
        self.volume_configuration_tooltip = 'Choose the profile of each sound device'
        self.volume_no_cards = 'No sound devices found'
        self.app_input_mute = "Mute Microphone for this application"
        self.app_input_unmute = "Unmute Microphone for this application"
        self.app_input_tab_tooltip = "Application Microphone Settings"
        self.app_input_no_apps = "No applications using microphone"

        # WiFi tab translations
        self.wifi_refresh_tooltip = "Refresh Networks"
        self.wifi_power = "Wi-Fi"
        self.wifi_available = "Available Networks"
        self.wifi_forget = "Forget"
        self.wifi_share_title = "Share Network"
        self.wifi_share_scan = "Scan to connect"
        self.wifi_network_name = "Network Name"
        self.wifi_password = "Password"
        self.wifi_loading_networks = "Loading Networks..."

class Russian:
    """Русский перевод утилиты"""

    def __init__(self):
        # app description
        self.msg_desc = "Красивая панель управления для Linux на тулките GTK"

        # USB notifications
        self.msg_app_url = "https://github.com/husam212/microcontrol"
        self.msg_usage = "Инструкция"

        # for args
        self.msg_args_help = "Выводит это сообщение"
        self.msg_args_battery = "При запуске, открывает вкладку управления батареей"
        self.msg_args_bluetooth = "При запуске, открывает вкладку управления Bluetooth"
        self.msg_args_display = "При запуске, открывает вкладку настройки экранов"
        self.msg_args_force = "Принуждает приложение запускаться только в случае, если установлены все зависимости"
        self.msg_args_volume = "При запуске, открывает вкладку управления громкостью"
        self.msg_args_volume_v = "Также, при запуске, открывает вкладку управления громкостью"
        self.msg_args_wifi = "При запуске, открывает вкладку управления сетями Wi-Fi"

        self.msg_args_log = "Программа либо выведет логи в файл, если таков указан,\n либо в stdout на основе уровня логов от 0 до 3"
        self.msg_args_redact = "Меняет важную информацию об оборудовании (имена сетей, идентификаторы устройств, т.д.)"
        self.msg_args_size = "Устанавливает указанный пользователем размер окна"

        # commonly used
        self.connect = "Подключить"
        self.connected = "Подключено"
        self.connecting = "Подключение..."
        self.disconnect = "Отключить"
        self.disconnected = "Не подключено"
        self.disconnecting = "Отключение..."
        self.enable = "Включить"
        self.disable = "Выключить"
        self.close = "Закрыть"
        self.show = "Показать"
        self.loading = "Загрузка..."
        self.loading_tabs = "Загрузка вкладок..."

        # for tabs
        self.refresh = "Обновить"
        self.allow = "Разрешить"
        self.block = "Запретить"
        self.msg_tab_battery = "Батарея"
        self.msg_tab_bluetooth = "Bluetooth"
        self.msg_tab_display = "Экран"
        self.msg_tab_volume = "Звук"
        self.msg_tab_wifi = "Wi-Fi"

        # Battery tab translations
        self.battery_power_saving = "Энергосбережение"
        self.battery_balanced = "Сбалансированный"
        self.battery_performance = "Макс. производительность"
        self.battery_no_batteries = "Батареи отсутствуют"

        # Bluetooth tab translations
        self.bluetooth_scan_devices = "Поиск устройств"
        self.bluetooth_scanning = "Поиск..."
        self.bluetooth_power = "Bluetooth"
        self.bluetooth_available_devices = "Доступные устройства"
        self.bluetooth_connect_failed = "Не удалось подключиться к устройству"
        self.bluetooth_disconnect_failed = "Не удалось отключиться от устройсва"
        self.bluetooth_try_again = "Попробуйте позже"

        # Bluetooth forget button translations
        self.bluetooth_forget_failed = "Не удалось разорвать сопряжение"
        self.forget = "Разовать сопряжение"
        self.forget_in_progress = "Идёт разрыв сопряжения..."

        # Display tab translations
        self.display_brightness = "Яркость"
        self.display_blue_light = "Синий цвет"
        self.display_scale = 'Масштаб'

        # Multiple displays
        self.display_multi_title = 'Расположение'
        self.display_mode_join = 'Объединить'
        self.display_mode_mirror = 'Зеркало'
        self.display_mode_single = 'Один'
        self.display_primary = 'Основной дисплей'
        self.display_active = 'Активный дисплей'
        self.display_builtin = 'Встроенный дисплей'
        self.display_mirror_unavailable = 'Для зеркалирования в Sway необходимо установить wl-mirror.'
        self.display_keep_changes = 'Сохранить эти параметры дисплея?'
        self.display_revert = 'Отменить'
        self.display_keep = 'Сохранить'
        self.display_reverting_in = 'Параметры будут сброшены через {seconds} с.'
        self.display_orientation = "Угол поворота"
        self.display_default = "Стандарт"
        self.display_left = "Влево"
        self.display_right = "Вправо"
        self.display_inverted = "Снизу вверх"

        self.display_rotation = "Параметры поворота"
        self.display_simple_rotation = "Быстрый поворот"
        self.display_specific_orientation = "Точный поворот"
        self.display_flip_controls = "Поворот экрана"
        self.display_rotate_cw = "Повернутьпо часовой"
        self.display_rotate_ccw = "Повернуть против часовой"
        self.display_rotation_help = "Поворот применится немедленно. Через 10 секунд без подтверждения произойдёт сброс."

        # Volume tab translations
        self.volume_title = "Параметры громкости"
        self.volume_speakers = "Динамики"
        self.volume_tab_tooltip = "Параметры динамиков"
        self.volume_output_device = "Устройство вывода"
        self.volume_speaker_volume = "Громкость динамика"
        self.volume_mute_speaker = "Заглушить динамики"
        self.volume_unmute_speaker = "Отключить глушение динамиков"
        self.volume_output_combo_tooltip = "Выберите устройство вывода для этого приложения"

        # Volume tab microphone translations
        self.microphone_tab_microphone = "Микрофон"
        self.microphone_tab_input_device = "Устройство ввода"
        self.microphone_tab_volume = "Громкость микрофона"
        self.microphone_tab_mute_microphone = "Заглушить микрофон"
        self.microphone_tab_unmute_microphone = "Отключить глушение микрофона"
        self.microphone_tab_tooltip = "Параметры микрофона"

        # Volume tab App output translations
        self.app_output_title = "Вывод приложения"
        self.app_output_mute = "Заглушить"
        self.app_output_unmute = "Отключить глушение"
        self.app_output_tab_tooltip = "Параметры вывода приложения"
        self.app_output_no_apps = "Ни в одном приложении не проигрывается аудио"
        self.app_output_dropdown_tooltip = "Выберите устройство выбора для этого приложения"

        # Volume tab App input translations
        self.app_input_title = "Ввод приложения"
        self.volume_configuration = 'Конфигурация'
        self.volume_configuration_tooltip = 'Выберите профиль для каждого звукового устройства'
        self.volume_no_cards = 'Звуковые устройства не найдены'
        self.app_input_mute = "Заглушить микрофон этому приложению"
        self.app_input_unmute = "Отключить глушение микрофона этому приложению"
        self.app_input_tab_tooltip = "Параметры микрофона приложения"
        self.app_input_no_apps = "Ни одно приложение не использует микрофон"

        # WiFi tab translations
        self.wifi_refresh_tooltip = "Поиск сетей"
        self.wifi_power = "Wi-Fi"
        self.wifi_available = "Доступные сети"
        self.wifi_forget = "Забыть"
        self.wifi_share_title = "Поделиться сетью"
        self.wifi_share_scan = "Сканируйте, чтобы поделиться"
        self.wifi_network_name = "Имя сети"
        self.wifi_password = "Пароль"
        self.wifi_loading_networks = "Загрузка сетей..."

class German:
    """German language translation for the application"""

    def __init__(self):
        # app description
        self.msg_desc = "Ein elegantes Bedienfeld für Linux mit GTK-Theming."

        # USB notifications
        self.msg_app_url = "https://github.com/husam212/microcontrol"
        self.msg_usage = "Nutzung"

        # for args
        self.msg_args_help = "Zeigt diese Meldung an"
        self.msg_args_battery = "Startet die Anwendung mit dem Batterie-Tab"
        self.msg_args_bluetooth = "Startet die Anwendung mit dem Bluetooth-Tab"
        self.msg_args_display = "Startet die Anwendung mit dem Display-Tab"
        self.msg_args_force = "Zwingt die Anwendung dazu alle Abhängigkeiten installiert zu haben"
        self.msg_args_volume = "Startet die Anwendung mit dem Lautstärke-Tab"
        self.msg_args_volume_v = "Startet die Anwendung ebenfalls mit dem Bluetooth-Tab"
        self.msg_args_wifi = "Startet die Anwendung mit dem WLAN-Tab"

        self.msg_args_log = "Das Programm schreibt das Log an den angegeben Pfad,\n oder an stdout basierend auf dem Log-Level, wenn ein Wert zwischen 0 und 3 angegeben wird."
        self.msg_args_redact = "Entfernt sesible Daten aus dem Log (Netzwerknamen, Geräte IDs, usw.)"
        self.msg_args_size = "Legt eine benutzerdefinierte Fenstergröße fest"

        # commonly used
        self.connect = "Verbinden"
        self.connected = "Verbunden"
        self.connecting = "Verbinde..."
        self.disconnect = "Verbindung trennen"
        self.disconnected = "Verbindung getrennt"
        self.disconnecting = "Trenne Verbindung..."
        self.enable = "Einschalten"
        self.disable = "Ausschalten"
        self.close = "Schließen"
        self.show = "Einblenden"
        self.loading = "Laden..."
        self.loading_tabs = "Lade Tabs..."

        # for tabs
        self.refresh = "Aktualisieren"
        self.allow = "Erlauben"
        self.block = "Blockieren"
        self.msg_tab_battery = "Akku"
        self.msg_tab_bluetooth = "Bluetooth"
        self.msg_tab_display = "Bildschirm"
        self.msg_tab_volume = "Audio"
        self.msg_tab_wifi = "WLAN"

        # Battery tab translations
        self.battery_power_saving = "Energiesparen"
        self.battery_balanced = "Ausbalanciert"
        self.battery_performance = "Höchstleistung"
        self.battery_no_batteries = "Keine Akkus gefunden"

        # Bluetooth tab translations
        self.bluetooth_scan_devices = "Nach Geräten suchen"
        self.bluetooth_scanning = "Suche..."
        self.bluetooth_power = "Bluetooth"
        self.bluetooth_available_devices = "Verfügbare Geräet"
        self.bluetooth_connect_failed = "Gerät konnte nicht verbunden werden"
        self.bluetooth_disconnect_failed = "Gerät konnte nicht getrennt werden"
        self.bluetooth_try_again = "Bitte versuche es später erneut"

        # Display tab translations
        self.display_brightness = "Helligkeit"
        self.display_blue_light = "Blaulichtfilter"
        self.display_scale = 'Skalierung'

        # Multiple displays
        self.display_multi_title = 'Anordnung'
        self.display_mode_join = 'Verbinden'
        self.display_mode_mirror = 'Spiegeln'
        self.display_mode_single = 'Einzeln'
        self.display_primary = 'Hauptbildschirm'
        self.display_active = 'Aktiver Bildschirm'
        self.display_builtin = 'Eingebauter Bildschirm'
        self.display_mirror_unavailable = 'Spiegeln unter Sway erfordert die Installation von wl-mirror.'
        self.display_keep_changes = 'Diese Bildschirmeinstellungen beibehalten?'
        self.display_revert = 'Zurücksetzen'
        self.display_keep = 'Änderungen beibehalten'
        self.display_reverting_in = 'Die Einstellungen werden in {seconds} Sekunden zurückgesetzt.'
        self.display_orientation = "Ausrichtung"
        self.display_default = "Standard"
        self.display_left = "Links"
        self.display_right = "Rechts"
        self.display_inverted = "Invertiert"

        self.display_rotation = "Rotationseinstellungen"
        self.display_simple_rotation = "Schnellrotation"
        self.display_specific_orientation = "Spezifische Orientierung"
        self.display_flip_controls = "Display drehung"
        self.display_rotate_cw = "Im Uhrzeigersinn drehen"
        self.display_rotate_ccw = "Gegen den Uhrzeigersinn drehen"
        self.display_rotation_help = "Die Einstellungen werden automatisch übernommen und nach 10 Sekunden zurückgesetzt sollten sie nicht bestätigt werden."

        # Volume tab translations
        self.volume_title = "Lautstärke Einstellungen"
        self.volume_speakers = "Ausgabegeräte"
        self.volume_tab_tooltip = "Geräte"
        self.volume_output_device = "Ausgabegeräte"
        self.volume_speaker_volume = "Ausgabelautstärke"
        self.volume_mute_speaker = "Lautsprecher Stummschalten"
        self.volume_unmute_speaker = "Stummschaltung aufheben"
        self.volume_output_combo_tooltip = "Ausgabegerät für die Anwendung auswählen"

        # Volume tab microphone translations
        self.microphone_tab_microphone = "Eingabegeräte"
        self.microphone_tab_input_device = "Eingabegerät"
        self.microphone_tab_volume = "Aufnahmelautstärke"
        self.microphone_tab_mute_microphone = "Mikrofon Stummschalten"
        self.microphone_tab_unmute_microphone = "Stummschaltung aufheben"
        self.microphone_tab_tooltip = "Geräte"

        # Volume tab App output translations
        self.app_output_title = "App Ausgabe"
        self.app_output_mute = "Stummschalten"
        self.app_output_unmute = "Stummschaltung aufheben"
        self.app_output_tab_tooltip = "Anwendungs Lautstärke Einstellungen"
        self.app_output_no_apps = "Keine Anwendungen die Ton wiedergeben"
        self.app_output_dropdown_tooltip = "Ausgabegerät für die Anwenung auswählen"

        # Volume tab App input translations
        self.app_input_title = "App Aufnahme"
        self.volume_configuration = 'Konfiguration'
        self.volume_configuration_tooltip = 'Profil für jedes Audiogerät auswählen'
        self.volume_no_cards = 'Keine Audiogeräte gefunden'
        self.app_input_mute = "Mikrofon für diese Anwenung Stummschalten"
        self.app_input_unmute = "Stummschaltung des Mikrofons für diese Anwendung aufheben"
        self.app_input_tab_tooltip = "Anwenungsaufnahme Einstellungen"
        self.app_input_no_apps = "Keine Anwenungen die Ton aufzeichenen"

        # WiFi tab translations
        self.wifi_refresh_tooltip = "Nach neuen Netzwerken suchen"
        self.wifi_power = "WLAN"
        self.wifi_available = "Verfügbare Netzwerke"
        self.wifi_forget = "Vergessen"
        self.wifi_share_title = "Netzwerk teilen"
        self.wifi_share_scan = "Scan to connect"
        self.wifi_network_name = "Netzwerkname"
        self.wifi_password = "Passwort"
        self.wifi_loading_networks = "Lade Netzwerke..."

class Italian:
    """Italian language translation for the application"""

    def __init__(self):
        # app description
        self.msg_desc = "Un pannello di controllo elegante e basato su GTK per Linux."

        # USB notifications
        self.msg_app_url = "https://github.com/husam212/microcontrol"
        self.msg_usage = "Utilizzo"

        # for args
        self.msg_args_help = "Mostra questo messaggio"
        self.msg_args_battery = "Avvia con la scheda della batteria aperta"
        self.msg_args_bluetooth = "Avvia con la scheda del bluetooth aperta"
        self.msg_args_display = "Avvia con la scheda dello schermo aperta"
        self.msg_args_force = "Fà si che l'applicazione richieda forzatamente tutte le dipendenze installate"
        self.msg_args_volume = "Avvia con la scheda del volume aperta"
        self.msg_args_volume_v = "Avvia con anche la scheda del volume aperta"
        self.msg_args_wifi = "Avvia con la scheda del wifi aperta"

        self.msg_args_log = "Il programma creerà un log se gli viene fornito un percorso,\n altrimenti invierà l'output su stdout in base al livello di log, con un valore compreso tra 0 e 3."
        self.msg_args_redact = "Elimina le informazioni sensibili dai registri (reti, ID dei device, etc.)"
        self.msg_args_size = "Imposta una dimensione personalizzata della finestra"

        # commonly used
        self.connect = "Connetti"
        self.connected = "Connesso"
        self.connecting = "Connessione..."
        self.disconnect = "Disconnetti"
        self.disconnected = "Disconnesso"
        self.disconnecting = "Disconnessione..."
        self.enable = "Attiva"
        self.disable = "Disattiva"
        self.close = "Chiudi"
        self.show = "Mostra"
        self.loading = "Caricamento..."
        self.loading_tabs = "Caricamento schede..."

        # for tabs
        self.refresh = "Ricarica"
        self.allow = "Permetti"
        self.block = "Blocca"
        self.msg_tab_battery = "Batteria"
        self.msg_tab_bluetooth = "Bluetooth"
        self.msg_tab_display = "Schermo"
        self.msg_tab_volume = "Audio"
        self.msg_tab_wifi = "Wi-Fi"

        # Battery tab translations
        self.battery_power_saving = "Risparmio energetico"
        self.battery_balanced = "Bilanciato"
        self.battery_performance = "Massime prestazioni"
        self.battery_no_batteries = "Nessuna batteria rilevata"

        # Bluetooth tab translations
        self.bluetooth_scan_devices = "Scansiona per trovare dispositivi"
        self.bluetooth_scanning = "Scansiono..."
        self.bluetooth_power = "Bluetooth"
        self.bluetooth_available_devices = "Dispositivi disponibili"
        self.bluetooth_connect_failed = "Errore durante la connessione al dispositivo"
        self.bluetooth_disconnect_failed = "Errore durante la disconnessione dal dispositivo"
        self.bluetooth_try_again = "Perfavore riprova."

        # Display tab translations
        self.display_brightness = "Luminosità"
        self.display_blue_light = "Luce blu"
        self.display_scale = 'Scala'

        # Multiple displays
        self.display_multi_title = 'Disposizione'
        self.display_mode_join = 'Unisci'
        self.display_mode_mirror = 'Duplica'
        self.display_mode_single = 'Singolo'
        self.display_primary = 'Schermo principale'
        self.display_active = 'Schermo attivo'
        self.display_builtin = 'Schermo integrato'
        self.display_mirror_unavailable = "La duplicazione su Sway richiede l'installazione di wl-mirror."
        self.display_keep_changes = 'Mantenere queste impostazioni dello schermo?'
        self.display_revert = 'Ripristina'
        self.display_keep = 'Mantieni modifiche'
        self.display_reverting_in = 'Le impostazioni verranno ripristinate tra {seconds} secondi.'
        self.display_orientation = "Orientamento"
        self.display_default = "Predefinito"
        self.display_left = "Sinistra"
        self.display_right = "Destra"
        self.display_inverted = "Invertito"

        self.display_rotation = "Opzioni della rotazione"
        self.display_simple_rotation = "Rotazione veloce"
        self.display_specific_orientation = "Orientamento spefico"
        self.display_flip_controls = "Capovolgimento dello schermo"
        self.display_rotate_cw = "Ruota in senso orario"
        self.display_rotate_ccw = "Ruota in senso antiorario"
        self.display_rotation_help = "La rotazione verrà applicata subito. In caso di mancata conferma entro 10 secondi verrà ripristinata."

        # Volume tab translations
        self.volume_title = "Impostazione volume"
        self.volume_speakers = "Altoparlanti"
        self.volume_tab_tooltip = "Impostazioni altoparlanti"
        self.volume_output_device = "Dispostivo d'uscita"
        self.volume_speaker_volume = "Volume altoparlanti"
        self.volume_mute_speaker = "Muta altoparlanti"
        self.volume_unmute_speaker = "Smuta altoparlanti"
        self.volume_output_combo_tooltip = "Seleziona il dispositivo d'uscita per questa applicazione"

        # Volume tab microphone translations
        self.microphone_tab_microphone = "Microfono"
        self.microphone_tab_input_device = "Dispositivo di input"
        self.microphone_tab_volume = "Volume del microfono"
        self.microphone_tab_mute_microphone = "Muta microfono"
        self.microphone_tab_unmute_microphone = "Smuta microfono"
        self.microphone_tab_tooltip = "Impostazioni microfono"

        # Volume tab App output translations
        self.app_output_title = "Output dell'app"
        self.app_output_mute = "Muta"
        self.app_output_unmute = "Smuta"
        self.app_output_tab_tooltip = "Impostazioni dell'output dell'app"
        self.app_output_no_apps = "Nessuna applicazione sta riproducendo audio"
        self.app_output_dropdown_tooltip = "Seleziona il dispositivo d'uscita di questa applicazione"

        # Volume tab App input translations
        self.app_input_title = "Ingresso app"
        self.volume_configuration = 'Configurazione'
        self.volume_configuration_tooltip = 'Scegli il profilo di ogni dispositivo audio'
        self.volume_no_cards = 'Nessun dispositivo audio trovato'
        self.app_input_mute = "Muta il microfono per questa applicazione"
        self.app_input_unmute = "Smuta il microfono per questa applicazione"
        self.app_input_tab_tooltip = "Impostazioni del microfono dell'app"
        self.app_input_no_apps = "Nessun applicazione sta usando il microfono"

        # WiFi tab translations
        self.wifi_refresh_tooltip = "Ricarica reti"
        self.wifi_power = "Wi-Fi"
        self.wifi_available = "Reti disponibili"
        self.wifi_forget = "Dimentica"
        self.wifi_share_title = "Condividi rete"
        self.wifi_share_scan = "Scansiona per connetterti"
        self.wifi_network_name = "Nome della rete"
        self.wifi_password = "Password"
        self.wifi_loading_networks = "Carico le reti..."

class Spanish:
    """Spanish language translation for the application"""

    def __init__(self):
        # app description
        self.msg_desc = "Un elegante panel de control con tema GTK para Linux."
        self.msg_app_url = "https://github.com/husam212/microcontrol"
        self.msg_usage = "Uso"

        # for args
        self.msg_args_help = "Muestra este mensaje"
        self.msg_args_battery = "Inicia con la pestaña de batería abierta"
        self.msg_args_bluetooth = "Inicia con la pestaña de bluetooth abierta"
        self.msg_args_display = "Inicia con la pestaña de pantalla abierta"
        self.msg_args_force = "Fuerza la aplicación a iniciar sin todas las dependencias"
        self.msg_args_volume = "Inicia con la pestaña de volumen abierta"
        self.msg_args_volume_v = "También inicia con la pestaña de volumen abierta"
        self.msg_args_wifi = "Inicia con la pestaña de wifi abierta"

        self.msg_args_log = "El programa registrará en un archivo si se proporciona una ruta,\n o mostrará en stdout según el nivel de registro si se da un valor entre 0 y 3."
        self.msg_args_redact = "Oculta información sensible de los registros (nombres de red, IDs de dispositivos, etc.)"
        self.msg_args_size = "Establece un tamaño de ventana personalizado"

        # commonly used
        self.connect = "Conectar"
        self.connected = "Conectado"
        self.connecting = "Conectando..."
        self.disconnect = "Desconectar"
        self.disconnected = "Desconectado"
        self.disconnecting = "Desconectando..."
        self.disable = "Deshabilitar"
        self.enable = "Habilitar"
        self.close = "Cerrar"
        self.show = "Mostrar"
        self.loading = "Cargando..."
        self.loading_tabs = "Cargando pestañas..."

        # for tabs
        self.refresh = "Actualizar"
        self.allow = "Permitir"
        self.block = "Bloquear"
        self.msg_tab_battery = "Batería"
        self.msg_tab_bluetooth = "Bluetooth"
        self.msg_tab_display = "Pantalla"
        self.msg_tab_volume = "Audio"
        self.msg_tab_wifi = "Wi-Fi"

        # Battery tab translations
        self.battery_power_saving = "Ahorro de Energía"
        self.battery_balanced = "Equilibrado"
        self.battery_performance = "Rendimiento"
        self.battery_no_batteries = "No se detectó ninguna batería"

        # Bluetooth tab translations
        self.bluetooth_scan_devices = "Buscar dispositivos"
        self.bluetooth_scanning = "Buscando..."
        self.bluetooth_power = "Bluetooth"
        self.bluetooth_available_devices = "Dispositivos Disponibles"
        self.bluetooth_connect_failed = "Error al conectar el dispositivo"
        self.bluetooth_disconnect_failed = "Error al desconectar el dispositivo"
        self.bluetooth_try_again = "Por favor, inténtelo de nuevo más tarde."

        # Display tab translations
        self.display_brightness = "Brillo"
        self.display_blue_light = "Luz Azul"
        self.display_scale = 'Escala'

        # Multiple displays
        self.display_multi_title = 'Disposición'
        self.display_mode_join = 'Unir'
        self.display_mode_mirror = 'Duplicar'
        self.display_mode_single = 'Única'
        self.display_primary = 'Pantalla principal'
        self.display_active = 'Pantalla activa'
        self.display_builtin = 'Pantalla integrada'
        self.display_mirror_unavailable = 'Duplicar en Sway requiere tener instalado wl-mirror.'
        self.display_keep_changes = '¿Mantener esta configuración de pantalla?'
        self.display_revert = 'Revertir'
        self.display_keep = 'Mantener cambios'
        self.display_reverting_in = 'La configuración se revertirá en {seconds} segundos.'
        self.display_orientation = "Orientación"
        self.display_default = "Predeterminado"
        self.display_left = "Izquierda"
        self.display_right = "Derecha"
        self.display_inverted = "Invertido"

        # Volume tab translations
        self.volume_title = "Configuración de Volumen"
        self.volume_speakers = "Altavoces"
        self.volume_tab_tooltip = "Configuración de Altavoces"
        self.volume_output_device = "Dispositivo de Salida"
        self.volume_speaker_volume = "Volumen de Altavoces"
        self.volume_mute_speaker = "Silenciar Altavoces"
        self.volume_unmute_speaker = "Activar Altavoces"
        self.volume_output_combo_tooltip = "Seleccionar dispositivo de salida para esta aplicación"

        # Volume tab microphone translations
        self.microphone_tab_microphone = "Micrófono"
        self.microphone_tab_input_device = "Dispositivo de Entrada"
        self.microphone_tab_volume = "Volumen de Micrófono"
        self.microphone_tab_mute_microphone = "Silenciar Micrófono"
        self.microphone_tab_unmute_microphone = "Activar Micrófono"
        self.microphone_tab_tooltip = "Configuración de Micrófono"

        # Volume tab App output translations
        self.app_output_title = "Salida de Aplicaciones"
        self.app_output_mute = "Silenciar"
        self.app_output_unmute = "Activar"
        self.app_output_tab_tooltip = "Configuración de Salida de Aplicaciones"
        self.app_output_no_apps = "No hay aplicaciones reproduciendo audio"
        self.app_output_dropdown_tooltip = "Seleccionar dispositivo de salida para esta aplicación"

        # Volume tab App input translations
        self.app_input_title = "Entrada de Aplicaciones"
        self.volume_configuration = 'Configuración'
        self.volume_configuration_tooltip = 'Elige el perfil de cada dispositivo de sonido'
        self.volume_no_cards = 'No se encontraron dispositivos de sonido'
        self.app_input_mute = "Silenciar Micrófono para esta aplicación"
        self.app_input_unmute = "Activar Micrófono para esta aplicación"
        self.app_input_tab_tooltip = "Configuración del Micrófono de Aplicaciones"
        self.app_input_no_apps = "No hay aplicaciones usando el micrófono"

        # WiFi tab translations
        self.wifi_refresh_tooltip = "Actualizar Redes"
        self.wifi_power = "Wi-Fi"
        self.wifi_available = "Redes Disponibles"
        self.wifi_forget = "Olvidar"
        self.wifi_share_title = "Compartir Red"
        self.wifi_share_scan = "Escanear para conectar"
        self.wifi_network_name = "Nombre de Red"
        self.wifi_password = "Contraseña"
        self.wifi_loading_networks = "Cargando Redes..."

class Portuguese:
    """Portuguese language translation for the application"""

    def __init__(self):
        # app description
        self.msg_desc = "Um elegante painel de controle com tema GTK para Linux."
        self.msg_app_url = "https://github.com/husam212/microcontrol"
        self.msg_usage = "Uso"

        # for args
        self.msg_args_help = "Mostra esta mensagem"
        self.msg_args_battery = "Inicia com a aba de bateria aberta"
        self.msg_args_bluetooth = "Inicia com a aba de bluetooth aberta"
        self.msg_args_display = "Inicia com a aba de tela aberta"
        self.msg_args_force = "Força o aplicativo a iniciar sem todas as dependências"
        self.msg_args_volume = "Inicia com a aba de volume aberta"
        self.msg_args_volume_v = "Também inicia com a aba de volume aberta"
        self.msg_args_wifi = "Inicia com a aba de wifi aberta"

        self.msg_args_log = "O programa registrará em um arquivo se fornecido um caminho,\n ou mostrará no stdout com base no nível de registro se fornecido um valor entre 0 e 3."
        self.msg_args_redact = "Oculta informações sensíveis dos registros (nomes de rede, IDs de dispositivos, etc.)"
        self.msg_args_size = "Define um tamanho de janela personalizado"

        # commonly used
        self.connect = "Conectar"
        self.connected = "Conectado"
        self.connecting = "Conectando..."
        self.disconnect = "Desconectar"
        self.disconnected = "Desconectado"
        self.disconnecting = "Desconectando..."
        self.enable = "Ativar"
        self.disable = "Desativar"
        self.close = "Fechar"
        self.show = "Mostrar"
        self.loading = "Carregando..."
        self.loading_tabs = "Carregando abas..."

        # for tabs
        self.refresh = "Atualizar"
        self.allow = "Permitir"
        self.block = "Bloquear"
        self.msg_tab_battery = "Bateria"
        self.msg_tab_bluetooth = "Bluetooth"
        self.msg_tab_display = "Tela"
        self.msg_tab_volume = "Áudio"
        self.msg_tab_wifi = "Wi-Fi"

        # Battery tab translations
        self.battery_power_saving = "Economia de Energia"
        self.battery_balanced = "Equilibrado"
        self.battery_performance = "Desempenho"
        self.battery_no_batteries = "Nenhuma bateria detectada"

        # Bluetooth tab translations
        self.bluetooth_scan_devices = "Buscar Dispositivos"
        self.bluetooth_scanning = "Buscando..."
        self.bluetooth_power = "Bluetooth"
        self.bluetooth_available_devices = "Dispositivos Disponíveis"
        self.bluetooth_connect_failed = "Falha ao conectar ao dispositivo"
        self.bluetooth_disconnect_failed = "Falha ao desconectar do dispositivo"
        self.bluetooth_try_again = "Por favor, tente novamente mais tarde."

        # Display tab translations
        self.display_brightness = "Brilho"
        self.display_blue_light = "Luz Azul"
        self.display_scale = 'Escala'

        # Multiple displays
        self.display_multi_title = 'Disposição'
        self.display_mode_join = 'Unir'
        self.display_mode_mirror = 'Espelhar'
        self.display_mode_single = 'Único'
        self.display_primary = 'Monitor principal'
        self.display_active = 'Monitor ativo'
        self.display_builtin = 'Monitor integrado'
        self.display_mirror_unavailable = 'Espelhar no Sway requer que o wl-mirror esteja instalado.'
        self.display_keep_changes = 'Manter estas configurações de monitor?'
        self.display_revert = 'Reverter'
        self.display_keep = 'Manter alterações'
        self.display_reverting_in = 'As configurações serão revertidas em {seconds} segundos.'
        self.display_orientation = "Orientação"
        self.display_default = "Padrão"
        self.display_left = "Esquerda"
        self.display_right = "Direita"
        self.display_inverted = "Invertido"

        # Volume tab translations
        self.volume_title = "Configurações de Volume"
        self.volume_speakers = "Alto-falantes"
        self.volume_tab_tooltip = "Configurações de Alto-falantes"
        self.volume_output_device = "Dispositivo de Saída"
        self.volume_speaker_volume = "Volume dos Alto-falantes"
        self.volume_mute_speaker = "Silenciar Alto-falantes"
        self.volume_unmute_speaker = "Ativar Alto-falantes"
        self.volume_output_combo_tooltip = "Selecionar dispositivo de saída para este aplicativo"

        # Volume tab microphone translations
        self.microphone_tab_microphone = "Microfone"
        self.microphone_tab_input_device = "Dispositivo de Entrada"
        self.microphone_tab_volume = "Volume do Microfone"
        self.microphone_tab_mute_microphone = "Silenciar Microfone"
        self.microphone_tab_unmute_microphone = "Ativar Microfone"
        self.microphone_tab_tooltip = "Configurações do Microfone"

        # Volume tab App output translations
        self.app_output_title = "Saída de Aplicativos"
        self.app_output_mute = "Silenciar"
        self.app_output_unmute = "Ativar"
        self.app_output_tab_tooltip = "Configurações de Saída de Aplicativos"
        self.app_output_no_apps = "Nenhum aplicativo reproduzindo áudio"
        self.app_output_dropdown_tooltip = "Selecionar dispositivo de saída para este aplicativo"

        # Volume tab App input translations
        self.app_input_title = "Entrada de Aplicativos"
        self.volume_configuration = 'Configuração'
        self.volume_configuration_tooltip = 'Escolha o perfil de cada dispositivo de som'
        self.volume_no_cards = 'Nenhum dispositivo de som encontrado'
        self.app_input_mute = "Silenciar Microfone para este aplicativo"
        self.app_input_unmute = "Ativar Microfone para este aplicativo"
        self.app_input_tab_tooltip = "Configurações do Microfone de Aplicativos"
        self.app_input_no_apps = "Nenhum aplicativo usando o microfone"

        # WiFi tab translations
        self.wifi_refresh_tooltip = "Atualizar Redes"
        self.wifi_power = "Wi-Fi"
        self.wifi_available = "Redes Disponíveis"
        self.wifi_forget = "Esquecer"
        self.wifi_share_title = "Compartilhar Rede"
        self.wifi_share_scan = "Escanear para conectar"
        self.wifi_network_name = "Nome da Rede"
        self.wifi_password = "Senha"
        self.wifi_loading_networks = "Carregando Redes..."

class French:
    """French language translation for the application"""

    def __init__(self):
        # app description
        self.msg_desc = "Un panneau de contrôle élégant avec thème GTK pour Linux."
        self.msg_app_url = "https://github.com/husam212/microcontrol"
        self.msg_usage = "Utilisation"

        # for args
        self.msg_args_help = "Affiche ce message"
        self.msg_args_battery = "Démarre avec l'onglet de batterie ouvert"
        self.msg_args_bluetooth = "Démarre avec l'onglet bluetooth ouvert"
        self.msg_args_display = "Démarre avec l'onglet d'affichage ouvert"
        self.msg_args_force = "Force l'application à démarrer sans toutes les dépendances"
        self.msg_args_volume = "Démarre avec l'onglet de volume ouvert"
        self.msg_args_volume_v = "Démarre également avec l'onglet de volume ouvert"
        self.msg_args_wifi = "Démarre avec l'onglet Wi-Fi ouvert"

        self.msg_args_log = "Le programme enregistrera dans un fichier si un chemin est fourni,\n ou affichera sur stdout selon le niveau de journalisation si une valeur entre 0 et 3 est donnée."
        self.msg_args_redact = "Masque les informations sensibles des journaux (noms de réseau, identifiants d'appareils, etc.)"
        self.msg_args_size = "Définit une taille de fenêtre personnalisée"

        # commonly used
        self.connect = "Connecter"
        self.connected = "Connecté"
        self.connecting = "Connexion..."
        self.disconnect = "Déconnecter"
        self.disconnected = "Déconnecté"
        self.disconnecting = "Déconnexion..."
        self.enable = "Activer"
        self.disable = "Désactiver"
        self.close = "Fermer"
        self.show = "Afficher"
        self.loading = "Chargement..."
        self.loading_tabs = "Chargement des onglets..."

        # for tabs
        self.refresh = "Actualiser"
        self.allow = "Autoriser"
        self.block = "Bloquer"
        self.msg_tab_battery = "Batterie"
        self.msg_tab_bluetooth = "Bluetooth"
        self.msg_tab_display = "Affichage"
        self.msg_tab_volume = "Audio"
        self.msg_tab_wifi = "Wi-Fi"

        # Battery tab translations
        self.battery_power_saving = "Économie d'Énergie"
        self.battery_balanced = "Équilibré"
        self.battery_performance = "Performance"
        self.battery_no_batteries = "Aucune batterie détectée"

        # Bluetooth tab translations
        self.bluetooth_scan_devices = "Rechercher des Appareils"
        self.bluetooth_scanning = "Recherche..."
        self.bluetooth_power = "Bluetooth"
        self.bluetooth_available_devices = "Appareils Disponibles"
        self.bluetooth_connect_failed = "Échec de la connexion à l'appareil"
        self.bluetooth_disconnect_failed = "Échec de la déconnexion de l'appareil"
        self.bluetooth_try_again = "Veuillez réessayer plus tard."

        # Display tab translations
        self.display_brightness = "Luminosité"
        self.display_blue_light = "Lumière Bleue"
        self.display_scale = 'Échelle'

        # Multiple displays
        self.display_multi_title = 'Disposition'
        self.display_mode_join = 'Joindre'
        self.display_mode_mirror = 'Miroir'
        self.display_mode_single = 'Unique'
        self.display_primary = 'Écran principal'
        self.display_active = 'Écran actif'
        self.display_builtin = 'Écran intégré'
        self.display_mirror_unavailable = "La recopie d'écran sous Sway nécessite l'installation de wl-mirror."
        self.display_keep_changes = "Conserver ces paramètres d'affichage ?"
        self.display_revert = 'Rétablir'
        self.display_keep = 'Conserver les modifications'
        self.display_reverting_in = 'Les paramètres seront rétablis dans {seconds} secondes.'
        self.display_orientation = "Orientation"
        self.display_default = "Par défaut"
        self.display_left = "Gauche"
        self.display_right = "Droite"
        self.display_inverted = "Inversé"

        # Volume tab translations
        self.volume_title = "Paramètres de Volume"
        self.volume_speakers = "Haut-parleurs"
        self.volume_tab_tooltip = "Paramètres des Haut-parleurs"
        self.volume_output_device = "Périphérique de Sortie"
        self.volume_speaker_volume = "Volume des Haut-parleurs"
        self.volume_mute_speaker = "Couper les Haut-parleurs"
        self.volume_unmute_speaker = "Activer les Haut-parleurs"
        self.volume_output_combo_tooltip = "Sélectionner le périphérique de sortie pour cette application"

        # Volume tab microphone translations
        self.microphone_tab_microphone = "Microphone"
        self.microphone_tab_input_device = "Périphérique d'Entrée"
        self.microphone_tab_volume = "Volume du Microphone"
        self.microphone_tab_mute_microphone = "Couper le Microphone"
        self.microphone_tab_unmute_microphone = "Activer le Microphone"
        self.microphone_tab_tooltip = "Paramètres du Microphone"

        # Volume tab App output translations
        self.app_output_title = "Sortie d'Applications"
        self.app_output_mute = "Couper"
        self.app_output_unmute = "Activer"
        self.app_output_tab_tooltip = "Paramètres de Sortie d'Applications"
        self.app_output_no_apps = "Aucune application ne joue de l'audio"
        self.app_output_dropdown_tooltip = "Sélectionner le périphérique de sortie pour cette application"

        # Volume tab App input translations
        self.app_input_title = "Entrée d'Applications"
        self.volume_configuration = 'Configuration'
        self.volume_configuration_tooltip = 'Choisir le profil de chaque périphérique audio'
        self.volume_no_cards = 'Aucun périphérique audio trouvé'
        self.app_input_mute = "Couper le Microphone pour cette application"
        self.app_input_unmute = "Activer le Microphone pour cette application"
        self.app_input_tab_tooltip = "Paramètres du Microphone d'Applications"
        self.app_input_no_apps = "Aucune application n'utilise le microphone"

        # WiFi tab translations
        self.wifi_refresh_tooltip = "Actualiser les Réseaux"
        self.wifi_power = "Wi-Fi"
        self.wifi_available = "Réseaux Disponibles"
        self.wifi_forget = "Oublier"
        self.wifi_share_title = "Partager le Réseau"
        self.wifi_share_scan = "Scanner pour se connecter"
        self.wifi_network_name = "Nom du Réseau"
        self.wifi_password = "Mot de passe"
        self.wifi_loading_networks = "Chargement des Réseaux..."

class Indonesian:
    """Indonesian language translation for the application"""

    def __init__(self):
        # app description
        self.msg_desc = "Panel kontrol GTK yang unik untuk Linux"
        self.msg_app_url = "https://github.com/husam212/microcontrol"
        self.msg_usage = "Penggunaan"

        # for args
        self.msg_args_help = "Mencetak pesan ini"
        self.msg_args_battery = "Memulai aplikasi dengan tab Baterai terbuka"
        self.msg_args_bluetooth = "Memulai aplikasi dengan tab Blueetooth terbuka"
        self.msg_args_display = "Memulai aplikasi the tab Tampilan terbuka"
        self.msg_args_force = "Memaksa aplikasi untuk mengecek semua ketergantungan"
        self.msg_args_volume = "Memulai aplikasi dengan tab Volume terbuka"
        self.msg_args_volume_v = "Juga memulai aplikasit dengan tab Volume terbuka"
        self.msg_args_wifi = "Memulai aplikasi dengan tab WiFI terbuka"

        self.msg_args_log = "Aplikasi akan mengeluarkan log ke sebuah file jika diberi sebuah file path,\n atau mengeluarkan output ke stdout jika diberikan nilai antara 0, dan 3."
        self.msg_args_redact = "Menyunting informasi sensitif dari log. (nama jaringan, ID perankat, dst.)"
        self.msg_args_size = "Menetapkan ukuran Window kustom"

        # commonly used
        self.connect = "Sambungkan"
        self.connected = "Tersambung"
        self.connecting = "Manyambungkan..."
        self.disconnect = "Putuskan sambungan"
        self.disconnected = "Tidak tersambung"
        self.disconnecting = "Memutuskan sambungan..."
        self.enable = "Aktifan"
        self.disable = "Nonaktifkan"
        self.close = "Tutup"
        self.show = "Tampilkan"
        self.loading = "Memuat..."
        self.loading_tabs = "Memuat tab..."

        # for tabs
        self.refresh = "Perbarui"
        self.allow = "Izinkan"
        self.block = "Blokir"
        self.msg_tab_battery = "Baterai"
        self.msg_tab_bluetooth = "Bluetooth"
        self.msg_tab_display = "Tampilan"
        self.msg_tab_volume = "Audio"
        self.msg_tab_wifi = "Wi-Fi"

        # Battery tab translations
        self.battery_power_saving = "Hemat Daya"
        self.battery_balanced = "Seimbang"
        self.battery_performance = "Performa"
        self.battery_no_batteries = "Tidak ada baterai yang terdeteksi"

        # Bluetooth tab translations
        self.bluetooth_scan_devices = "Pindai perangkat"
        self.bluetooth_scanning = "Memindai..."
        self.bluetooth_power = "Bluetooth"
        self.bluetooth_available_devices = "Perangkat yang tersedia"
        self.bluetooth_connect_failed = "Gagal untuk menyambung ke perangkat"
        self.bluetooth_disconnect_failed = "Gagal untuk memutus sambungan ke perangkat"
        self.bluetooth_try_again = "Mohon coba lagi."

        # Display tab translations
        self.display_brightness = "Kecerahan"
        self.display_blue_light = "Anti Radiasi"
        self.display_scale = 'Skala'

        # Multiple displays
        self.display_multi_title = 'Tata Letak'
        self.display_mode_join = 'Gabungkan'
        self.display_mode_mirror = 'Cermin'
        self.display_mode_single = 'Tunggal'
        self.display_primary = 'Layar Utama'
        self.display_active = 'Layar Aktif'
        self.display_builtin = 'Layar Bawaan'
        self.display_mirror_unavailable = 'Mencerminkan layar di Sway memerlukan wl-mirror terpasang.'
        self.display_keep_changes = 'Simpan pengaturan layar ini?'
        self.display_revert = 'Kembalikan'
        self.display_keep = 'Simpan Perubahan'
        self.display_reverting_in = 'Pengaturan akan dikembalikan dalam {seconds} detik.'
        self.display_orientation = "Orientasi"
        self.display_default = "Default"
        self.display_left = "Kiri"
        self.display_right = "Kanan"
        self.display_inverted = "Terbalik"

        # Volume tab translations
        self.volume_title = "Pengaturan Volume"
        self.volume_speakers = "Speaker"
        self.volume_tab_tooltip = "Pengatures Speaker"
        self.volume_output_device = "Perangkat Output"
        self.volume_speaker_volume = "Volume Speaker"
        self.volume_mute_speaker = "Bisukan Speaker"
        self.volume_unmute_speaker = "Menyalakan Speakers"
        self.volume_output_combo_tooltip = "Piling perangkat output untuk aplikasi ini"

        # Volume tab microphone translations
        self.microphone_tab_microphone = "Mikrofon"
        self.microphone_tab_input_device = "Perangkat Input"
        self.microphone_tab_volume = "Volume Mikrofon"
        self.microphone_tab_mute_microphone = "Bisukan Mikrofon"
        self.microphone_tab_unmute_microphone = "Nyalakn Microphone"
        self.microphone_tab_tooltip = "Pengaturan Mikrofon"

        # Volume tab App output translations
        self.app_output_title = "Output Aplikasi"
        self.app_output_mute = "Bisukan"
        self.app_output_unmute = "Nyalakan"
        self.app_output_tab_tooltip = "Pengaturan Output Aplikasi"
        self.app_output_no_apps = "Tidak ada aplikasi yang mengeluarkan suara"
        self.app_output_dropdown_tooltip = "Pilih perangkat output untuk aplikasi ini"

        # Volume tab App input translations
        self.app_input_title = "Input aplikasi"
        self.volume_configuration = 'Konfigurasi'
        self.volume_configuration_tooltip = 'Pilih profil untuk setiap perangkat suara'
        self.volume_no_cards = 'Tidak ada perangkat suara ditemukan'
        self.app_input_mute = "Bisukan Mikrofon untuk aplikasi ini"
        self.app_input_unmute = "Nyalakan Mikrofon untuk aplikasi ini"
        self.app_input_tab_tooltip = "Pengaturan Mikrofon Aplikasi"
        self.app_input_no_apps = "Tidak ada aplikasi yang menggunakan mikrofon"

        # WiFi tab translations
        self.wifi_refresh_tooltip = "Pindai Ulang Jaringan"
        self.wifi_power = "Wi-Fi"
        self.wifi_available = "Jaringan yang Tersedia"
        self.wifi_forget = "Lupakan"
        self.wifi_share_title = "Bagikan Jaringan"
        self.wifi_share_scan = "Pindai untuk menyambungkan"
        self.wifi_network_name = "Nama Jaringan"
        self.wifi_password = "Password"
        self.wifi_loading_networks = "Memuat Networks..."

class Turkish:
    """Uygulama için Türkçe dil çevirisi"""

    def __init__(self):
        # app description
        self.msg_desc = "Linux için şık bir GTK temalı kontrol paneli."
        self.msg_app_url = "https://github.com/husam212/microcontrol"
        self.msg_usage = "Kullanım"

        # for args
        self.msg_args_help = "Bu mesajı yazdırır"
        self.msg_args_battery = "Pil sekmesi açık olarak başlar"
        self.msg_args_bluetooth = "Bluetooth sekmesi açık olarak başlar"
        self.msg_args_display = "Ekran sekmesi açık olarak başlar"
        self.msg_args_force = "Tüm bağımlılıkların yüklü olmasını zorunlu kılar"
        self.msg_args_volume = "Ses sekmesi açık olarak başlar"
        self.msg_args_volume_v = "Ayrıca ses sekmesi açık olarak başlar"
        self.msg_args_wifi = "Wi-Fi sekmesi açık olarak başlar"
        self.msg_args_log = "Program bir dosya yolu verilirse log dosyasına yazar,\n veya 0 ile 3 arasında bir değer verilirse stdout'a yazar."
        self.msg_args_redact = "Loglardan hassas bilgileri gizle (ağ adları, cihaz kimlikleri, vb.)"
        self.msg_args_size = "Özel bir pencere boyutu ayarlar"

        # commonly used
        self.connect = "Bağlan"
        self.connected = "Bağlı"
        self.connecting = "Bağlanıyor..."
        self.disconnect = "Bağlantıyı Kes"
        self.disconnected = "Bağlantı Kesildi"
        self.disconnecting = "Bağlantı Kesiliyor..."
        self.enable = "Etkinleştir"
        self.disable = "Devre Dışı Bırak"
        self.close = "Kapat"
        self.show = "Göster"
        self.loading = "Yükleniyor..."
        self.loading_tabs = "Sekmeler yükleniyor..."

        # for tabs
        self.refresh = "Yenile"
        self.allow = "İzin Ver"
        self.block = "Engelle"
        self.msg_tab_battery = "Pil"
        self.msg_tab_bluetooth = "Bluetooth"
        self.msg_tab_display = "Ekran"
        self.msg_tab_volume = "Ses"
        self.msg_tab_wifi = "Wi-Fi"

        # Battery tab translations
        self.battery_power_saving = "Güç Tasarrufu"
        self.battery_balanced = "Dengeli"
        self.battery_performance = "Performans"
        self.battery_no_batteries = "Pil algılanmadı"

        # Bluetooth tab translations
        self.bluetooth_scan_devices = "Cihazları Tara"
        self.bluetooth_scanning = "Taranıyor..."
        self.bluetooth_power = "Bluetooth"
        self.bluetooth_available_devices = "Mevcut Cihazlar"
        self.bluetooth_connect_failed = "Cihaza bağlanılamadı"
        self.bluetooth_disconnect_failed = "Cihaz bağlantısı kesilemedi"
        self.bluetooth_try_again = "Lütfen daha sonra tekrar deneyin."

        # Display tab translations
        self.display_brightness = "Parlaklık"
        self.display_blue_light = "Mavi Işık"
        self.display_scale = 'Ölçek'

        # Multiple displays
        self.display_multi_title = 'Düzen'
        self.display_mode_join = 'Birleştir'
        self.display_mode_mirror = 'Yansıt'
        self.display_mode_single = 'Tek'
        self.display_primary = 'Birincil Ekran'
        self.display_active = 'Etkin Ekran'
        self.display_builtin = 'Dahili Ekran'
        self.display_mirror_unavailable = "Sway'de yansıtma için wl-mirror kurulu olmalıdır."
        self.display_keep_changes = 'Bu ekran ayarları korunsun mu?'
        self.display_revert = 'Geri Al'
        self.display_keep = 'Değişiklikleri Koru'
        self.display_reverting_in = 'Ayarlar {seconds} saniye içinde geri alınacak.'
        self.display_orientation = "Yönlendirme"
        self.display_default = "Varsayılan"
        self.display_left = "Sol"
        self.display_right = "Sağ"
        self.display_inverted = "Ters"
        self.display_rotation = "Döndürme Seçenekleri"
        self.display_simple_rotation = "Hızlı Döndürme"
        self.display_specific_orientation = "Belirli Yön"
        self.display_flip_controls = "Ekran Çevirme"
        self.display_rotate_cw = "Saat yönünde döndür"
        self.display_rotate_ccw = "Saat yönünün tersine döndür"
        self.display_rotation_help = "Döndürme işlemi hemen uygulanır. Onaylamazsanız 10 saniye içinde eski haline döner."

        # Volume tab translations
        self.volume_title = "Ses Ayarları"
        self.volume_speakers = "Hoparlörler"
        self.volume_tab_tooltip = "Hoparlör Ayarları"
        self.volume_output_device = "Çıkış Aygıtı"
        self.volume_speaker_volume = "Hoparlör Sesi"
        self.volume_mute_speaker = "Hoparlörü Sessize Al"
        self.volume_unmute_speaker = "Hoparlörü Sesli Yap"
        self.volume_output_combo_tooltip = "Bu uygulama için çıkış cihazını seçin"

        # Volume tab microphone translations
        self.microphone_tab_microphone = "Mikrofon"
        self.microphone_tab_input_device = "Giriş Aygıtı"
        self.microphone_tab_volume = "Mikrofon Sesi"
        self.microphone_tab_mute_microphone = "Mikrofonu Sessize Al"
        self.microphone_tab_unmute_microphone = "Mikrofonu Sesli Yap"
        self.microphone_tab_tooltip = "Mikrofon Ayarları"

        # Volume tab App output translations
        self.app_output_title = "Uygulama Çıkışı"
        self.app_output_mute = "Sessize Al"
        self.app_output_unmute = "Sesi Aç"
        self.app_output_tab_tooltip = "Uygulama Çıkış Ayarları"
        self.app_output_no_apps = "Ses çalan uygulama yok"
        self.app_output_dropdown_tooltip = "Bu uygulama için çıkış cihazını seçin"

        # Volume tab App input translations
        self.app_input_title = "Uygulama Girişi"
        self.volume_configuration = 'Yapılandırma'
        self.volume_configuration_tooltip = 'Her ses aygıtının profilini seçin'
        self.volume_no_cards = 'Ses aygıtı bulunamadı'
        self.app_input_mute = "Bu uygulama için mikrofonu sessize al"
        self.app_input_unmute = "Bu uygulama için mikrofonu aç"
        self.app_input_tab_tooltip = "Uygulama Mikrofon Ayarları"
        self.app_input_no_apps = "Mikrofon kullanan uygulama yok"

        # WiFi tab translations
        self.wifi_refresh_tooltip = "Ağları Yenile"
        self.wifi_power = "Wi-Fi"
        self.wifi_available = "Mevcut Ağlar"
        self.wifi_forget = "Unut"
        self.wifi_share_title = "Ağı Paylaş"
        self.wifi_share_scan = "Bağlanmak için tarayın"
        self.wifi_network_name = "Ağ Adı"
        self.wifi_password = "Parola"
        self.wifi_loading_networks = "Ağlar Yükleniyor..."

def _map_system_lang_to_code(system_lang: str, logger: Optional[Logger] = None) -> str:
    """Helper function to map system language to supported code and optionally log mapping"""
    if system_lang.startswith("es"):
        if logger:
            logger.log(
                LogLevel.Info, f"System language '{system_lang}' mapped to Spanish (es)")
        return "es"
    if system_lang.startswith("it"):
        if logger:
            logger.log(
                LogLevel.Info, f"System language '{system_lang}' mapped to Italian (it)")
        return "it"
    elif system_lang.startswith("pt"):
        if logger:
            logger.log(
                LogLevel.Info, f"System language '{system_lang}' mapped to Portuguese (pt)")
        return "pt"
    elif system_lang.startswith("fr"):
        if logger:
            logger.log(
                LogLevel.Info, f"System language '{system_lang}' mapped to French (fr)")
        return "fr"
    elif system_lang.startswith("id"):
        if logger:
            logger.log(
                LogLevel.Info, f"System language '{system_lang}' mapped to Indonesian (id)")
        return "id"
    elif system_lang.startswith("tr"):
        if logger:
            logger.log(
                LogLevel.Info, f"System language '{system_lang}' mapped to Turkish (tr)")
        return "tr"
    elif system_lang.startswith("ru"):
        if logger:
            logger.log(
                LogLevel.Info, f"System language '{system_lang}' mapped to Russian (ru)")
        return "ru"
    elif system_lang.startswith("de"):
        if logger:
            logger.log(
                LogLevel.Info, f"System language '{system_lang}' mapped to German (de)")
        return "de"
    else:
        if logger:
            logger.log(
                LogLevel.Info, f"System language '{system_lang}' not supported, falling back to English (en)")
        return "en"

def get_translations(logging: Optional[Logger] = None, lang: str = "en") -> Translation:
    """Load the language according to the selected language

    Args:
        lang (str): Language code ('en', 'es', 'it', 'pt', 'fr', 'id', 'tr', 'de', 'default')
                   'default' will use the system's $LANG environment variable

    Returns:
        Translation: Translation object for the selected language
    """
    # Handle 'default' option by checking system's LANG environment variable
    if lang == "default":
        env_lang = os.environ.get("LANG")
        if env_lang is None:
            # No LANG env var set, fall back to English immediately
            system_lang_code = "en"
            if logging:
                logging.log(
                    LogLevel.Info, "Environment variable LANG not set, falling back to English")
        else:
            # LANG env var exists
            parts = env_lang.split("_")
            system_lang_code = parts[0].lower()
            if logging:
                logging.log(
                    LogLevel.Info, f"Using system language: {system_lang_code} from $LANG={env_lang}")
        lang = _map_system_lang_to_code(system_lang_code, logging)

    if logging:
        logging.log(LogLevel.Info, f"Using language: {lang}")

    match lang:
        case "ru":
            return Russian()
        case "es":
            return Spanish()
        case "it":
            return Italian()
        case "pt":
            return Portuguese()
        case "fr":
            return French()
        case "id":
            return Indonesian()
        case "tr":
            return Turkish()
        case "de":
            return German()
        case _:
            return English()
