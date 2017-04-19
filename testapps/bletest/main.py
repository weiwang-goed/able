"""Connect to "KivyBLETest" server and test various BLE functions
"""
import time

from able import GATT_SUCCESS, Advertisement, BluetoothDispatcher
from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
from kivy.properties import BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout

Config.set('kivy', 'log_level', 'debug')
Config.set('kivy', 'log_enable', '1')


class MainLayout(BoxLayout):
    pass


class BLETestApp(App):
    ble = BluetoothDispatcher()
    state = StringProperty('')
    test_string = StringProperty('')
    notification_value = StringProperty('')
    counter_value = StringProperty('')
    increment_count_value = StringProperty('')
    incremental_interval = StringProperty('100')
    counter_max = StringProperty('128')
    counter_value = StringProperty('')
    counter_state = StringProperty('')
    counter_total_time = StringProperty('')
    queue_timeout_enabled = BooleanProperty(True)
    queue_timeout = StringProperty('1000')

    uids = {
        'string': '0d01',
        'counter_reset': '0d02',
        'counter_increment': '0d03',
        'counter_read': '0d04',
        'notifications': '0d05'
    }

    def build(self):
        return MainLayout()

    def on_pause(self):
        return True

    def on_resume(self):
        pass

    def init(self, *args, **kwargs):
        self.set_queue_settings()
        self.ble.bind(on_device=self.on_device)
        self.ble.bind(on_scan_started=self.on_scan_started)
        self.ble.bind(on_scan_completed=self.on_scan_completed)
        self.ble.bind(
            on_connection_state_change=self.on_connection_state_change)
        self.ble.bind(on_services=self.on_services)
        self.ble.bind(on_characteristic_read=self.on_characteristic_read)
        self.ble.bind(on_characteristic_changed=self.on_characteristic_changed)

    def start_scan(self, *args, **kwargs):
        if not self.state:
            self.init()
        self.state = 'scan_start'
        self.ble.start_scan()

    def on_scan_started(self, ble, success):
        self.state = 'scan' if success else 'scan_error'

    def on_device(self, ble, device, rssi, advertisement):
        if self.state != 'scan':
            return
        for ad in advertisement:
            if ad.ad_type == Advertisement.ad_types.complete_local_name:
                if str(ad.data) == 'KivyBLETest':
                    self.device = device
                    self.state = 'found'
                    self.ble.stop_scan()

    def on_scan_completed(self, ble):
        if self.device:
            self.ble.connect_gatt(self.device)

    def on_connection_state_change(self, ble, status, state):
        if status == GATT_SUCCESS:
            if state:
                self.ble.discover_services()
            else:
                self.state = 'disconnected'
        else:
            self.state = 'connection_error'

    def on_services(self, ble, status, services):
        if status != GATT_SUCCESS:
            self.state = 'services_error'
            return
        self.state = 'connected'
        self.services = services
        self.read_test_string(ble)
        self.characteristics = {
            'counter_increment': self.services.search(
                self.uids['counter_increment']),
            'counter_reset': self.services.search(
                self.uids['counter_reset']),
        }

    def read_test_string(self, ble):
        characteristic = self.services.search(self.uids['string'])
        if characteristic:
            ble.read_characteristic(characteristic)
        else:
            self.test_string = 'not found'

    def read_remote_counter(self, *args, **kwargs):
        characteristic = self.services.search(self.uids['counter_read'])
        if characteristic:
            self.ble.read_characteristic(characteristic)
        else:
            self.counter_value = 'error'

    def enable_notifications(self, enable):
        if enable:
            self.notification_value = '0'
        characteristic = self.services.search(self.uids['notifications'])
        if characteristic:
            self.ble.enable_notifications(characteristic, enable)
        else:
            self.notification_value = 'error'

    def enable_counter(self, enable):
        if enable:
            self.counter_state = 'init'
            interval = int(self.incremental_interval) * .001
            Clock.schedule_interval(self.counter_next, interval)
        else:
            Clock.unschedule(self.counter_next)
            if self.counter_state != 'stop':
                self.counter_state = 'stop'
                self.read_remote_counter()

    def counter_next(self, *args, **kwargs):
        if self.counter_state == 'init':
            self.counter_started_time = time.time()
            self.counter_total_time = ''
            self.reset_remote_counter()
            self.increment_remote_counter()
        elif self.counter_state == 'enabled':
            if int(self.increment_count_value) < int(self.counter_max):
                self.increment_remote_counter()
            else:
                self.enable_counter(False)

    def reset_remote_counter(self):
        self.increment_count_value = '0'
        self.counter_value = ''
        self.ble.write_characteristic(self.characteristics['counter_reset'],
                                      '1')
        self.counter_state = 'enabled'

    def on_characteristic_read(self, ble, characteristic, status):
        uuid = characteristic.getUuid().toString()
        if self.uids['string'] in uuid:
            self.update_string_value(characteristic, status)
        elif self.uids['counter_read'] in uuid:
            self.counter_total_time = str(
                time.time() - self.counter_started_time)
            self.update_counter_value(characteristic, status)

    def update_string_value(self, characteristic, status):
        result = 'ERROR'
        if status == GATT_SUCCESS:
            value = characteristic.getStringValue(0)
            if value == 'test':
                result = 'OK'
        self.test_string = result

    def increment_remote_counter(self):
        characteristic = self.characteristics['counter_increment']
        self.ble.write_characteristic(characteristic, '1')
        prev_value = int(self.increment_count_value)
        self.increment_count_value = str(prev_value + 1)

    def update_counter_value(self, characteristic, status):
        if status == GATT_SUCCESS:
            self.counter_value = characteristic.getStringValue(0)
        else:
            self.counter_value = 'ERROR'

    def set_queue_settings(self):
        self.ble.set_queue_timeout(None if not self.queue_timeout_enabled
                                   else int(self.queue_timeout) * .001)

    def on_characteristic_changed(self, ble, characteristic):
        uuid = characteristic.getUuid().toString()
        if self.uids['notifications'] in uuid:
            prev_value = self.notification_value
            value = int(characteristic.getStringValue(0))
            if (prev_value == 'error') or (value != int(prev_value) + 1):
                value = 'error'
            self.notification_value = str(value)


if __name__ == '__main__':
    BLETestApp().run()
