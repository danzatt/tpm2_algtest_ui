#include <iostream>
#include <sstream>
#include <string>
#include <cstdio>
#include <fcntl.h>

#include "YUI.h"
#include "YWidgetFactory.h"
#include "YDialog.h" 
#include "YLayoutBox.h"
#include "YEvent.h"
#include "YProgressBar.h"
#include "YPushButton.h"
#include "YIntField.h"
#include "YRadioButtonGroup.h"
#include "YRadioButton.h"
#include "YRichText.h"

int primary_max=100;
int secondary_max=100;

static YProgressBar *primary_progress_bar;
static YProgressBar *secondary_progress_bar;

int main(int argc, char **argv)
{
	YDialog *dialog = YUI::widgetFactory()->createMainDialog();

	YLayoutBox *vbox = YUI::widgetFactory()->createVBox( dialog );
	YUI::widgetFactory()->createLabel(vbox, "TPM2 algorithms test");

	YRadioButtonGroup *group = YUI::widgetFactory()->createRadioButtonGroup(vbox);
	YLayoutBox *type_box = YUI::widgetFactory()->createHBox(group);

	YRadioButton *quicktest_button = YUI::widgetFactory()->createRadioButton(type_box, "&quicktest");
	quicktest_button->setValue(true);
	group->addRadioButton(quicktest_button);

	YRadioButton *keygen_button = YUI::widgetFactory()->createRadioButton(type_box, "&keygen");
	group->addRadioButton(keygen_button);
	
	YRadioButton *perf_button = YUI::widgetFactory()->createRadioButton(type_box, "&perf");
	group->addRadioButton(perf_button);

	YRadioButton *fulltest_button = YUI::widgetFactory()->createRadioButton(type_box, "&fulltest");
	group->addRadioButton(fulltest_button);

	YLayoutBox *primary_box = YUI::widgetFactory()->createVBox( vbox );
	primary_progress_bar = YUI::widgetFactory()->createProgressBar(primary_box, "Overal progress", 100);
	secondary_progress_bar = YUI::widgetFactory()->createProgressBar(vbox, "Current test progress", 100);

	YLayoutBox *bottom_buttons = YUI::widgetFactory()->createHBox(vbox);

	YPushButton *run_button = YUI::widgetFactory()->createPushButton(bottom_buttons, "&RUN");
	YPushButton *exit_button = YUI::widgetFactory()->createPushButton(bottom_buttons, "&EXIT");
	
	YRichText *text = YUI::widgetFactory()->createRichText(vbox, "", true);
	text->setText("Select the test type and press RUN to start.");
	text->setAutoScrollDown(true);
	
	std::stringstream alltext;
	FILE* pipe = NULL;
	char c;
	std::string line;
	int bytes_read;

	while (YEvent *ev = dialog->waitForEvent(30)) {
		std::cout << "event\n";
		switch (ev->eventType()) {
		case YEvent::EventType::WidgetEvent:
			if (!ev->widget())
				continue;

			std::cout << ev->widget()->widgetClass() << "\n";
			if (ev->widget() == exit_button) {
				dialog->destroy();
				return 0;
			} else if (ev->widget() == run_button) {
				// Open pipe to file
				pipe = popen("../tpm2-algtest/build/tpm2_algtest -s perf", "r");
				if (!pipe) {
					text->setText("Failed to open pipe to tpm2_algtest");
				}

				int fd = fileno(pipe);
				fcntl(fd, F_SETFL, O_NONBLOCK);

				//int ret = fcntl(fd, F_SETPIPE_SZ, 10*1024*1024);
				//if (ret < 0) {
				//	perror("set pipe size failed.");
				//}

				//pclose(pipe);
			}
			break;
		case YEvent::EventType::TimeoutEvent:
			if (!pipe)
				continue;

			while ((c = fgetc(pipe)) != EOF) {
				line += c;

				if (c == '\n') {
					if (line.length() < 5) {
						line = "";
						continue;
					}

					if (line[0] == '*') {
						line = line.substr(1, line.size()-2);
						size_t slash_pos = line.find("/");
						std::string curr = line.substr(0, slash_pos);
						std::string total = line.substr(slash_pos + 1, line.length() - slash_pos - 2);

						int progress = 100 * (stoi(curr)/float(stoi(total)));
						primary_progress_bar->setValue(progress);
						line = "";
					}
					if (line[0] == '|') {
						line = line.substr(1, line.size()-2);
						size_t slash_pos = line.find("/");
						std::string curr = line.substr(0, slash_pos);
						std::string total = line.substr(slash_pos + 1, line.length() - slash_pos - 2);
						int progress = 100 * (stoi(curr)/float(stoi(total)));
						secondary_progress_bar->setValue(progress);
						line = "";
					}
					//text->setText(alltext.str());
					alltext << line;
					line = "";
				}
			}

			break;
		case YEvent::EventType::CancelEvent:
			if (pipe)
				pclose(pipe);
			return 0;
		default:
			std::cout << "Unhandled event: " << ev->toString(ev->eventType()) << "\n";
			continue;
		}
	}

	dialog->destroy();
}
