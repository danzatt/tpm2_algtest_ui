#!/usr/bin/python3

import subprocess
import fcntl
import os
import csv
import glob

from collections import deque

from yui import YUI
from yui import YEvent

tests_to_run = deque()

detail_dir = "out"
cmd = ["tpm2_algtest", '--outdir=' + detail_dir, "-s"]
algtest_proc = None

def compute_rsa_privates(filename):
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

def run_test(test):
    global algtest_proc
    test = "perf" if perf_button.value() else "keygen"
    algtest_proc = subprocess.Popen(cmd + [test], stdout=subprocess.PIPE)
    fd = algtest_proc.stdout.fileno()
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

def run_perf():
    run_test("perf")

def run_keygen():
    run_test("keygen")

def keygen_post():
    print('Computing RSA private keys...')
    for filename in glob.glob(os.path.join(detail_dir, 'Keygen_RSA_*_keys.csv')):
        print(filename)
        compute_rsa_privates(filename)

def run_quicktest():
    os.makedirs(detail_dir, exist_ok=True)

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
        with open(os.path.join(detail_dir, f'Quicktest_{category}.txt'), 'w') as outfile:
            subprocess.run(run_command + [category], stdout=outfile).check_returncode()

if __name__ == "__main__":
    dialog = YUI.widgetFactory().createMainDialog()
    vbox = YUI.widgetFactory().createVBox(dialog)
    YUI.widgetFactory().createLabel(vbox, "TPM2 algorithms test")

    group = YUI.widgetFactory().createRadioButtonGroup(vbox)
    type_box = YUI.widgetFactory().createHBox(group)

    both_button = YUI.widgetFactory().createRadioButton(type_box, "&both")
    both_button.setValue(True)
    group.addRadioButton(both_button)

    keygen_button = YUI.widgetFactory().createRadioButton(type_box, "&keygen")
    group.addRadioButton(keygen_button)

    perf_button = YUI.widgetFactory().createRadioButton(type_box, "&perf")
    group.addRadioButton(perf_button)

    # fulltest_button = YUI.widgetFactory().createRadioButton(type_box, "&fulltest")
    # group.addRadioButton(fulltest_button)

    primary_box = YUI.widgetFactory().createVBox(vbox)
    progress_bar = YUI.widgetFactory().createProgressBar(primary_box, "Test progress", 100)
    progress_bar.setValue(0)

    text = YUI.widgetFactory().createRichText(vbox, "", True)
    text.setText("Select the test type and press RUN to start.")
    text.setAutoScrollDown(True)

    bottom_buttons = YUI.widgetFactory().createHBox(vbox)

    run_button = YUI.widgetFactory().createPushButton(bottom_buttons, "&RUN")
    stop_button = YUI.widgetFactory().createPushButton(bottom_buttons, "&STOP")
    exit_button = YUI.widgetFactory().createPushButton(bottom_buttons, "&EXIT")

    while True:
        ev = dialog.waitForEvent(10)

        if ev.eventType() == YEvent.CancelEvent:
            dialog.destroy()
            if algtest_proc is not None and algtest_proc.poll() is None:
                algtest_proc.terminate()
            break
        elif ev.eventType() == YEvent.WidgetEvent:
            if ev.widget() in [exit_button, stop_button]:
                if algtest_proc is not None and algtest_proc.poll() is None:
                    algtest_proc.terminate()
                progress_bar.setValue(0)
                if ev.widget() == exit_button:
                    dialog.destroy()
                    break
            elif ev.widget() == run_button:
                text.setText("Starting tests...")
                if algtest_proc is not None and algtest_proc.poll() is None:
                    algtest_proc.terminate()

                progress_bar.setValue(0)

                tests_to_run = deque()
                tests_to_run.append((run_quicktest, "Collecting basic TPM info..."))

                if perf_button.value():
                    tests_to_run.append((run_perf, "Running perf test... (1/1)"))
                elif keygen_button.value():
                    tests_to_run.append((run_keygen, "Running keygen test... (1/1)"))
                    tests_to_run.append((keygen_post, "Computing RSA private keys..."))
                elif both_button.value():
                    tests_to_run.append((run_perf, "Running perf test... (1/2)"))
                    tests_to_run.append((run_keygen, "Running keygen test... (2/2)"))
                    tests_to_run.append((keygen_post, "Computing RSA private keys..."))

        elif ev.eventType() == YEvent.TimeoutEvent:
            if algtest_proc is not None and algtest_proc.poll() == 0:
                progress_bar.setValue(100)

            if (algtest_proc is None or algtest_proc.poll() is not None) and len(tests_to_run) > 0:
                next_test, message = tests_to_run.popleft()
                text.setText(text.text() + "\n" + message)
                next_test()

            if algtest_proc is None:
                continue
            line = algtest_proc.stdout.readline().decode("ascii")
            while line != "":
                if 2 < len(line) <= 5 and line[-2] == "%":
                    progress_bar.setValue(int(line[:-2]))
                line = algtest_proc.stdout.readline().decode("ascii")
