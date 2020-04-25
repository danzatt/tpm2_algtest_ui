#!/usr/bin/python3

from collections import deque
from enum import Enum, auto

from threading import Thread, Lock
import subprocess
import fcntl
import os
import csv
import glob
import requests
import json
import datetime
import zipfile

from shutil import copyfile
from uuid import uuid4
from tempfile import mkdtemp

from yui import YUI
from yui import YEvent

IMAGE_TAG = 'tpm2-algtest-ui v1.0'
RESULT_PATH = "/mnt/algtest"


class ISUploader:
    def __init__(self, user_agent, uco):
        self.user_agent = user_agent
        self.uco = uco
        self.headers = {
            'User-Agent': self.user_agent
        }

        self.params = (
            ('vybos_vzorek_last', ''),
            ('vybos_vzorek', self.uco),
            ('vybos_hledej', 'Vyhledat osobu')
        )

    def upload(self, filename, description="", mail_text=""):
        try:
            files = {
                'quco': (None, self.uco),
                'vlsozav': (None, 'najax'),
                'ajax-upload': (None, 'ajax'),
                'FILE_1': (filename, open(filename, 'rb')),
                'A_NAZEV_1': (None, filename),
                'A_POPIS_1': (None, description),
                'TEXT_MAILU': (None, mail_text),
            }

            response = requests.post('https://is.muni.cz/dok/depository_in', headers=self.headers, params=self.params, files=files)
            json_response = json.loads(response.content.decode("utf-8"))
            if json_response["uspech"] != 1:
                return False
        except:
            return False
        return True


class TestResultCollector:
    def __init__(self, outdir, email):
        self.outdir = outdir
        self.detail_dir = os.path.join(self.outdir, 'detail')
        self.zip_path = None
        self.email = email

    def create_result_files(self):
        manufacturer, vendor_str, fw = self.get_tpm_id()
        file_name = manufacturer + '_' + vendor_str + '_' + fw + '.csv'

        os.makedirs(os.path.join(self.outdir, 'results'), exist_ok=True)
        with open(os.path.join(self.outdir, 'results', file_name), 'w') as support_file:
            self.write_header(support_file, manufacturer, vendor_str, fw)
            self.write_support_file(support_file)

        os.makedirs(os.path.join(self.outdir, 'performance'), exist_ok=True)
        with open(os.path.join(self.outdir, 'performance', file_name), 'w') as perf_file:
            self.write_header(perf_file, manufacturer, vendor_str, fw)
            self.write_perf_file(perf_file)

    def write_header(self, file, manufacturer, vendor_str, fw):
        file.write(f'Tested and provided by;{self.email}\n')
        file.write(f'Execution date/time; {datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")}\n')
        file.write(f'Manufacturer; {manufacturer}\n')
        file.write(f'Vendor string; {vendor_str}\n')
        file.write(f'Firmware version; {fw}\n')
        file.write(f'Image tag; {IMAGE_TAG}\n')
        file.write(f'TPM devices; {";".join(glob.glob("/dev/tpm*"))}\n\n')

    def get_tpm_id(self):
        def get_val(line):
            return line[line.find('0x') + 2:-1]

        manufacturer = ''
        vendor_str = ''
        fw = ''
        qt_properties = os.path.join(self.detail_dir, 'Quicktest_properties-fixed.txt')
        if os.path.isfile(qt_properties):
            with open(os.path.join(self.detail_dir, 'Quicktest_properties-fixed.txt'), 'r') as properties_file:
                read_vendor_str = False
                read_manufacturer_str = False
                read_fw1_str = False
                read_fw2_str = False
                fw1 = ''
                fw2 = ''
                for line in properties_file:
                    if read_vendor_str:
                        val = get_val(line)
                        if len(val) % 2 != 0:
                            val = "0" + val

                        vendor_str += bytearray.fromhex(val).decode()
                        read_vendor_str = False
                    elif read_manufacturer_str:
                        val = get_val(line)
                        if len(val) % 2 != 0:
                            val = "0" + val

                        manufacturer = bytearray.fromhex(val).decode()
                        read_manufacturer_str = False
                    elif line.startswith('TPM2_PT_MANUFACTURER'):
                        read_manufacturer_str = True
                    elif line.startswith('TPM2_PT_FIRMWARE_VERSION_1'):
                        read_fw1_str = True
                    elif read_fw1_str:
                        fw1 = line[line.find('0x') + 2:-1]
                        read_fw1_str = False
                    elif line.startswith('TPM2_PT_FIRMWARE_VERSION_2'):
                        read_fw2_str = True
                    elif read_fw2_str:
                        fw2 = line[line.find('0x') + 2:-1]
                        read_fw2_str = False
                    elif line.startswith('TPM2_PT_VENDOR_STRING_'):
                        read_vendor_str = True
                try:
                    fw = str(int(fw1[0:4], 16)) + '.' + str(int(fw1[4:8], 16)) + '.' + str(int(fw2[0:4], 16)) + '.' + str(int(fw2[4:8], 16))
                except:
                    fw = ""

        manufacturer = manufacturer.replace('\0', '')
        vendor_str = vendor_str.replace('\0', '')
        return manufacturer, vendor_str, fw

    def write_support_file(self, support_file):
            qt_properties = os.path.join(self.detail_dir, 'Quicktest_properties-fixed.txt')
            if os.path.isfile(qt_properties):
                support_file.write('\nQuicktest_properties-fixed\n')
                with open(os.path.join(self.detail_dir, 'Quicktest_properties-fixed.txt'), 'r') as infile:
                    properties = ""
                    for line in infile:
                        if line.startswith('  as UINT32:'):
                            continue
                        if line.startswith('  as string:'):
                            line = line[line.find('"'):]
                            properties = properties[:-1] + '\t' + line
                        else:
                            properties += line.replace(':', ';')
                    support_file.write(properties)

            qt_algorithms = os.path.join(self.detail_dir, 'Quicktest_algorithms.txt')
            if os.path.isfile(qt_algorithms):
                support_file.write('\nQuicktest_algorithms\n')
                with open(qt_algorithms, 'r') as infile:
                    for line in infile:
                        if line.startswith('TPMA_ALGORITHM'):
                            line = line[line.find('0x'):]
                            line = line[:line.find(' ')]
                            support_file.write(line + '\n')

            qt_commands = os.path.join(self.detail_dir, 'Quicktest_commands.txt')
            if os.path.isfile(qt_commands):
                support_file.write('\nQuicktest_commands\n')
                with open(qt_commands, 'r') as infile:
                    for line in infile:
                        if line.startswith('  commandIndex:'):
                            line = line[line.find('0x'):]
                            support_file.write(line)

            qt_ecc_curves = os.path.join(self.detail_dir, 'Quicktest_ecc-curves.txt')
            if os.path.isfile(qt_ecc_curves):
                support_file.write('\nQuicktest_ecc-curves\n')
                with open(os.path.join(self.detail_dir, 'Quicktest_ecc-curves.txt'), 'r') as infile:
                    for line in infile:
                        line = line[line.find('(') + 1:line.find(')')]
                        support_file.write(line + '\n')

    def write_perf_file(self, perf_file):
        perf_csvs = glob.glob(os.path.join(self.detail_dir, 'Perf_*.csv'))
        perf_csvs.sort()
        command = ''
        for filepath in perf_csvs:
            filename = os.path.basename(filepath)
            params_idx = filename.find(':')
            suffix_idx = filename.find('.csv')
            new_command = filename[5:suffix_idx if params_idx == -1 else params_idx]
            params = filename[params_idx+1:suffix_idx].split('_')
            if new_command != command:
                command = new_command
                perf_file.write('TPM2_' + command + '\n\n')

            if command == 'GetRandom':
                perf_file.write(f'Data length (bytes):;32\n')
            elif command in [ 'Sign', 'VerifySignature', 'RSA_Encrypt', 'RSA_Decrypt' ]:
                perf_file.write(f'Key parameters:;{params[0]} {params[1]};Scheme:;{params[2]}\n')
            elif command == 'EncryptDecrypt':
                perf_file.write(f'Algorithm:;{params[0]};Key length:;{params[1]};Mode:;{params[2]};Encrypt/decrypt?:;{params[3]};Data length (bytes):;256\n')
            elif command == 'HMAC':
                perf_file.write('Hash algorithm:;SHA-256;Data length (bytes):;256\n')
            elif command == 'Hash':
                perf_file.write(f'Hash algorithm:;{params[0]};Data length (bytes):;256\n')
            else:
                perf_file.write(f'Key parameters:;{" ".join(params)}\n')

            with open(filepath, 'r') as infile:
                avg_op, min_op, max_op, total, success, fail, error = self.compute_stats(infile)
                perf_file.write(f'operation stats (ms/op):;avg op:;{avg_op:.2f};min op:;{min_op:.2f};max op:;{max_op:.2f}\n')
                perf_file.write(f'operation info:;total iterations:;{total};successful:;{success};failed:;{fail};error:;{"None" if not error else error}\n\n')

    def compute_stats(self, infile, *, rsa2048=False):
        ignore = 5 if rsa2048 else 0
        success, fail, sum_op, min_op, max_op, avg_op = 0, 0, 0, 10000000000, 0, 0
        error = None
        for line in infile:
            if line.startswith('duration'):
                continue
            if ignore > 0:
                ignore -= 1
                continue
            t, rc = line.split(',')[:2]
            rc = rc.replace(' ', '')
            rc = rc.replace('\n', '')
            if rc == '0000':
                success += 1
            else:
                error = rc
                fail += 1
                continue
            t = float(t)
            sum_op += t
            if t > max_op: max_op = t
            if t < min_op: min_op = t
        total = success + fail
        if success != 0:
            avg_op = (sum_op / success)
        else:
            min_op = 0

        return avg_op * 1000, min_op * 1000, max_op * 1000, total, success, fail, error # sec -> ms

    def zip(self):
        self.zip_path = self.outdir + '.zip'
        zipf = zipfile.ZipFile(self.zip_path, 'w', zipfile.ZIP_DEFLATED)
        for root, _, files in os.walk(self.outdir):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, file_path[len(self.outdir):])
        zipf.close()

    def generate_zip(self):
        self.create_result_files()
        self.zip()
        return self.zip_path


class TestType(Enum):
    PERFORMANCE = auto()
    KEYGEN = auto()


class StoreType(Enum):
    STORE_USB = auto()
    UPLOAD = auto()
    CANCEL = auto()

class AlgtestTestRunner(Thread):
    def __init__(self, out_dir):
        super().__init__(name="AlgtestTestRunner")
        self.out_dir = out_dir
        self.detail_dir = os.path.join(self.out_dir, 'detail')
        self.cmd = ["tpm2_algtest", '--outdir=' + self.detail_dir, "-s"]

        self.percentage = 0
        self.text = []
        self.info_lock = Lock()
        self.info_changed = True

        self.tests_to_run = deque()
        self.algtest_proc = None
        self.shall_stop = False

        self.test_finished = False

        self.uploader = ISUploader("tpm2-algtest-ui", 469348)

        self.email = None

    def run(self):
        total_tests = len(self.tests_to_run)
        current_test = 1

        self.append_text("Collecting basic TPM info...")
        code = self.run_quicktest()
        if code != 0:
            self.append_text("Cannot collect TPM info. Do you have TPM present and enabled in BIOS?")
            return code

        while self.tests_to_run and not self.get_shall_stop():
            test = self.tests_to_run.popleft()
            os.makedirs(self.detail_dir, exist_ok=True)

            self.append_text(f"Running the {test.name.lower()} test... ({current_test}/{total_tests})")
            if test == TestType.PERFORMANCE:
                self.algtest_proc = subprocess.Popen(self.cmd + ["perf"], stdout=subprocess.PIPE)
            elif test == TestType.KEYGEN:
                self.algtest_proc = subprocess.Popen(self.cmd + ["keygen"], stdout=subprocess.PIPE)

            fd = self.algtest_proc.stdout.fileno()
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

            self.monitor_algtest(current_test, total_tests)

            if self.algtest_proc.poll() is None:
                if self.get_shall_stop():
                    self.algtest_proc.terminate()

                print("Waiting for the tpm2_algtest process to finish...")
                self.append_text("Waiting for the tpm2_algtest process to finish...")
                self.algtest_proc.wait()

            code = self.algtest_proc.returncode
            if code != 0:
                if not self.get_shall_stop():
                    print("The tpm2_algtest process failed. Please try to re-run the test.")
                    self.append_text("The tpm2_algtest process failed. Please try to re-run the test.")
                return code

            self.append_text(f"The {test.name.lower()} test finished")

            if test == TestType.KEYGEN and not self.get_shall_stop():
                self.append_text(f"Computing RSA private keys...")
                self.keygen_post()

            current_test += 1

        if self.get_shall_stop():
            self.append_text("Stop requested.")
            return

        self.append_text("All tests finished successfully.")
        self.append_text("Please wait, collecting results...")
        result_collector = TestResultCollector(self.out_dir, self.get_mail())
        result_collector.generate_zip()
        self.append_text("Results collected.")
        self.set_percentage(100)

        with self.info_lock:
            self.test_finished = True

    def store_results(self, store_type):
        result_zip = self.out_dir + '.zip'
        zip_filename = os.path.basename(result_zip)

        if not os.path.isdir(RESULT_PATH):
            if os.system("mkdir -p " + RESULT_PATH + " && mount /dev/disk/by-label/ALGTEST_RES " + RESULT_PATH) == 0:
                self.append_text("Successfully mounted ALGTEST_RES partition")

        if os.path.isdir(RESULT_PATH):
            try:
                copyfile(result_zip, os.path.join(RESULT_PATH, zip_filename))
                self.append_text("Copied to USB. File name: " + zip_filename)
            except:
                self.append_text("Failed to copy to USB.")
        else:
            self.append_text("ALGTEST_RES partition is not mounted. Can not store on USB.")

        if store_type == StoreType.UPLOAD:
            self.append_text("Uploading results...")
            if self.uploader.upload(result_zip):
                self.append_text("Results uploaded successfully.")
            else:
                self.append_text("Results upload failed.")

    def set_mail(self, email):
        with self.info_lock:
            self.email = email

    def get_mail(self):
        with self.info_lock:
            return self.email

    def is_finished(self):
        with self.info_lock:
            return self.test_finished

    def get_info_changed(self):
        with self.info_lock:
            if not self.info_changed:
                return False

            self.info_changed = False
            return True

    def monitor_algtest(self, current_test, total_tests):
        if self.algtest_proc is None:
            return

        while self.algtest_proc.poll() is None and not self.get_shall_stop():
            line = self.algtest_proc.stdout.readline().decode("ascii")
            while line != "" and not self.get_shall_stop():
                if 2 < len(line) <= 5 and line[-2] == "%":
                    current_test_percentage = int(line[:-2]) / 100
                    absolute_percentage = ((current_test - 1) / total_tests) + (1/total_tests) * current_test_percentage
                    self.set_percentage(int(absolute_percentage * 100))
                else:
                    self.append_text(line[:-1])
                line = self.algtest_proc.stdout.readline().decode("ascii")

    def append_text(self, text):
        with self.info_lock:
            self.text.append(text)
            self.info_changed = True

    def get_text(self):
        with self.info_lock:
            return "\n".join(self.text[-100:])

    def set_percentage(self, value):
        with self.info_lock:
            self.percentage = value
            self.info_changed = True

    def get_percentage(self):
        with self.info_lock:
            return self.percentage

    def stop(self):
        with self.info_lock:
            self.shall_stop = True

    def get_shall_stop(self):
        with self.info_lock:
            return self.shall_stop

    def keygen_post(self):
        for filename in glob.glob(os.path.join(self.detail_dir, 'Keygen_RSA_*_keys.csv')):
            self.compute_rsa_privates(filename)

    def run_quicktest(self):
        os.makedirs(self.detail_dir, exist_ok=True)

        run_command = ['tpm2_getcap']

        getcap_proc = subprocess.Popen(["tpm2_getcap", "-v"], stdout=subprocess.PIPE)
        line = getcap_proc.stdout.readline().decode("ascii")
        version_begin = line.find('version="') + len('version="')
        version_end = line.find('"', version_begin)
        version = line[version_begin:version_end].split(".")
        version = list(map(int, version))

        # newer versions take category directly as an argument, older need -c
        if version < [4, 0, 0]:
            run_command.append("-c")

        categories = ['algorithms', 'commands', 'properties-fixed', 'properties-variable', 'ecc-curves', 'handles-persistent']
        for category in categories:
            with open(os.path.join(self.detail_dir, f'Quicktest_{category}.txt'), 'w') as outfile:
                ret = subprocess.run(run_command + [category], stdout=outfile).returncode
                if ret != 0:
                    return ret
        return 0

    def schedule_test(self, test):
        self.tests_to_run.append(test)

    def terminate(self):
        self.stop()
        if self.is_alive():
            self.join()

        if self.algtest_proc is not None and self.algtest_proc.poll() is None:
            self.algtest_proc.terminate()

    def compute_rsa_privates(self, filename):
        def extended_euclidean(a, b):
            x0, x1, y0, y1 = 0, 1, 1, 0
            while a != 0:
                q, b, a = b // a, a, b % a
                y0, y1 = y1, y0 - q * y1
                x0, x1 = x1, x0 - q * x1
            return b, x0, y0

        def mod_exp(base, exp, n):
            res = 1
            base %= n
            while exp > 0:
                if exp % 2 == 1:
                    res *= base
                    res %= n
                exp //= 2
                base *= base
                base %= n
            return res

        def compute_row(row):
            try:
                n = int(row['n'], 16)
                e = int(row['e'], 16)
                p = int(row['p'], 16)
            except Exception:
                print(f"Cannot compute row {row['id']}")
                return
            q = n // p
            totient = (p - 1) * (q - 1)
            _, d, _ = extended_euclidean(e, totient)
            d %= totient

            message = 12345678901234567890
            assert mod_exp(mod_exp(message, e, n), d, n) == message, \
                f"something went wrong (row {row['id']})"

            row['q'] = '%X' % q
            row['d'] = '%X' % d

        rows = []
        with open(filename) as infile:
            reader = csv.DictReader(infile, delimiter=';')
            for row in reader:
                rows.append(row)

        for row in rows:
            compute_row(row)

        with open(filename, 'w') as outfile:
            writer = csv.DictWriter(
                    outfile, delimiter=';', fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for row in rows:
                writer.writerow(row)


class TPM2AlgtestUI:
    def __init__(self):
        self.out_dir = os.path.join(mkdtemp(), "tpm2-algtest", "algtest_result_" + str(uuid4()))
        os.makedirs(self.out_dir, exist_ok=True)
        self.algtest_runner = AlgtestTestRunner(self.out_dir)

        self.dialog = None
        self.vbox = None
        self.group = None
        self.type_box = None
        self.both_button = None
        self.keygen_button = None
        self.perf_button = None
        self.primary_box = None
        self.progress_bar = None
        self.text = None
        self.bottom_buttons = None
        self.run_button = None
        self.stop_button = None
        self.exit_button = None
        self.store_button = None
        self.mail_box = None

        self.popup = None
        self.yesNoButtons = None
        self.popup_upload = None
        self.popup_usb = None
        self.popup_cancel = None

    def construct_ui(self):
        YUI.application().setApplicationIcon("/usr/share/icons/hicolor/256x256/apps/tpm2-algtest.png")
        YUI.application().setProductName("TPM2 algorithms test")
        YUI.application().setApplicationTitle("TPM2 algorithms test")
        self.dialog = YUI.widgetFactory().createMainDialog()

        self.vbox = YUI.widgetFactory().createVBox(self.dialog)
        self.hbox = YUI.widgetFactory().createHBox(self.vbox)
        YUI.widgetFactory().createLabel(self.hbox, "Select the test type")

        self.group = YUI.widgetFactory().createRadioButtonGroup(self.hbox)
        self.type_box = YUI.widgetFactory().createHBox(self.group)

        self.keygen_button = YUI.widgetFactory().createRadioButton(self.type_box, "&keygen")
        self.group.addRadioButton(self.keygen_button)

        self.perf_button = YUI.widgetFactory().createRadioButton(self.type_box, "&perf")
        self.group.addRadioButton(self.perf_button)

        self.both_button = YUI.widgetFactory().createRadioButton(self.type_box, "&both")
        self.both_button.setValue(True)
        self.group.addRadioButton(self.both_button)

        self.primary_box = YUI.widgetFactory().createVBox(self.vbox)

        self.mail_box = YUI.widgetFactory().createHBox(self.vbox)
        YUI.widgetFactory().createLabel(self.mail_box, "Your email (optional): ")
        self.email_field = YUI.widgetFactory().createInputField(self.mail_box, "")

        YUI.widgetFactory().createLabel(self.vbox, "We may need to contact you in the future if we need more info. "\
            "The email address won't be shared with anybody and you will not receive any advertisement.")


        self.progress_bar = YUI.widgetFactory().createProgressBar(self.primary_box, "Test progress", 100)
        self.progress_bar.setValue(0)

        self.text = YUI.widgetFactory().createRichText(self.vbox, "", True)
        self.text.setText("Select the test type and press RUN to start.")
        self.text.setAutoScrollDown(True)

        self.bottom_buttons = YUI.widgetFactory().createHBox(self.vbox)
        self.run_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Start")
        self.dialog.setDefaultButton(self.run_button)
        self.stop_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Stop")
        self.exit_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Exit")

        shutdown_highlight_box = YUI.widgetFactory().createHBox(self.bottom_buttons)
        self.shutdown_button = YUI.widgetFactory().createPushButton(shutdown_highlight_box, "&Shutdown PC")
        self.dialog.highlight(shutdown_highlight_box)

        self.dialog.open()
        self.dialog.activate()

    def popup_ask_upload(self):
        self.popup = YUI.widgetFactory().createPopupDialog()

        popup_vbox = YUI.widgetFactory().createVBox(self.popup)
        YUI.widgetFactory().createLabel(popup_vbox, "Do you want to upload the anonymised "\
            "results or just store on the USB?\nResults will be available after plugging "\
            "the live USB on ALGTEST_RESULTS volume.\nIf you choose to upload, check if you set up networking.\n")
        self.yesNoButtons = YUI.widgetFactory().createHBox(popup_vbox)

        self.yesNoButtons = YUI.widgetFactory().createHBox(popup_vbox)
        self.popup_usb = YUI.widgetFactory().createPushButton(self.yesNoButtons, "&Just store on USB")
        self.popup_upload = YUI.widgetFactory().createPushButton(self.yesNoButtons, "&Upload and store")
        self.popup_cancel = YUI.widgetFactory().createPushButton(self.yesNoButtons, "&Cancel")
        self.popup.setDefaultButton(self.popup_usb)

        self.popup.open()
        self.popup.activate()


    def main_ui_loop(self):
        while self.dialog is not None and self.dialog.isOpen():
            ev = self.dialog.topmostDialog().waitForEvent(100)

            if self.algtest_runner.is_finished() and self.dialog.topmostDialog() != self.popup and self.store_button is None:
                self.popup_ask_upload()
                self.store_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Store or upload results")

            if ev.eventType() == YEvent.CancelEvent:
                print("terminate")
                if self.algtest_runner.is_alive():
                    self.algtest_runner.terminate()

                if self.popup is not None:
                    self.popup.destroy()
                    self.popup = None
                    continue

                self.dialog.destroy()
                self.dialog = None
            elif ev.eventType() == YEvent.WidgetEvent:
                if ev.widget() in [self.exit_button, self.stop_button]:
                    self.algtest_runner.terminate()
                    self.algtest_runner = AlgtestTestRunner(self.out_dir)

                    if ev.widget() == self.exit_button:
                        self.dialog.destroy()
                        break
                elif ev.widget() == self.run_button:
                    self.text.setText("Starting tests...")

                    if self.algtest_runner.is_alive():
                        self.algtest_runner.terminate()
                    self.algtest_runner = AlgtestTestRunner(self.out_dir)
                    self.algtest_runner.set_mail(self.email_field.value())

                    if self.both_button.value() or self.keygen_button.value():
                        self.algtest_runner.schedule_test(TestType.KEYGEN)

                    if self.both_button.value() or self.perf_button.value():
                        self.algtest_runner.schedule_test(TestType.PERFORMANCE)

                    self.algtest_runner.start()
                elif ev.widget() == self.popup_cancel:
                    self.popup.destroy()
                    self.popup = None
                elif ev.widget() == self.popup_usb:
                    self.algtest_runner.store_results(StoreType.STORE_USB)
                    self.popup.destroy()
                    self.popup = None
                elif ev.widget() == self.popup_upload:
                    self.algtest_runner.store_results(StoreType.UPLOAD)
                    self.popup.destroy()
                    self.popup = None
                elif ev.widget() == self.store_button:
                    self.popup_ask_upload()
                elif ev.widget() == self.shutdown_button:
                    os.system("shutdown -h now")

            elif ev.eventType() == YEvent.TimeoutEvent:
                if self.algtest_runner.get_info_changed():
                    self.progress_bar.setValue(self.algtest_runner.get_percentage())
                    self.text.setText(self.algtest_runner.get_text())


if __name__ == "__main__":
    ui = TPM2AlgtestUI()
    ui.construct_ui()
    ui.main_ui_loop()
