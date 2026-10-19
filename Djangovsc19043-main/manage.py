#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks."""

    # 🔥 Ensure project root is added to Python path (important for Render)
    BASE_DIR = Path(__file__).resolve().parent
    sys.path.append(str(BASE_DIR))

    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE',
        'kavita_chemist.settings'
    )

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Check if it's installed and available "
            "in your environment. Also verify your project structure."
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
