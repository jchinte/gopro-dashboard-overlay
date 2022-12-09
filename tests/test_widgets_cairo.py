import colorsys
import contextlib
import dataclasses
import math
from enum import Enum, auto
from typing import Callable, List, Tuple

import cairo
from PIL import Image, ImageDraw

from gopro_overlay.dimensions import Dimension
from gopro_overlay.exceptions import Defect
from gopro_overlay.framemeta import FrameMeta
from gopro_overlay.journey import Journey
from gopro_overlay.point import Point, Coordinate
from tests.approval import approve_image
from tests.test_widgets import time_rendering


class CairoCircuit:

    def __init__(self, dimensions: Dimension, framemeta: FrameMeta, location: Callable[[], Point]):
        self.framemeta = framemeta
        self.location = location
        self.dimensions = dimensions
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, dimensions.x, dimensions.y)

        self.drawn = False

    def draw(self, image: Image, draw: ImageDraw):
        if not self.drawn:
            journey = Journey()
            self.framemeta.process(journey.accept)

            bbox = journey.bounding_box
            size = bbox.size() * 1.1

            ctx = cairo.Context(self.surface)
            ctx.scale(self.dimensions.x, self.dimensions.y)

            def scale(point):
                x = (point.lat - bbox.min.lat) / size.x
                y = (point.lon - bbox.min.lon) / size.y
                return x, y

            start = journey.locations[0]
            ctx.move_to(*scale(start))

            [ctx.line_to(*scale(p)) for p in journey.locations[1:]]

            line_width = 0.01

            ctx.set_source_rgba(*Colour(0.3, 0.2, 0.5).rgba())
            ctx.set_line_width(line_width)
            ctx.stroke_preserve()

            ctx.set_source_rgba(*WHITE.rgba())
            ctx.set_line_width(line_width / 4)
            ctx.stroke()

            self.drawn = True

        image.alpha_composite(to_pillow(self.surface), (0, 0))


#
# This is a conversion of the ADA INDUSTRIAL CONTROL WIDGET LIBRARY
# http://www.dmitry-kazakov.de/ada/aicwl.htm
# Any bugs are my own
# The original is GPLv2 - I don't know how this applies yet.
# The original has link-time exception...so.. ?

@dataclasses.dataclass(frozen=True)
class EllipseParameters:
    centre: Coordinate
    major_curve: float = 0.0
    minor_radius: float = 0.0
    angle: float = 0.0

    def __mul__(self, angle) -> float:
        if type(angle) == float:
            if tiny(self.major_curve):
                return angle - self.angle
            else:
                cos_ellipse = math.cos(self.angle)
                sin_ellipse = math.sin(self.angle)
                cos_angle = math.cos(angle)
                sin_angle = math.sin(angle)

                return math.atan2(
                    (sin_ellipse * cos_angle + cos_ellipse * sin_angle),
                    (self.major_curve * self.minor_radius * (cos_ellipse * cos_angle - sin_ellipse * sin_angle))
                )
        raise NotImplementedError("only float")

    def cos_gamma(self, angle):
        beta = self.angle + angle
        cos_gamma = math.cos(math.pi / 2.0 + self.angle - beta)

        if tiny(cos_gamma):
            raise ValueError("Infinite coordinate")

        return beta, cos_gamma

    def get_x(self, angle: float) -> float:
        if tiny(self.major_curve):
            beta, cos_gamma = self.cos_gamma(angle)
            return self.centre.x + self.minor_radius * math.cos(beta) / cos_gamma
        else:
            cos_angle = math.cos(angle)
            sin_angle = math.sin(angle)

            return self.centre.x + cos_angle * math.cos(self.angle) / self.major_curve - sin_angle * math.sin(self.angle) * self.minor_radius

    def get_y(self, angle) -> float:
        if tiny(angle):
            beta, cos_gamma = self.cos_gamma(angle)
            return self.centre.y + self.minor_radius * math.sin(beta) / cos_gamma
        else:
            cos_angle = math.cos(angle)
            sin_angle = math.sin(angle)

            return self.centre.y + cos_angle * math.sin(self.angle) / self.major_curve + sin_angle * math.cos(self.angle) * self.minor_radius

    def get(self, angle) -> Coordinate:
        return Coordinate(x=self.get_x(angle), y=self.get_y(angle))

    def get_point(self, angle):
        return self.centre + self.get_relative_point(angle)

    def get_relative_point(self, angle) -> Coordinate:
        if tiny(self.major_curve):
            beta, cos_gamma = self.cos_gamma(angle)

            return Coordinate(
                x=self.minor_radius * math.cos(beta) / cos_gamma,
                y=self.minor_radius * math.sin(beta) / cos_gamma
            )

        else:
            cos_angle = math.cos(angle)
            sin_angle = math.sin(angle)
            cos_ellipse = math.cos(self.angle)
            sin_ellipse = math.sin(self.angle)

            return Coordinate(
                x=cos_angle * cos_ellipse / self.major_curve - sin_angle * sin_ellipse * self.minor_radius,
                y=cos_angle * sin_ellipse / self.major_curve + sin_angle * cos_ellipse * self.minor_radius
            )


def tiny(f: float) -> bool:
    return abs(f) < 0.000001


@contextlib.contextmanager
def saved(context: cairo.Context):
    context.save()
    try:
        yield
    finally:
        context.restore()


@dataclasses.dataclass(frozen=True)
class HLSColour:
    h: float
    l: float
    s: float
    a: float

    def lighten(self, by: float) -> 'HLSColour':
        return HLSColour(self.h, math.min(self.l + by, 1.0), self.s, self.a)

    def darken(self, by: float) -> 'HLSColour':
        return HLSColour(self.h, math.max(self.l - by), self.s, self.a)

    def rgb(self) -> 'Colour':
        r, g, b = colorsys.hls_to_rgb(self.h, self.l, self.s)
        return Colour(r, g, b, self.a)


@dataclasses.dataclass(frozen=True)
class Colour:
    r: float
    g: float
    b: float
    a: float = 1.0

    def rgba(self) -> Tuple[float, float, float, float]:
        return self.r, self.g, self.b, self.a

    def rgb(self) -> Tuple[float, float, float]:
        return self.r, self.g, self.b

    def hls(self) -> HLSColour:
        h, l, s = colorsys.rgb_to_hls(self.r, self.g, self.b)
        return HLSColour(h, l, s, self.a)

    def darken(self, by: float) -> 'Colour':
        return self.hls().darken(by).rgb()

    def lighten(self, by: float) -> 'Colour':
        return self.hls().lighten(by).rgb()


BLACK = Colour(0.0, 0.0, 0.0)
WHITE = Colour(1.0, 1.0, 1.0)
RED = Colour(1.0, 0.0, 0.0)


class Arc:
    def __init__(self, ellipse: EllipseParameters, start: float = 0.0, length=2 * math.pi):
        self.ellipse = ellipse
        self.start = start
        self.length = length

    def draw(self, context: cairo.Context):
        to = self.start + self.length
        angle = self.ellipse * to - self.start

        if self.length > 0.0:
            if angle < 0.0:
                angle += math.tau
        elif self.length < 0.0:
            if angle > 0.0:
                angle -= math.tau

        if tiny(self.ellipse.major_curve):
            if abs(self.length > math.pi):
                raise ValueError("Constraint")

            context.line_to(*self.ellipse.get(self.start).tuple())
            context.line_to(*self.ellipse.get(to).tuple())
        else:
            with saved(context):
                context.translate(*self.ellipse.centre.tuple())
                context.rotate(self.ellipse.angle)
                context.scale(1.0 / self.ellipse.major_curve, self.ellipse.minor_radius)
                if self.length > 0.0:
                    context.arc(0.0, 0.0, 1.0, self.start, to)
                else:
                    context.arc_negative(0.0, 0.0, 1.0, self.start, to)


@dataclasses.dataclass(frozen=True)
class TickParameters:
    step: float
    first: int
    skipped: int


@dataclasses.dataclass(frozen=True)
class LineParameters:
    width: float
    colour: Colour = WHITE
    cap: cairo.LineCap = cairo.LINE_CAP_BUTT

    def apply_to(self, context: cairo.Context):
        context.set_source_rgba(*self.colour.rgba())
        context.set_line_cap(self.cap)
        context.set_line_width(self.width)


class EllipticScale:

    def __init__(self, inner: EllipseParameters, outer: EllipseParameters,
                 tick: TickParameters, line: LineParameters, length: float):
        self.inner = inner
        self.outer = outer
        self.tick = tick
        self.line = line
        self.start = 0.0
        self.length = length + tick.step * 0.05

    def draw(self, context: cairo.Context):
        with saved(context):
            context.new_path()

            self.line.apply_to(context)

            thick = self.tick.first

            for i in range(0, 1000):
                value = self.tick.step * i
                if value >= self.length:
                    break

                if value == self.tick.skipped:
                    thick = 1
                else:
                    thick += 1

                    point_from = self.inner.get_point(self.inner * (self.start + value))
                    point_to = self.outer.get_point(self.outer * (self.start + value))

                    context.move_to(*point_from.tuple())
                    context.line_to(*point_to.tuple())

            context.stroke()


class EllipticBackground:
    def __init__(self,
                 arc: Arc,
                 colour: Colour = BLACK):
        self.arc = arc
        self.colour = colour

    def draw(self, context: cairo.Context):
        self.arc.draw(context)

        context.set_source_rgba(*self.colour.rgba())
        context.fill()


cos45 = math.sqrt(2.0) * 0.5


@dataclasses.dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float


def abox(x1, y1, x2, y2):
    return Box(x1, y1, x2, y2)


class ShadowMode(Enum):
    ShadowNone = auto()
    ShadowIn = auto()
    ShadowOut = auto()
    ShadowEtchedIn = auto()
    ShadowEtchedOut = auto()


class DrawingAction(Enum):
    Region = auto()
    Line = auto()
    Contents = auto()


darkenBy = 1.0 / 3
lightenBy = 1.0 / 3


class AbstractBordered:
    def __init__(self):
        self.border_width = 0.1
        self.border_depth = 1.0
        self.border_shadow = ShadowMode.ShadowNone
        self.colour = RED

    def set_contents_path(self, context: cairo.Context):
        pass

    def draw_contents(self, context: cairo.Context):
        pass

    def draw(self, context: cairo.Context):

        if self.border_width > 0:
            shadow_depth = self.border_depth
        else:
            shadow_depth = 0.0

        with saved(context):
            context.new_path()
            self.set_contents_path(context)
            context.close_path()

            box = abox(*context.path_extents())

            extent = abs(box.x2 - box.x1)

            box_centre = Coordinate(
                x=(box.x2 + box.x1) * 0.5,
                y=(box.y2 + box.y1) * 0.5
            )

            def _draw(shift: float, bound: float, width: float, action: DrawingAction = DrawingAction.Line):
                F = (bound - width) / extent
                S = shift * shadow_depth * 0.5

                FX = F
                FY = F

                context.new_path()
                context.scale(FX, FY)
                context.translate(
                    box_centre.x * (1.0 / FX - 1.0) + S * cos45 / FX,
                    box_centre.y * (1.0 / FY - 1.0) + S * cos45 / FY
                )
                context.append_path(path)
                context.set_line_width(width / F)

                if action == DrawingAction.Line:
                    context.stroke()
                elif action == DrawingAction.Region:
                    context.fill()
                elif action == DrawingAction.Contents:
                    self.draw_contents(context)

            inner_size = extent
            outer_size = extent + 2.0 * self.border_width

            if self.border_shadow == ShadowMode.ShadowNone:
                middle_size = outer_size
            elif self.border_shadow == ShadowMode.ShadowIn:
                outer_size = outer_size + 2.0 * shadow_depth
                middle_size = outer_size
            elif self.border_shadow == ShadowMode.ShadowOut:
                outer_size = outer_size + shadow_depth
                middle_size = outer_size - 2.0 * shadow_depth
            elif self.border_shadow in [ShadowMode.ShadowEtchedIn, ShadowMode.ShadowEtchedOut]:
                outer_size = outer_size + 2.0 * shadow_depth
                middle_size = outer_size - 2.0 * shadow_depth

            def set_normal():
                context.set_source_rgba(*self.colour.rgba())

            def set_light():
                context.set_source_rgba(*self.colour.lighten(lightenBy).rgba())

            def set_dark():
                context.set_source_rgba(*self.colour.darken(darkenBy).rgba())

            if inner_size > 0:
                path = context.copy_path()

                if self.border_shadow == ShadowMode.ShadowNone:
                    if self.border_width > 0.0:
                        set_normal()
                        _draw(0.0, middle_size, 0.0)
                elif self.border_shadow == ShadowMode.ShadowIn:
                    if self.border_width > 0.0:
                        set_normal()
                        _draw(0.0, middle_size, 0.0)
                    set_dark()
                    _draw(-1.0, inner_size + shadow_depth, shadow_depth)
                    set_light()
                    _draw(1.0, inner_size + shadow_depth, shadow_depth)
                elif self.border_shadow == ShadowMode.ShadowOut:
                    set_light()
                    _draw(-1.0, outer_size - shadow_depth, shadow_depth)
                    set_dark()
                    _draw(1.0, outer_size - shadow_depth, shadow_depth)
                    if self.border_width > 0.0:
                        set_normal()
                        _draw(0.0, middle_size, 0.0)
                elif self.border_shadow == ShadowMode.ShadowEtchedIn:
                    set_dark()
                    _draw(-1.0, outer_size - shadow_depth, shadow_depth)
                    set_light()
                    _draw(1.0, outer_size - shadow_depth, shadow_depth)
                    if self.border_width > 0.0:
                        set_normal()
                        _draw(0.0, middle_size, 0.0)
                    set_light()
                    _draw(-1.0, inner_size + shadow_depth, shadow_depth)
                    set_dark()
                    _draw(1.0, inner_size + shadow_depth, shadow_depth)
                elif self.border_shadow == ShadowMode.ShadowEtchedOut:
                    set_light()
                    _draw(-1.0, outer_size - shadow_depth, shadow_depth)
                    set_dark()
                    _draw(1.0, outer_size - shadow_depth, shadow_depth)
                    if self.border_width > 0.0:
                        set_normal()
                        _draw(0.0, middle_size, 0.0)
                    set_dark()
                    _draw(-1.0, inner_size + shadow_depth, shadow_depth)
                    set_light()
                    _draw(1.0, inner_size + shadow_depth, shadow_depth)
                _draw(0.0, inner_size, 0.0, DrawingAction.Contents)


class Cap(AbstractBordered):
    def __init__(self, centre: Coordinate, radius: float, cfrom: Colour, cto: Colour):
        super().__init__()
        self.centre = centre
        self.radius = radius
        self.cfrom = cfrom
        self.cto = cto

        self.pattern = None
        self.mask = None

    def init(self):
        pattern = cairo.LinearGradient(-cos45, -cos45, cos45, cos45)
        pattern.add_color_stop_rgba(0.0, *self.cfrom.rgba())
        pattern.add_color_stop_rgba(1.0, *self.cto.rgba())

        mask = cairo.RadialGradient(
            0.0, 0.0, 0.0,
            0.0, 0.0, 1.0
        )
        mask.add_color_stop_rgba(0.0, *BLACK.rgba())
        mask.add_color_stop_rgba(1.0, *BLACK.rgba())
        mask.add_color_stop_rgba(1.01, *BLACK.rgba())

        self.pattern = pattern
        self.mask = mask

    def set_contents_path(self, context: cairo.Context):
        context.arc(self.centre.x, self.centre.y, self.radius, 0.0, math.tau)

    def draw_contents(self, context: cairo.Context):
        if self.pattern is None:
            self.init()

        x1, y1, x2, y2 = context.path_extents()
        r = 0.5 * (x2 - x1)

        matrix = context.get_matrix()
        matrix.xx = r
        matrix.x0 = matrix.x0 + 0.5 * (x1 + x2)
        matrix.yy = r
        matrix.y0 = matrix.y0 + 0.5 + (y1 + y2)

        context.set_matrix(matrix)
        context.set_source(self.pattern)
        context.mask(self.mask)


@dataclasses.dataclass(frozen=True)
class NeedleParameter:
    width: float
    length: float
    cap: cairo.LineCap = cairo.LINE_CAP_BUTT

    @property
    def radius(self):
        return self.width / 2.0


class Needle:

    def __init__(self, centre: Coordinate,
                 value: Callable[[], float],
                 start: float, length: float,
                 tip: NeedleParameter, rear: NeedleParameter,
                 colour: Colour):
        self.centre = centre
        self.colour = colour
        self.rear = rear
        self.tip = tip
        self.length = length
        self.start = start
        self.value = value

    def draw(self, context: cairo.Context):
        with saved(context):
            context.new_path()
            context.translate(*self.centre.tuple())
            context.rotate(self.start + self.value() * self.length)

            tip = self.tip
            rear = self.rear

            if tip.cap == cairo.LINE_CAP_BUTT:
                context.move_to(tip.length, -tip.radius)
                context.line_to(tip.length, tip.radius)
            elif tip.cap == cairo.LINE_CAP_ROUND:

                angle = math.atan2(
                    tip.radius - rear.radius,
                    tip.length + rear.length
                )
                cos_angle = math.cos(angle)
                sin_angle = math.sin(angle)

                context.move_to(tip.length + tip.radius * sin_angle, -tip.radius * cos_angle)
                context.arc(tip.length, 0.0, tip.radius, angle - math.pi / 2.0, math.pi / 2.0 - angle)
                context.line_to(tip.length + tip.radius * sin_angle, tip.radius * cos_angle)

            elif tip.cap == cairo.LINE_CAP_SQUARE:
                context.move_to(tip.length, -tip.radius)
                context.line_to(tip.length + tip.radius * math.sqrt(2.0), 0.0)
                context.line_to(tip.length, tip.radius)
            else:
                raise ValueError("Unsupported needle tip type")

            if rear.cap == cairo.LINE_CAP_BUTT:
                context.line_to(-rear.length, rear.radius)
                context.line_to(-rear.length, -rear.radius)
            elif tip.cap == cairo.LINE_CAP_ROUND:
                angle = math.atan2(
                    rear.radius - tip.radius,
                    tip.length + rear.length
                )
                cos_angle = math.cos(angle)
                sin_angle = math.sin(angle)

                context.line_to(-rear.length - rear.radius * sin_angle, rear.radius * cos_angle)
                context.arc(-rear.length, 0.0, rear.radius, math.pi / 2.0 - angle, angle - math.pi / 2.0)
                context.line_to(-rear.length - rear.radius * sin_angle, -rear.radius * cos_angle)

            elif tip.cap == cairo.LINE_CAP_SQUARE:
                context.line_to(-rear.length, rear.radius)
                context.line_to(-rear.length - rear.radius * math.sqrt(2.0), 0.0)
                context.line_to(-rear.length, -rear.radius)
            else:
                raise ValueError("Unsupported needle rear type")

            context.close_path()
            context.set_source_rgba(*self.colour.rgba())

            context.fill()


class AnnotationMode(Enum):
    MovedInside = auto()
    MovedOutside = auto()
    MovedCentred = auto()
    Rotated = auto()
    Skewed = auto()


class FontFace:

    def text_extents(self, context: cairo.Context, text: str) -> cairo.TextExtents:
        raise NotImplementedError()

    def show(self, context: cairo.Context, text: str):
        raise NotImplementedError()


class PangoFontFace(FontFace):
    pass


class ToyFontFace(FontFace):

    def __init__(self, family: str, slant: cairo.FontSlant = cairo.FONT_SLANT_NORMAL, weight: cairo.FontWeight = cairo.FONT_WEIGHT_NORMAL):
        self.face = cairo.ToyFontFace(family, slant, weight)

    def text_extents(self, context: cairo.Context, text: str) -> cairo.TextExtents:
        context.set_font_face(self.face)
        return context.text_extents(text)

    def show(self, context: cairo.Context, text: str):
        context.set_font_face(self.face)
        context.show_text(text)


class EllipticAnnotation:

    def __init__(self, centre: Coordinate,
                 ellipse: EllipseParameters,
                 tick: TickParameters,
                 colour: Colour,
                 face: FontFace,
                 mode: AnnotationMode,
                 texts: List[str],
                 start: float,
                 length: float):
        self.mode = mode
        self.texts = texts
        self.face = face
        self.colour = colour
        self.centre = centre
        self.tick = tick
        self.ellipse = ellipse
        self.start = start
        self.original_length = length
        self.length = length + tick.step * 0.05
        self.height = 0.05  # hack
        self.stretch = 0.8

    def draw(self, context: cairo.Context):

        context.set_source_rgba(*self.colour.rgba())
        thick = self.tick.first

        for i in range(0, 1_000_000):
            angle = self.tick.step * i
            if angle > self.length:
                break
            if self.original_length < 0.0:
                angle = -angle
            if thick == self.tick.skipped:
                thick = 1
            else:
                thick += 1
                angle = self.start + angle
                point = self.ellipse.get_point(self.ellipse * angle)

                if i >= len(self.texts):
                    break

                text = self.texts[i]
                extents = self.face.text_extents(context, text)

                with saved(context):
                    if extents.height > 0.0:
                        gain = self.height / extents.height

                        context.translate(*point.tuple())

                        if self.mode == AnnotationMode.MovedInside:
                            context.translate(
                                (-extents.width * 0.5 * gain * math.cos(angle)),
                                (-extents.height * 0.5 * gain * math.sin(angle))
                            )
                        elif self.mode == AnnotationMode.MovedOutside:
                            raise NotImplementedError("Moved Outside")
                        elif self.mode == AnnotationMode.MovedCentred:
                            # nothing to do
                            pass
                        elif self.mode == AnnotationMode.Rotated:
                            raise NotImplementedError("Rotated")
                        elif self.mode == AnnotationMode.Skewed:
                            raise NotImplementedError("Skewed")

                        context.scale(gain * self.stretch, gain)
                        context.move_to(
                            -(extents.x_bearing + extents.width) * 0.5,
                            -(extents.y_bearing + extents.height) * 0.5
                        )

                        self.face.show(context, text)


def to_pillow(surface: cairo.ImageSurface) -> Image:
    size = (surface.get_width(), surface.get_height())
    stride = surface.get_stride()

    format = surface.get_format()
    if format != cairo.FORMAT_ARGB32:
        raise Defect(f"Only support ARGB32 images, not {format}")

    with surface.get_data() as memory:
        return Image.frombuffer("RGBA", size, memory.tobytes(), 'raw', "BGRa", stride)


class CairoWidget:

    def __init__(self, size: Dimension, widgets):
        self.size = size
        self.widgets = widgets

    def draw(self, image: Image, draw: ImageDraw):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.size.x, self.size.y)
        ctx = cairo.Context(surface)
        ctx.scale(surface.get_width(), surface.get_height())

        for widget in self.widgets:
            widget.draw(ctx)

        image.alpha_composite(to_pillow(surface), (0, 0))


def cairo_widget_test(widgets, repeat=100):
    return time_rendering(
        name="test_gauge",
        dimensions=Dimension(500, 500),
        widgets=[
            CairoWidget(size=Dimension(500, 500), widgets=widgets)
        ],
        repeat=repeat
    )


@approve_image
def test_ellipse():
    return cairo_widget_test(widgets=[
        EllipticBackground(
            arc=Arc(
                ellipse=EllipseParameters(Coordinate(x=0.5, y=0.5), major_curve=1.0 / 0.5, minor_radius=0.5, angle=0.0),
                start=0.0, length=math.pi
            ),
            colour=BLACK
        )
    ])


@approve_image
def test_cap():
    return cairo_widget_test(widgets=[
        Cap(
            centre=Coordinate(0.0, 0.0),
            radius=0.2,
            cfrom=Colour(1.0, 1.0, 1.0),
            cto=Colour(0.5, 0.5, 0.5)
        )
    ], repeat=1)


@approve_image
def test_scale():
    return cairo_widget_test(widgets=[
        EllipticScale(
            inner=EllipseParameters(Coordinate(x=0.5, y=0.5), major_curve=1.0 / 0.43, minor_radius=0.43, angle=0.0),
            outer=EllipseParameters(Coordinate(x=0.5, y=0.5), major_curve=1.0 / 0.49, minor_radius=0.49, angle=0.0),
            tick=TickParameters(step=math.pi / 12, first=1, skipped=1000),
            length=2 * math.pi,
            line=LineParameters(
                width=6.0 / 400.0,
            )
        ),
        EllipticScale(
            inner=EllipseParameters(Coordinate(x=0.5, y=0.5), major_curve=1.0 / 0.43, minor_radius=0.43, angle=0.0),
            outer=EllipseParameters(Coordinate(x=0.5, y=0.5), major_curve=1.0 / 0.49, minor_radius=0.49, angle=0.0),
            tick=TickParameters(step=(math.pi / 12) / 2.0, first=1, skipped=2),
            length=2 * math.pi,
            line=LineParameters(
                width=1.0 / 400.0,
                colour=BLACK
            )
        ),
    ])


@approve_image
def test_needle():
    return cairo_widget_test(widgets=[
        Needle(
            value=lambda: 0.0,
            centre=Coordinate(0.5, 0.5),
            start=math.radians(36),
            length=math.radians(254),
            tip=NeedleParameter(width=0.0175, length=0.46),
            rear=NeedleParameter(width=0.03, length=0.135),
            colour=RED
        )
    ])


@approve_image
def test_annotation():
    sectors = 17
    step = math.radians(254) / sectors

    return cairo_widget_test(widgets=[
        EllipticAnnotation(
            centre=Coordinate(x=0.5, y=0.5),
            ellipse=EllipseParameters(Coordinate(x=0.0, y=0.0), major_curve=1.0 / 0.41, minor_radius=0.41, angle=math.tau),
            tick=TickParameters(step=(math.pi / 12) / 2.0, first=1, skipped=2),
            colour=BLACK,
            face=ToyFontFace("arial"),
            mode=AnnotationMode.MovedInside,
            texts=[str(x) for x in range(0, 180, 10)],
            start=0.0 + step,
            length=math.tau - step
        ),
    ], repeat=1)


class GaugeRound254:

    def __init__(self):
        value = lambda: 0.23

        sectors = 17
        length = math.radians(254)
        start = math.radians(-36)

        step = length / sectors

        center = Coordinate(x=0.5, y=0.5)
        background = EllipticBackground(Arc(
            EllipseParameters(center, major_curve=1.0 / 0.5, minor_radius=0.5, angle=0.0),
        ))

        pin = Cap(
            centre=center, radius=0.12, cfrom=WHITE, cto=Colour(0.5, 0.5, 0.5)
        )

        major_ticks = EllipticScale(
            inner=EllipseParameters(center, major_curve=1.0 / 0.43, minor_radius=0.43, angle=length),
            outer=EllipseParameters(center, major_curve=1.0 / 0.49, minor_radius=0.49, angle=length),
            tick=TickParameters(step, 0, 0),
            line=LineParameters(6.0 / 4000),
            length=length
        )

        minor_ticks = EllipticScale(
            inner=EllipseParameters(center, major_curve=1.0 / 0.46, minor_radius=0.46, angle=length),
            outer=EllipseParameters(center, major_curve=1.0 / 0.49, minor_radius=0.49, angle=length),
            tick=TickParameters(step / 2.0, 0, 2),
            line=LineParameters(1.0 / 4000),
            length=length
        )

        needle = Needle(
            centre=center,
            value=value,
            start=start,
            length=length,
            tip=NeedleParameter(width=0.0175, length=0.46),
            rear=NeedleParameter(width=0.03, length=0.135),
            colour=RED
        )

        self.widgets = [
            background, major_ticks, minor_ticks, needle
        ]

    def draw(self, context: cairo.Context):
        [w.draw(context) for w in self.widgets]


@approve_image
def test_gauge_round_254():
    return cairo_widget_test(widgets=[
        GaugeRound254()
    ], repeat=1)
