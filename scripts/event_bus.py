class EventBus:
    def __init__(self):
        self._handlers = {}

    def connect(self, event, func):
        self._handlers.setdefault(event, []).append(func)

    async def emit(self, event, *args, **kwargs):
        for func in self._handlers.get(event, []):
            await func(*args, **kwargs)

bus = EventBus()