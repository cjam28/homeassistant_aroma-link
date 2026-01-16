"""Constants for the Aroma-Link integration."""

DOMAIN = "aroma_link_integration_test"

# Configuration
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_ID = "device_id"
CONF_DIFFUSE_TIME = "diffuse_time"
CONF_WORK_DURATION = "work_duration"

# Default values
DEFAULT_DIFFUSE_TIME = 60  # seconds
DEFAULT_WORK_DURATION = 10  # seconds
DEFAULT_PAUSE_DURATION = 900  # seconds (15 minutes)

# Services
SERVICE_SET_SCHEDULER = "set_scheduler"
SERVICE_RUN_DIFFUSER = "run_diffuser"
SERVICE_LOAD_WORKSET = "load_workset"
SERVICE_SAVE_WORKSET = "save_workset"

# Attributes
ATTR_DURATION = "duration"
ATTR_DIFFUSE_TIME = "diffuse_time"
ATTR_WORK_DURATION = "work_duration"
ATTR_PAUSE_DURATION = "pause_duration"
ATTR_WEEK_DAYS = "week_days"

# SSL Configuration
VERIFY_SSL = False  # Set to False to bypass SSL certificate verification for Aroma-Link API
