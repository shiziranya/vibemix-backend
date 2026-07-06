import multiprocessing

bind = "0.0.0.0:5005"
workers = min(multiprocessing.cpu_count() * 2, 8)
worker_class = "gthread"
threads = 4
timeout = 30
keepalive = 5
accesslog = "-"
errorlog = "-"
loglevel = "info"
