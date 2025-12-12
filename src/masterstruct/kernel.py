
# Centre du programme

class Kernel:
    def __init__(self, name):
        self.name = name

    def start(self):
        print(f"Kernel {self.name} is starting...")

    def shutdown(self):
        print(f"Kernel {self.name} is shutting down...")


