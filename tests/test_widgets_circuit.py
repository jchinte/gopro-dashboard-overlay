import random
from datetime import timedelta

from gopro_overlay import fake
from gopro_overlay.dimensions import Dimension
from gopro_overlay.privacy import NoPrivacyZone
from gopro_overlay.widgets.map import Circuit
from tests.approval import approve_image
from tests.test_widgets import time_rendering

rng = random.Random()
rng.seed(12345)

ts = fake.fake_framemeta(timedelta(minutes=10), step=timedelta(seconds=1), rng=rng)


@approve_image
def test_circuit():
    return time_rendering(
        name="test_gauge",
        dimensions=Dimension(500, 500),
        widgets=[
            Circuit(
                dimensions=Dimension(500, 500),
                framemeta=ts,
                privacy_zone=NoPrivacyZone(),
                location=lambda: ts.get(ts.min).point,
            )
        ],
        repeat=100
    )
