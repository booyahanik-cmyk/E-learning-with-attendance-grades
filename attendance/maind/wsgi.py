"""
WSGI config for Cobra Coaching project.
"""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
for p in (str(BASE_DIR.parent), str(BASE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'maind.settings')

application = get_wsgi_application()
