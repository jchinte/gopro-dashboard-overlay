import contextlib
import ctypes
import dataclasses
from typing import IO, AnyStr, Any

from PIL import Image, ImageDraw

from gopro_overlay.dimensions import Dimension


@dataclasses.dataclass(frozen=True)
class Frame:
    image: Image


@dataclasses.dataclass(frozen=True)
class DirectFrame(Frame):
    buffer: Any


class NullFrameWriter:
    def write(self, frame: Frame):
        pass


class SimpleFrameWriter:
    def __init__(self, fd: IO[AnyStr]):
        self._fd = fd

    def write(self, frame: Frame):
        self._fd.write(frame.image.tobytes())


class DirectFrameWriter:
    def __init__(self, fd: IO[AnyStr]):
        self._fd = fd

    def write(self, frame: DirectFrame):
        self._fd.write(frame.buffer)


class DirectFrameProvider:

    def __init__(self, dimensions: Dimension):
        self._dimensions = dimensions
        self._buffer_size = (dimensions.x * dimensions.y * 4)
        self._buffer = ctypes.create_string_buffer(self._buffer_size)
        self._image = Image.frombuffer("RGBA", (dimensions.x, dimensions.y), self._buffer, "raw", "RGBA", 0, 1)
        self._image.readonly = 0
        self._draw = ImageDraw.Draw(self._image)

    @contextlib.contextmanager
    def provide(self) -> DirectFrame:
        try:
            yield DirectFrame(image=self._image, buffer=self._buffer)
        finally:
            self.clear()

    def clear(self):
        ctypes.memset(ctypes.byref(self._buffer), 0x00, self._buffer_size)


class SimpleFrameProvider:
    def __init__(self, dimensions: Dimension):
        self._dimensions = dimensions

    @contextlib.contextmanager
    def provide(self) -> Frame:
        yield Frame(image=Image.new("RGBA", (self._dimensions.x, self._dimensions.y), (0, 0, 0, 0)))
