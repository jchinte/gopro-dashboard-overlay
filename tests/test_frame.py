from io import BytesIO

from PIL import ImageDraw

from gopro_overlay.dimensions import Dimension
from gopro_overlay.frame import SimpleFrameProvider, Frame, DirectFrameProvider, SimpleFrameWriter, DirectFrameWriter


def draw_something_into(frame: Frame):
    draw = ImageDraw.Draw(frame.image)
    draw.rectangle((10, 10, 50, 50), fill=(255, 0, 255, 128), outline=(0, 0, 0, 255))


def test_simple_frame_same_output_as_direct_frame():
    dimension = Dimension(x=100, y=100)

    simple_bytes = BytesIO()
    simple_writer = SimpleFrameWriter(simple_bytes)

    with SimpleFrameProvider(dimensions=dimension).provide() as frame:
        draw_something_into(frame)
        simple_writer.write(frame)

    direct_bytes = BytesIO()
    direct_writer = DirectFrameWriter(direct_bytes)
    with DirectFrameProvider(dimensions=dimension).provide() as frame:
        draw_something_into(frame)
        direct_writer.write(frame)

    assert simple_bytes.getvalue() == direct_bytes.getvalue()
