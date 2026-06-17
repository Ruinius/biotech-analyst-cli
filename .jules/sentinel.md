## 2025-02-18 - Missing Timeouts on External API Calls
**Vulnerability:** External API calls using `urllib.request.urlopen` across multiple fetch scripts lacked timeout configurations.
**Learning:** Without timeouts, unresponsive external APIs can cause the application's data collection pipeline to hang indefinitely, leading to resource exhaustion or Denial of Service (DoS) conditions.
**Prevention:** Always enforce a `timeout` parameter (e.g., `timeout=30`) when making network requests using `urllib` or any other HTTP client library.
