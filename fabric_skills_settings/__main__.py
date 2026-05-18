"""Allow `python -m fabric_skills_settings` to invoke the installer."""

import sys
from fabric_skills_settings._installer import main

sys.exit(main())
