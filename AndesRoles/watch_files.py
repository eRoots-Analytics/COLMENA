from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import os

class FileCreateHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            print(f"[NEW FILE] {event.src_path}")

if __name__ == "__main__":
    path_to_watch = os.getcwd()  # or specify the path explicitly
    print(f"Watching for file creation in: {path_to_watch}")
    
    event_handler = FileCreateHandler()
    observer = Observer()
    observer.schedule(event_handler, path=path_to_watch, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
