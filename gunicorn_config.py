"""
Gunicorn configuration for VibeMix Backend
Production-ready WSGI server configuration
"""
import multiprocessing
import os

# Server socket
bind = "127.0.0.1:5005"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"  # or "gevent" for async, "eventlet" for WebSockets
worker_connections = 1000
max_requests = 1000  # Restart workers after N requests (helps prevent memory leaks)
max_requests_jitter = 50  # Add randomness to max_requests
timeout = 120  # Worker timeout in seconds
keepalive = 5  # Keep-alive connections

# Process naming
proc_name = "vibemix-backend"

# Logging
accesslog = "/var/log/vibemix/access.log"
errorlog = "/var/log/vibemix/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Server mechanics
daemon = False  # Run in foreground when managed by systemd
pidfile = None  # Let systemd manage the PID
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if terminating SSL at Gunicorn instead of Nginx)
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem"

# Server hooks
def on_starting(server):
    """Called just before the master process is initialized."""
    # Create log directory if it doesn't exist
    import os
    os.makedirs("/var/log/vibemix", exist_ok=True)

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("VibeMix backend server is ready. Accepting connections.")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("VibeMix backend server is reloading.")
