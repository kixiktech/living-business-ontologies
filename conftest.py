import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def pytest_configure(config):
    config.addinivalue_line('markers', 'live: calls the model through the Agent SDK; needs LBO_LIVE=1')


def pytest_collection_modifyitems(config, items):
    if os.environ.get('LBO_LIVE') == '1':
        return
    skip = pytest.mark.skip(reason='live run; set LBO_LIVE=1')
    for item in items:
        if 'live' in item.keywords:
            item.add_marker(skip)
