#!/usr/bin/python3

import subprocess, fcntl, os

from yui import YUI
from yui import YEvent

cmd = ["/home/dan/skola/bp_code/tpm2_algtest_ui/tpm2-algtest/build/tpm2_algtest", "-s", "perf"]

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

    fulltest_button = YUI.widgetFactory().createRadioButton(type_box, "&fulltest")
    group.addRadioButton(fulltest_button)

    primary_box = YUI.widgetFactory().createVBox(vbox)
    primary_progress_bar = YUI.widgetFactory().createProgressBar(primary_box, "Overal progress", 100)
    secondary_progress_bar = YUI.widgetFactory().createProgressBar(vbox, "Current test progress", 100)
    primary_progress_bar.setValue(0)
    secondary_progress_bar.setValue(0)

    bottom_buttons = YUI.widgetFactory().createHBox(vbox)

    run_button = YUI.widgetFactory().createPushButton(bottom_buttons, "&RUN")
    stop_button = YUI.widgetFactory().createPushButton(bottom_buttons, "&STOP")
    exit_button = YUI.widgetFactory().createPushButton(bottom_buttons, "&EXIT")

    text = YUI.widgetFactory().createRichText(vbox, "", True)
    text.setText("Select the test type and press RUN to start.")
    text.setAutoScrollDown(True)

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
                primary_progress_bar.setValue(0)
                secondary_progress_bar.setValue(0)
                if ev.widget() == exit_button:
                    dialog.destroy()
                    break
            elif ev.widget() == run_button:
                if algtest_proc is not None and algtest_proc.poll() is None:
                    algtest_proc.terminate()
                primary_progress_bar.setValue(0)
                secondary_progress_bar.setValue(0)
                algtest_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                fd = algtest_proc.stdout.fileno()
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
        elif ev.eventType() == YEvent.TimeoutEvent:
            if algtest_proc is None:
                continue
            line = algtest_proc.stdout.readline().decode("ascii")
            while line != "":
                print(f"line is '{line}'")
                if 2 < len(line) <= 5 and line[-2] == "%":
                    primary_progress_bar.setValue(int(line[:-1]))
                line = algtest_proc.stdout.readline().decode("ascii")
