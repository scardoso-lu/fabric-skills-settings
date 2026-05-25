"""Allow `python -m fabric_agent_installer` to invoke the installer."""

import sys
from fabric_agent_installer._installer import main

sys.exit(main())
