#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks."""
    # Ensure both 'attendance' and repo root are in sys.path
    current_dir = Path(__file__).resolve().parent
    parent_dir = current_dir.parent
    for p in (str(parent_dir), str(current_dir)):
        if p not in sys.path:
            sys.path.insert(0, p)

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'maind.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
