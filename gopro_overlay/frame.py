import contextlib
import ctypes
import dataclasses
from multiprocessing import shared_memory
from typing import IO, AnyStr, Any

from PIL import Image

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


class SimpleFrameProvider:
    def __init__(self, dimensions: Dimension):
        self._dimensions = dimensions

    @contextlib.contextmanager
    def provide(self) -> Frame:
        yield Frame(image=Image.new("RGBA", (self._dimensions.x, self._dimensions.y), (0, 0, 0, 0)))


def clear_buffer(buffer):
    ctypes.memset(ctypes.byref(buffer), 0x00, len(buffer))


def raw_image(dimensions: Dimension, buffer) -> Image:
    return Image.frombuffer("RGBA", (dimensions.x, dimensions.y), buffer, "raw", "RGBA", 0, 1)


class DirectFrameProvider:

    def __init__(self, dimensions: Dimension):
        self._dimensions = dimensions
        self._buffer_size = (dimensions.x * dimensions.y * 4)
        self._buffer = ctypes.create_string_buffer(self._buffer_size)
        self._image = raw_image(dimensions=dimensions, buffer=self._buffer)
        self._image.readonly = 0

    @contextlib.contextmanager
    def provide(self) -> DirectFrame:
        frame = DirectFrame(image=self._image, buffer=self._buffer)
        try:
            yield frame
        finally:
            clear_buffer(frame.buffer)


class SharedFrameProvider:
    def __init__(self, dimensions: Dimension):
        self._dimensions = dimensions
        self._buffer_size = (dimensions.x * dimensions.y * 4)

        self._shm = shared_memory.SharedMemory(create=True, size=self._buffer_size * 2)

        self._buffer0 = self._shm
        self._buffer1 = self._shm[self._buffer_size:]

        self._image0 = raw_image(dimensions=dimensions, buffer=self._buffer0)
        self._image1 = raw_image(dimensions=dimensions, buffer=self._buffer1)

        self._image0.readonly = 0
        self._image1.readonly = 0

        self._writing = 0

    def provide(self) -> DirectFrame:

        if self._writing == 0:
            frame = DirectFrame(self._image0, self._buffer0)
        else:
            frame = DirectFrame(self._image1, self._buffer1)

        try:
            yield frame
        finally:
            clear_buffer(frame.buffer)
