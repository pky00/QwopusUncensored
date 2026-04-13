import os
import time
import logging
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("qwopus.rate_limiter")
logging.basicConfig(level=logging.INFO)

REQUESTS_PER_MINUTE = int(os.environ.get("RATE_LIMIT_RPM", "50"))
BAN_AFTER_FAILURES = int(os.environ.get("RATE_LIMIT_BAN_AFTER", "3"))
BAN_DURATION_SECONDS = int(os.environ.get("RATE_LIMIT_BAN_SECONDS", "3600"))


class RateLimiterMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.request_log = defaultdict(list)
        self.auth_failures = defaultdict(int)
        self.banned_ips = {}

    def _client_ip(self, request):
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host

    def _cleanup_old_requests(self, ip, now):
        cutoff = now - 60
        self.request_log[ip] = [t for t in self.request_log[ip] if t > cutoff]

    def _is_banned(self, ip, now):
        if ip in self.banned_ips:
            if now < self.banned_ips[ip]:
                return True
            del self.banned_ips[ip]
            self.auth_failures[ip] = 0
        return False

    async def dispatch(self, request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        now = time.time()
        ip = self._client_ip(request)

        if self._is_banned(ip, now):
            remaining = int(self.banned_ips[ip] - now)
            logger.warning(f"Banned IP attempted access: {ip} ({remaining}s remaining)")
            return JSONResponse(
                status_code=403,
                content={"error": f"IP banned. Try again in {remaining}s."},
            )

        self._cleanup_old_requests(ip, now)
        if len(self.request_log[ip]) >= REQUESTS_PER_MINUTE:
            logger.warning(f"Rate limit exceeded: {ip}")
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Max 50 requests/minute."},
            )

        self.request_log[ip].append(now)
        response = await call_next(request)

        if response.status_code == 401:
            self.auth_failures[ip] += 1
            logger.warning(f"Auth failure from {ip} ({self.auth_failures[ip]}/{BAN_AFTER_FAILURES})")
            if self.auth_failures[ip] >= BAN_AFTER_FAILURES:
                self.banned_ips[ip] = now + BAN_DURATION_SECONDS
                logger.warning(f"IP banned for {BAN_DURATION_SECONDS}s: {ip}")
                return JSONResponse(
                    status_code=403,
                    content={"error": f"Too many failed attempts. Banned for {BAN_DURATION_SECONDS // 60} minutes."},
                )
        elif response.status_code == 200:
            self.auth_failures[ip] = 0

        return response
