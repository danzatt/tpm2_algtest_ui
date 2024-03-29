#!/usr/bin/python3

# Copyright (C) 2022 Daniel Zatovic
# parts Copyright (C) 2019 Simon Struk
# parts Copyright (C) 2022 Antonin Dufka

from collections import deque
from enum import Enum, auto

from threading import Thread, Lock
import subprocess
import fcntl
import os
import requests
import json
import datetime
import re

from shutil import copyfile
from uuid import uuid4
from tempfile import mkdtemp
import urllib.request

from yui import YUI
from yui import YEvent

VERSION = 'v.0.5.4'
IMAGE_TAG = 'tpm2-algtest-ui ' + VERSION
# RESULT_PATH = "/mnt/algtest"
RESULT_PATH = "/tmp/algtest"
RUN_ALGTEST_SCRIPT = "/home/dzatovic/tpm2-algtest/run_algtest.py"
# RUN_ALGTEST_SCRIPT = "run_algtest.py"
DEPOSITORY_UCO = 4085
TCTII = "device:/dev/tpm0"
INFO_MESSAGE = \
"""<b>Experiment</b>: Analysis of Trusted Platform Modules
<b>Research institute</b>: CRoCS laboratory, Masaryk University and Red Hat Czech
<b>Contact person</b>: Petr Svenda &lt;svenda@fi.muni.cz&gt;

<b>What to do</b>:
<ol>
     <li>Please read the information about the experiment below</li>
     <li>Run the test by clicking 'Start TPM test' button. The test runs for approximately 1-3 hours (5 at most).</li>
     <li>Unplug USB disk, restart to your standard system, plug USB disk again</li>
     <li>Upload file(s) algtest_result_xxx.zip file from the USB disk at https://is.muni.cz/go/tpm</li>
</ol>

<b>Goal of the research:</b>
The goal of the research is to get a better understanding of the Trusted
Platform Modules ecosystem. Such information is vital for the designers and
developers using this technology, allowing then to answer questions like:
<ul>
    <li>What fraction of devices has TPM chip?</li>
    <li>Which cryptographic algorithms are widely supported?</li>
    <li>What is the overhead of computing a digital signature?</li>
</ul>

We do not collect any personal data. We collect only the TPM chip metadata, PCR
registers, supported cryptographic algorithms, output of random number
generator, performance measurements and temporary cryptographic keys generated
by TPM chip, product name of your device (e.g., Lenovo ThinkBook 15) and
anonymized endorsement key certificates. We plan to release the data collected
later as an open research dataset.

<b>Data we collect:</b>
<ul>
    <li>Device vendor, type (e.g., Lenovo ThinkBook 15) and BIOS version.</li>
    <li>TPM vendor, firmware version (e.g., Intel 401.1.0.0) and TPM version-related information.</li>
    <li>TPM PCR registers (see Capability_pcrread.txt).</li>
    <li>TPM metadata (TPM2_PT_xxx properties like TPM2_PT_REVISION, TPM2_PT_MANUFACTURER or TPM2_PT_PCR_COUNT – see file Capability_properties-fixed.txt and Capability_properties-variable.txt for full list).</li>
    <li>Algorithms and commands supported by TPM (see Capability_algorithms.txt and Capability_commands.txt for full list).</li>
    <li>Performance measurements for various cryptographic algorithms (see Perf_xxx.csv files).</li>
    <li>Freshly generated transient keys and signatures for ECC and RSA (see Keygen_xxx.csv and Cryptoops_xxx.csv).</li>
    <li>Generated random data (see Rng.bin).</li>
    <li>Anonymized endorsement key (EK) certificates (see Capability_ek-xxx.txt').</li>
    <li>Anonymized SRKs</li>
</ul>

Note: All mentioned files are stored inside the algtest_result_xxx.zip file.

<b>Specifically, we do NOT collect:</b>
<ul>
    <li>Personal information about the user of the analyzed computer.</li>
    <li>Full endorsement keys and SRKs (we collect only anonymized EK certificates and SRKs).</li>
    <li>Attestation key(s).</li>
    <li>User-specific content of the non-volatile TPM memory (NVRAM).</li>
</ul>

<b>Data retention:</b>
<ul>
    <li>We plan to release the data collected as open research dataset to enable wider research cooperation.</li>
    <li>The data collected will be first analyzed by CRoCS research team for the purpose of analysis current TPM chip ecosystem. We plan to release the data collected together with the research findings.</li>
</ul>
<b>Thank you a lot for cooperation!</b>""".replace("\n", "<br>")

INFO_MESSAGE_PLAIN = \
"""Experiment: Analysis of Trusted Platform Modules
Research institute: CRoCS laboratory, Masaryk University and Red Hat Czech
Contact person: Petr Svenda <svenda@fi.muni.cz>

What to do:
1. Please read the information about the experiment below
2. Run the test by clicking 'Start TPM test' button. The test runs for
   approximately 1-3 hours (5 at most).
3. Unplug USB disk, restart to your standard system, plug USB disk again
4. Upload file(s) algtest_result_xxx.zip file from the USB disk at https://is.muni.cz/go/tpm

Goal of the research:
The goal of the research is to get a better understanding of the Trusted
Platform Modules ecosystem. Such information is vital for the designers and
developers using this technology, allowing then to answer questions like:
- What fraction of devices has TPM chip?
- Which cryptographic algorithms are widely supported?
- What is the overhead of computing a digital signature?

We do not collect any personal data. We collect only the TPM chip metadata, PCR
registers, supported cryptographic algorithms, output of random number
generator, performance measurements and temporary cryptographic keys generated
by TPM chip, product name of your device (e.g., Lenovo ThinkBook 15) and
anonymized endorsement key certificates. We plan to release the data collected
later as an open research dataset.

Data we collect:
- Device vendor, type (e.g., Lenovo ThinkBook 15) and BIOS version.
- TPM vendor, firmware version (e.g., Intel 401.1.0.0) and TPM version-related information.
- TPM PCR registers (see Capability_pcrread.txt).
- TPM metadata (TPM2_PT_xxx properties like TPM2_PT_REVISION, TPM2_PT_MANUFACTURER or TPM2_PT_PCR_COUNT – see file Capability_properties-fixed.txt and Capability_properties-variable.txt for full list).
- Algorithms and commands supported by TPM (see Capability_algorithms.txt and Capability_commands.txt for full list).
- Performance measurements for various cryptographic algorithms (see Perf_xxx.csv files).
- Freshly generated transient keys and signatures for ECC and RSA (see Keygen_xxx.csv and Cryptoops_xxx.csv).
- Generated random data (see Rng.bin).
- Anonymized endorsement key (EK) certificates (see Capability_ek-xxx.txt').
- Anonymized SRKs

Note: All mentioned files are stored inside the algtest_result_xxx.zip file.

Specifically, we do NOT collect:
- Personal information about the user of the analyzed computer.
- Full endorsement keys and SRKs (we collect only anonymized EK certificates and SRKs).
- Attestation key(s).
- User-specific content of the non-volatile TPM memory (NVRAM).

Data retention:
- We plan to release the data collected as open research dataset to enable
  wider research cooperation.
- The data collected will be first analyzed by CRoCS research team for the
  purpose of analysis current TPM chip ecosystem. We plan to release the data
  collected together with the research findings.

Thank you a lot for cooperation!"""

POPUP_TEXT = """
The test finished successfully and the anonymised results were stored on the
USB. Results and instructions how to upload them will be available on the
ALGTEST_RES volume after plugging the USB into your system.

Do you want to upload the data now?
""".strip()

POPUP_TEXT_ONLINE = """
You seem to be connected to the internet. Please upload the data to the
research database now.  Alternatively, you can reboot and upload the archive
from the USB later.
"""

POPUP_TEXT_OFFLINE = """
You seem to be offline. Please configure the network and upload the data to the
research database now.  Alternatively, you can reboot and upload the archive
from the USB later.
"""

SHORT_TEST_ITERATIONS = 1000
EXTENSIVE_TEST_ITERATIONS = 100000



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


class AlgtestState(Enum):
    NOT_RUNNING = auto()
    RUNNING = auto()
    SUCCESS = auto()
    FAILED = auto()
    STOPPED = auto()


class StoreType(Enum):
    STORE_USB = auto()
    UPLOAD = auto()
    CANCEL = auto()


class AlgtestTestRunner(Thread):
    def __init__(self, out_dir, extensive, watchdog_tick=None):
        super().__init__(name="AlgtestTestRunner")
        self.out_dir = out_dir
        self.detail_dir = os.path.join(self.out_dir, 'detail')
        self.cmd = [RUN_ALGTEST_SCRIPT, '--include-legacy', '--machine-readable-statuses', '--use-system-algtest',
                    '--outdir', self.out_dir, "--with-image-tag", IMAGE_TAG, "--with-tctii", TCTII]
        self.extensive = extensive

        self.percentage = 0
        self.text = []
        self.statuses = []
        self.status = ""
        self.state = AlgtestState.NOT_RUNNING
        self.watchdog_tick = watchdog_tick
        self.info_lock = Lock()
        self.info_changed = True

        self.tests_to_run = deque()
        self.algtest_proc = None
        self.shall_stop = False
        self.internet_connected = None

        self.test_finished = False
        self.email = None

        self.uploader = ISUploader("tpm2-algtest-ui", DEPOSITORY_UCO)

    def run_and_monitor(self, cmd):
        with self.info_lock:
            self.shall_stop = False
        self.set_state(AlgtestState.RUNNING)
        self.algtest_proc = subprocess.Popen(cmd, stderr=subprocess.STDOUT, stdout=subprocess.PIPE)

        fd = self.algtest_proc.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        self.monitor_algtest()

        if self.algtest_proc.poll() is None:
            if self.get_shall_stop():
                self.algtest_proc.terminate()

            print("Waiting for the tpm2_algtest process to finish...")
            self.append_text("Waiting for the tpm2_algtest process to finish...")
            self.algtest_proc.wait()

        # read the rest of output, except the trailing newline
        text = self.algtest_proc.stdout.read()
        if text:
            self.append_text(text.decode("ascii")[:-1])

        return self.algtest_proc.returncode

    def format_results(self):
        self.append_text("Formatting results...")
        self.set_status("Formatting results...")
        code = self.run_and_monitor(self.cmd + ["format"])
        if code != 0:
            if not self.get_shall_stop():
                self.set_status("Failed to format the results.")
                self.set_state(AlgtestState.FAILED)
            else:
                self.set_status("Stop requested.")
                self.set_state(AlgtestState.STOPPED)
            self.tick(False)
        else:
            self.set_state(AlgtestState.SUCCESS)
            self.set_status("Formatted the results successfully.")
        return code

    def run(self):
        self.set_percentage(1)
        self.append_text("Starting TPM test..")
        os.makedirs(self.detail_dir, exist_ok=True)
        self.tick()

        code = self.run_and_monitor(self.cmd + ["extensive" if self.extensive else "all"])
        if code != 0:
            if not self.get_shall_stop():
                print("The run_algtest process failed. Please try to re-run the test.")
                self.set_state(AlgtestState.FAILED)
                self.tick(False)
                self.format_results()
                self.tick(False)
                self.append_text("The run_algtest process failed. Please try to re-run the test.")
                self.set_status("The run_algtest process failed. Please re-run the test.")
                self.set_percentage(0)
            else:
                self.set_status("Stop requested.")
                self.set_state(AlgtestState.STOPPED)
                self.tick(False)
                self.format_results()
                self.tick(False)
            with self.info_lock:
                self.test_finished = True
            return code

        self.append_text("Testing internet connection...")
        self.set_status("Testing internet connection...")
        self.test_connection()
        self.tick()

        self.set_percentage(100)
        with self.info_lock:
            self.test_finished = True

        if self.get_shall_stop():
            self.append_text("Stop requested.")
            self.set_status("Stop requested.")
            self.set_state(AlgtestState.STOPPED)
            self.tick(False)
            return 1
        else:
            self.set_state(AlgtestState.SUCCESS)
            self.append_text("All tests finished successfully.")
            self.set_status("All tests finished successfully.")
            self.tick(False)
            return 0

    def test_connection(self):
        try:
            urllib.request.urlopen('http://google.com', timeout=2)  # Python 3.x
            with self.info_lock:
                self.internet_connected = True
        except:
            with self.info_lock:
                self.internet_connected = False

    def store_results(self, store_type):
        result_zip = self.out_dir + '.zip'
        zip_filename = os.path.basename(result_zip)

        if store_type == StoreType.STORE_USB:
            if not os.path.isdir(RESULT_PATH):
                if os.system("mkdir -p " + RESULT_PATH + " && mount /dev/disk/by-label/ALGTEST_RES " + RESULT_PATH) == 0:
                    self.append_text("Successfully mounted ALGTEST_RES partition")

            if os.path.isdir(RESULT_PATH):
                try:
                    copyfile(result_zip, os.path.join(RESULT_PATH, zip_filename))
                    self.append_text("Copied to USB. File name: " + zip_filename)
                    with open(os.path.join(RESULT_PATH, "README_AND_HOW_TO_UPLOAD.txt"), "w") as readme_file:
                        readme_file.write(INFO_MESSAGE_PLAIN)
                    os.sync()
                except:
                    self.append_text("Failed to copy to USB.")
                    self.set_status("Failed to copy to USB.")
            else:
                self.append_text("ALGTEST_RES partition is not mounted. Can not store on USB.")

        if store_type == StoreType.UPLOAD:
            self.append_text("Uploading results...")
            if self.uploader.upload(result_zip):
                self.append_text("Results uploaded successfully.")
                self.set_status("Results uploaded successfully.")
            else:
                self.append_text("Results upload failed.")
                self.set_status("Results upload failed.")

    def is_finished(self):
        with self.info_lock:
            return self.test_finished

    def set_finished(self):
        with self.info_lock:
            self.test_finished = True

    def get_info_changed(self):
        with self.info_lock:
            if not self.info_changed:
                return False

            self.info_changed = False
            return True

    def monitor_algtest(self):
        if self.algtest_proc is None:
            return

        status_regex = re.compile(r'(\+\+\+)(.*)(\+\+\+)')

        while self.algtest_proc.poll() is None and not self.get_shall_stop():
            self.tick()

            line = self.algtest_proc.stdout.readline().decode("ascii")
            while line != "" and not self.get_shall_stop():
                self.tick()

                match = status_regex.search(line)
                if 2 < len(line) <= 5 and line[-2] == "%":
                    self.set_current_test_percentage(int(line[:-2]) / 100)
                elif match:
                    self.set_status(match.group(2))
                    self.append_text(match.group(2))
                else:
                    self.append_text(line[:-1])
                line = self.algtest_proc.stdout.readline().decode("ascii")

    def set_current_test_percentage(self, current_test_percentage):
        regexp = re.compile(r'\([0-9]+/[0-9]+\)')
        match = regexp.search(self.get_status())
        if match:
            current_test, total_tests = match.group(0)[1:-1].split('/')
            current_test = int(current_test)
            total_tests = int(total_tests)
            absolute_percentage = ((current_test - 1) / total_tests) + (1/total_tests) * current_test_percentage
            absolute_percentage = int(absolute_percentage * 100)

            # at this point test is started, so we make the progress at least 1 percent
            absolute_percentage = min(absolute_percentage + 1, 100)
            self.set_percentage(absolute_percentage)

    def append_text(self, text):
        for line in text.splitlines():
            with self.info_lock:
                if line != "":
                    self.text.append(datetime.datetime.now().strftime("%H:%M:%S") + " " + line)
                    self.info_changed = True

    def get_text(self, lines=400):
        with self.info_lock:
            return "\n".join(self.text[-lines:] if lines else self.text)

    def set_state(self, state):
        with self.info_lock:
            self.state = state
            self.info_changed = True

    def get_internet_connected(self):
        with self.info_lock:
            return self.internet_connected

    def get_state(self):
        with self.info_lock:
            return self.state

    def set_status(self, status):
        with self.info_lock:
            self.status = status
            self.statuses.append("<b>" + datetime.datetime.now().strftime("%H:%M:%S") + "</b>: " + status)
            self.info_changed = True

    def get_statuses(self):
        with self.info_lock:
            return "<br>".join(self.statuses)

    def get_status(self):
        with self.info_lock:
            return self.status

    def tick(self, alive=True):
        if self.watchdog_tick is not None:
            self.watchdog_tick(alive)

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

    def terminate(self):
        self.stop()
        if self.is_alive():
            self.join()

        if self.algtest_proc is not None and self.algtest_proc.poll() is None:
            self.algtest_proc.terminate()


class TPM2AlgtestUI:
    def __init__(self):
        self.reset_ui_members()

        self.simple_mode = True
        self.result_stored = False

        #  TODO: init to None
        self.out_dir = os.path.join(mkdtemp(), "tpm2-algtest", "algtest_result_" + str(uuid4()))
        os.makedirs(self.out_dir, exist_ok=True)
        self.algtest_runner = None

    def reset_ui_members(self):
        self.dialog = None
        self.vbox = None
        self.group = None
        self.type_box = None
        self.progress_bar = None
        self.busy_indicator = None
        self.text = None
        self.bottom_buttons = None
        self.start_short_button = None
        self.start_extensive_button = None
        self.stop_button = None
        self.store_button = None
        self.info_button = None
        self.advanced_button = None
        self.shutdown_checkbox = None
        # self.email_field = None
        self.exit_button = None

        self.popup_info = None
        self.popup_info_hide_button = None

        self.popup = None
        self.popup_buttons = None
        self.popup_upload = None
        self.popup_configure = None
        self.popup_cancel = None

    def construct_advanced_ui(self):
        self.simple_mode = False

        YUI.application().setApplicationIcon("/usr/share/icons/hicolor/256x256/apps/tpm2-algtest.png")
        YUI.application().setProductName("TPM2 algorithms test " + VERSION)
        YUI.application().setApplicationTitle("TPM2 algorithms test " + VERSION)
        self.dialog = YUI.widgetFactory().createMainDialog()

        self.vbox = YUI.widgetFactory().createVBox(self.dialog)
        self.hbox = YUI.widgetFactory().createHBox(self.vbox)
        YUI.widgetFactory().createLabel(self.hbox, "Select the test type")

        self.type_box = YUI.widgetFactory().createHBox(self.hbox)

        self.hbox2 = YUI.widgetFactory().createHBox(self.vbox)
        YUI.widgetFactory().createLabel(self.hbox2, "Select number of test repetitions: ")

        self.group = YUI.widgetFactory().createRadioButtonGroup(self.hbox2)
        self.duration_box = YUI.widgetFactory().createHBox(self.group)

        self.duration_100_button = YUI.widgetFactory().createRadioButton(self.duration_box, "&100 (Default)")
        self.duration_100_button.setValue(True)
        self.group.addRadioButton(self.duration_100_button)

        self.duration_200_button = YUI.widgetFactory().createRadioButton(self.duration_box, "&200")
        self.group.addRadioButton(self.duration_200_button)

        self.duration_300_button = YUI.widgetFactory().createRadioButton(self.duration_box, "&300")
        self.group.addRadioButton(self.duration_300_button)

        self.duration_400_button = YUI.widgetFactory().createRadioButton(self.duration_box, "&400")
        self.group.addRadioButton(self.duration_400_button)

        self.duration_500_button = YUI.widgetFactory().createRadioButton(self.duration_box, "&500")
        self.group.addRadioButton(self.duration_500_button)

        self.duration_1000_button = YUI.widgetFactory().createRadioButton(self.duration_box, "&1000")
        self.group.addRadioButton(self.duration_1000_button)

        self.duration_1500_button = YUI.widgetFactory().createRadioButton(self.duration_box, "&1500")
        self.group.addRadioButton(self.duration_1500_button)

        # YUI.widgetFactory().createLabel(self.vbox,
        #   "The collected information does not contain any of your personal information.\n" \
        #   "It will be sent to Masaryk University information system and it will be used\n" \
        #   "for research purposes regarding the performance and the security of the keys\n"
        #   "generated by your TPM. The test might take 1-4 hours.\n\n" \
        #   "We may need to contact you in the future if we need more info.\n" \
        #   "The email address won't be shared with anybody and you will not receive any advertisement.\n")

        # self.email_field = YUI.widgetFactory().createInputField(self.vbox, "Your email (optional): ")

        self.running_label = YUI.widgetFactory().createLabel(self.vbox, "Test is not running.")

        self.busy_indicator = YUI.widgetFactory().createBusyIndicator(self.vbox, "Test status", 25000)
        self.busy_indicator.setAlive(False)

        self.progress_bar = YUI.widgetFactory().createProgressBar(self.vbox, "Test progress", 100)
        self.progress_bar.setValue(0)

        self.text = YUI.widgetFactory().createRichText(self.vbox, "", True)
        self.text.setText("Select the test type and press RUN to start.")
        self.text.setAutoScrollDown(True)

        self.bottom_buttons = YUI.widgetFactory().createHBox(self.vbox)
        start_highlight_box = YUI.widgetFactory().createHBox(self.bottom_buttons)
        self.start_short_button = YUI.widgetFactory().createPushButton(start_highlight_box, "&Start basic test (<5h)")
        self.start_extensive_button = YUI.widgetFactory().createPushButton(start_highlight_box, "&Start extensive test")
        #self.dialog.highlight(start_highlight_box)
        self.dialog.setDefaultButton(self.start_short_button)
        self.info_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Info")
        self.stop_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Stop")

        if YUI.application().isTextMode():
            self.exit_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Exit")
        self.shutdown_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Shutdown PC")
        self.simple_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Simple mode")

        self.dialog.open()
        self.dialog.activate()

    def construct_simple_ui(self):
        self.simple_mode = True

        YUI.application().setApplicationIcon("/usr/share/icons/hicolor/256x256/apps/tpm2-algtest.png")
        YUI.application().setProductName("TPM2 algorithms test " + VERSION)
        YUI.application().setApplicationTitle("TPM2 algorithms test " + VERSION)
        self.dialog = YUI.widgetFactory().createMainDialog()

        if not YUI.application().isTextMode():
            self.dialog.setSize(1000, 800)

        self.vbox = YUI.widgetFactory().createVBox(self.dialog)

        # self.email_field = YUI.widgetFactory().createInputField(self.vbox, "Your email (optional): ")

        self.running_label = YUI.widgetFactory().createLabel(self.vbox, "Test is not running.")

        self.busy_indicator = YUI.widgetFactory().createBusyIndicator(self.vbox, "Test status", 25000)
        self.busy_indicator.setAlive(False)

        self.progress_bar = YUI.widgetFactory().createProgressBar(self.vbox, "Test progress", 100)
        self.progress_bar.setValue(0)

        self.shutdown_checkbox = YUI.widgetFactory().createCheckBox(self.vbox, "Shutdown automatically when test finishes successfully (results will be stored on the USB, YOU WILL NEED TO UPLOAD THEM LATER MANUALLY)")

        self.text = YUI.widgetFactory().createRichText(self.vbox, "", True)
        self.text.setAutoScrollDown(True)

        self.bottom_buttons = YUI.widgetFactory().createHBox(self.vbox)
        start_highlight_box = YUI.widgetFactory().createHBox(self.bottom_buttons)

        self.start_short_button = YUI.widgetFactory().createPushButton(start_highlight_box, "&Start basic test (<5h)")
        self.start_extensive_button = YUI.widgetFactory().createPushButton(start_highlight_box, "&Start extensive test")

        self.dialog.setDefaultButton(self.start_short_button)
        self.info_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Info")
        self.stop_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Stop")

        if  YUI.application().isTextMode():
            self.exit_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Exit")
        self.shutdown_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Shutdown PC")

        self.dialog.open()
        self.dialog.activate()

    def popup_ask_upload(self):
        if self.algtest_runner.get_internet_connected():
            popup_text = POPUP_TEXT + "\n" + POPUP_TEXT_ONLINE
        else:
            popup_text = POPUP_TEXT + "\n" + POPUP_TEXT_OFFLINE

        self.popup = YUI.widgetFactory().createPopupDialog()
        popup_vbox = YUI.widgetFactory().createVBox(self.popup)
        YUI.widgetFactory().createLabel(popup_vbox, popup_text)
        self.popup_buttons = YUI.widgetFactory().createHBox(popup_vbox)

        self.popup_buttons = YUI.widgetFactory().createHBox(popup_vbox)
        if not self.algtest_runner.get_internet_connected():
            self.popup_configure = YUI.widgetFactory().createPushButton(self.popup_buttons, "&Configure network")
        self.popup_upload = YUI.widgetFactory().createPushButton(self.popup_buttons, "&Upload results")

        self.popup_cancel = YUI.widgetFactory().createPushButton(self.popup_buttons, "&Cancel")

        self.popup.open()
        self.popup.activate()

    def popup_info_show(self):
        if YUI.application().isTextMode():
            self.text.setText(INFO_MESSAGE_PLAIN)
            return

        self.popup_info = YUI.widgetFactory().createPopupDialog()
        self.popup_info.setSize(70, 70)
        if not YUI.application().isTextMode():
            self.popup_info.setSize(550, 600)

        popup_vbox = YUI.widgetFactory().createVBox(self.popup_info)

        # YUI.widgetFactory().createLabel(popup_vbox, "\n\n")
        # YUI.widgetFactory().createLabel(popup_vbox, INFO_MESSAGE)

        text_vbox = YUI.widgetFactory().createVBox(popup_vbox)
        text = YUI.widgetFactory().createRichText(text_vbox, INFO_MESSAGE)
        text.setShrinkable(False)

        self.popup_info_hide_button = YUI.widgetFactory().createPushButton(popup_vbox, "&Continue")

        self.popup_info.open()
        self.popup_info.activate()


    def main_ui_loop(self):
        self.popup_info_show()
        while self.dialog is not None and self.dialog.isOpen():
            ev = self.dialog.topmostDialog().waitForEvent(100)

            if self.algtest_runner is not None and self.algtest_runner.is_finished() and self.dialog.topmostDialog() != self.popup and not self.result_stored:
                self.algtest_runner.store_results(StoreType.STORE_USB)
                self.result_stored = True
                if self.shutdown_checkbox.isChecked() and self.algtest_runner.get_state() == AlgtestState.SUCCESS:
                    self.algtest_runner.store_results(StoreType.UPLOAD)
                    os.system("shutdown -h now")
                if self.store_button is None:
                    self.popup_ask_upload()
                    self.store_button = YUI.widgetFactory().createPushButton(self.bottom_buttons, "&Upload results")

            if ev.eventType() == YEvent.CancelEvent or (self.exit_button is not None and ev.widget() == self.exit_button):
                if self.popup is not None:
                    self.popup.destroy()
                    self.popup = None
                    continue

                if self.popup_info is not None:
                    self.popup_info.destroy()
                    self.popup_info = None
                    continue

                if self.algtest_runner.is_alive():
                    self.algtest_runner.terminate()


                self.dialog.destroy()
                self.dialog = None
            elif ev.eventType() == YEvent.WidgetEvent:
                if ev.widget() == self.stop_button:
                    self.algtest_runner.terminate()
                elif ev.widget() in [self.start_short_button, self.start_extensive_button]:
                    if self.algtest_runner is not None and self.algtest_runner.is_alive():
                        continue
                    if self.store_button is not None:
                        self.store_button.parent().removeChild(self.store_button)
                        self.store_button = None
                        self.result_stored = False

                    self.out_dir = os.path.join(mkdtemp(), "tpm2-algtest", "algtest_result_" + str(uuid4()))
                    os.makedirs(self.out_dir, exist_ok=True)
                    self.algtest_runner = AlgtestTestRunner(self.out_dir, ev.widget() == self.start_extensive_button, lambda alive: self.busy_indicator.setAlive(alive))
                    # self.algtest_runner.set_mail(self.email_field.value())

                    if ev.widget() == self.start_short_button:
                        duration = SHORT_TEST_ITERATIONS
                        rng_iterations = 16384
                    elif ev.widget() == self.start_extensive_button:
                        duration = EXTENSIVE_TEST_ITERATIONS
                        # 14MB
                        rng_iterations = 524288

                    self.algtest_runner.start()
                elif ev.widget() == self.popup_cancel:
                    self.popup.destroy()
                    self.popup = None
                elif ev.widget() == self.popup_upload:
                    self.algtest_runner.store_results(StoreType.UPLOAD)
                    self.popup.destroy()
                    self.popup = None
                elif ev.widget() == self.popup_configure:
                    os.system("gnome-control-center wifi&")
                elif ev.widget() == self.store_button:
                    self.popup_ask_upload()
                elif ev.widget() == self.shutdown_button:
                    os.system("shutdown -h now")
                elif ev.widget() == self.popup_info_hide_button:
                    self.popup_info.destroy()
                    self.popup_info = None
                elif ev.widget() == self.info_button:
                    self.popup_info_show()
                elif ev.widget() == self.advanced_button:
                    self.dialog.destroy()
                    self.reset_ui_members()
                    self.construct_advanced_ui()
                elif ev.widget() == self.simple_button:
                    self.dialog.destroy()
                    self.reset_ui_members()
                    self.construct_simple_ui()

            elif ev.eventType() == YEvent.TimeoutEvent:
                if self.algtest_runner is not None and self.algtest_runner.get_info_changed():
                    self.progress_bar.setValue(self.algtest_runner.get_percentage())
                    if self.algtest_runner.get_text():
                        self.text.setText(self.algtest_runner.get_text())
                    self.busy_indicator.setLabel(self.algtest_runner.get_status())

                    if self.algtest_runner.get_state() == AlgtestState.NOT_RUNNING:
                        self.running_label.setText("Test is not yet running")
                        self.running_label.setUseBoldFont(False)
                    elif self.algtest_runner.get_state() == AlgtestState.RUNNING:
                        self.running_label.setText("Test is running, please do not power off your computer and plug it into AC")
                        self.running_label.setUseBoldFont(True)
                    elif self.algtest_runner.get_state() == AlgtestState.SUCCESS:
                        if self.result_stored:
                            self.running_label.setText("Test finished successfully and the result was stored. You can exit now.")
                        else:
                            self.running_label.setText("Testing completed, storing the result")
                        self.running_label.setUseBoldFont(True)
                    elif self.algtest_runner.get_state() == AlgtestState.FAILED:
                        if self.result_stored:
                            self.running_label.setText("Test failed and the partial result was stored. Try to re-run the test.")
                        else:
                            self.running_label.setText("Test failed, storing the partial result")
                        self.running_label.setUseBoldFont(True)


if __name__ == "__main__":
    ui = TPM2AlgtestUI()
    ui.construct_simple_ui()
    ui.main_ui_loop()
