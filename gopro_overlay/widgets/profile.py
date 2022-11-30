from typing import Any

from gopro_overlay.timing import PoorTimer


class ProfiledWidget:

    def __init__(self, widget: Any, timer: PoorTimer):
        self.widget = widget
        self.timer = timer

    def draw(self, image, draw):
        with self.timer.timing(doprint=False):
            self.widget.draw(image, draw)


class WidgetProfiler:

    def __init__(self, timers):
        self.widgets = []
        self.timers = timers

    def decorate(self, name: str, level: int, widget: Any):
        widget = ProfiledWidget(widget, self.timers.timer(name, level))

        self.widgets.append(widget)

        return widget
