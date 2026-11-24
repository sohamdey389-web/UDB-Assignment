
import time
import threading
class RateLimiter:
    def __init__(self, capacity=5, refill_rate=1):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()
    def allow_request(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.refill_rate   
                                  )
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False
limiter = RateLimiter(capacity=5, refill_rate=1)

for request_number in range(1, 8):
    allowed = limiter.allow_request()
    status = "Allowed" if allowed else "Blocked"
    print(
        f"Request {request_number}: {status} "
        f"(tokens left: {limiter.tokens:.2f})"
    )
    time.sleep(0.2)
