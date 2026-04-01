# Gunicorn configuration file for production deployment

# Server socket
bind = "0.0.0.0:8000"
backlog = 2048

# Worker processes
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests
max_requests = 1000
max_requests_jitter = 100

# Logging
accesslog = "access.log"
errorlog = "error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "avalon-app"

# User and group
user = "www-data"
group = "www-data"

# Preload application
preload_app = True

# Daemon mode
daemon = False

# Umask
umask = 0

# PID file
pidfile = "gunicorn.pid"

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190
