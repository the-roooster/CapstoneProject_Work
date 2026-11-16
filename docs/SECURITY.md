# Security

## Threat model

1. Analyst credentials protect access to employee activity and risk scores.
2. An attacker may try stolen passwords or repeated login guesses.
3. Login failures are limited per source IP and normalized email in each process.
4. A stolen bearer token grants access until it expires.
5. The JWT signing secret must be at least 32 characters outside tests.
6. Input CSVs and event metadata are untrusted application data.
7. CORS accepts only the origins explicitly listed in CORS_ORIGINS.
8. The API returns a generic message for unexpected server errors.
9. Model and alert explanations can contain sensitive employee information.
10. Database, model files and logs require restricted operator access.

## Known simplifications

- One analyst account is used for the demo; there is no role hierarchy.
- Job state and login rate limits are in memory and are not shared across processes or restarts.
- JWTs use a shared HS256 signing secret.
- Development does not terminate TLS; use HTTPS at a trusted proxy outside development.
- The limiter uses the direct client IP and does not trust forwarding headers. Configure a trusted proxy to pass the real IP at the server layer.
