import pytest

from asi import analysis
from asi.generate import generate
from asi.model import build


@pytest.fixture(scope="session")
def data():
    return generate()


@pytest.fixture(scope="session")
def con(data):
    c = build(*data)
    yield c
    c.close()


@pytest.fixture(scope="session")
def res(con):
    return analysis.run_all(con)
