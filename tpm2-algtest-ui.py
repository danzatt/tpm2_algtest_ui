#!/usr/bin/python3

import subprocess
import fcntl
import os

from yui import YUI
from yui import YEvent

cmd = ["tpm2_algtest", "-s"]

if __name__ == "__main__":
    dialog = YUI.widgetFactory().createMainDialog()
    vbox = YUI.widgetFactory().createVBox(dialog)
    YUI.widgetFactory().createLabel(vbox, "TPM2 algorithms test")

    group = YUI.widgetFactory().createRadioButtonGroup(vbox)
    type_box = YUI.widgetFactory().createHBox(group)

    quicktest_button = YUI.widgetFactory().createRadioButton(type_box, "&quicktest")
    quicktest_button.setValue(True)
    group.addRadioButton(quicktest_button)

    keygen_button = YUI.widgetFactory().createRadioButton(type_box, "&keygen")
    group.addRadioButton(keygen_button)

    perf_button = YUI.widgetFactory().createRadioButton(type_box, "&perf")
    group.addRadioButton(perf_button)

    # fulltest_button = YUI.widgetFactory().createRadioButton(type_box, "&fulltest")
    # group.addRadioButton(fulltest_button)

    primary_box = YUI.widgetFactory().createVBox(vbox)
    progress_bar = YUI.widgetFactory().createProgressBar(primary_box, "Test progress", 100)
    progress_bar.setValue(0)

    bottom_buttons = YUI.widgetFactory().createHBox(vbox)

    run_button = YUI.widgetFactory().createPushButton(bottom_buttons, "&RUN")
    stop_button = YUI.widgetFactory().createPushButton(bottom_buttons, "&STOP")
    exit_button = YUI.widgetFactory().createPushButton(bottom_buttons, "&EXIT")

    algtest_proc = None
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
                if quicktest_button.value():
                    detail_dir = "out"
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
                    continue
                if algtest_proc is not None and algtest_proc.poll() is None:
                    algtest_proc.terminate()
                progress_bar.setValue(0)
                test = "perf" if perf_button.value() else "keygen"
                algtest_proc = subprocess.Popen(cmd + [test], stdout=subprocess.PIPE)
                fd = algtest_proc.stdout.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        elif ev.eventType() == YEvent.TimeoutEvent:
            if algtest_proc is not None and algtest_proc.poll() == 0:
                progress_bar.setValue(100)
            if algtest_proc is None:
                continue
            line = algtest_proc.stdout.readline().decode("ascii")
            while line != "":
                if 2 < len(line) <= 5 and line[-2] == "%":
                    progress_bar.setValue(int(line[:-2]))
                line = algtest_proc.stdout.readline().decode("ascii")
