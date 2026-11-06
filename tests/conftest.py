import pytest

from .helpers import make_fake_services, make_settings


@pytest.fixture
def settings():
    return make_settings()


@pytest.fixture
def fake_services(settings):
    return make_fake_services(settings)
