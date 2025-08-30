"""
Connection manager for MCP/WebSocket connections with enhanced error recovery and rate limiting.
"""

import time
import threading
import logging
from collections import defaultdict, deque
from typing import Dict, Set, Optional, Tuple, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio

from .types import SecurityLevel

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Connection state enumeration."""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    CLOSED = "closed"


class ErrorCategory(Enum):
    """Error category enumeration for better error handling."""
    NETWORK = "network"
    PROTOCOL = "protocol"
    RESOURCE = "resource"
    SECURITY = "security"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


@dataclass
class ConnectionError:
    """Information about connection errors."""
    error_type: ErrorCategory
    message: str
    timestamp: datetime
    recoverable: bool = True
    retry_count: int = 0


@dataclass
class ConnectionInfo:
    """Information about an active connection."""
    connection_id: str
    client_ip: str
    connected_at: datetime
    last_activity: datetime
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    state: ConnectionState = ConnectionState.CONNECTED
    error_history: List[ConnectionError] = field(default_factory=list)
    reconnect_attempts: int = 0
    last_error: Optional[ConnectionError] = None

    def __post_init__(self):
        if self.error_history is None:
            self.error_history = []


@dataclass
class RateLimitInfo:
    """Rate limiting information for a connection."""
    requests_in_window: int = 0
    window_start: float = 0.0
    burst_count: int = 0
    last_request_time: float = 0.0


class CircuitBreaker:
    """Circuit breaker pattern for connection error handling."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            if isinstance(e, self.expected_exception):
                self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if self.last_failure_time is None:
            return True
        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _on_success(self):
        """Handle successful operation."""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("Circuit breaker reset to CLOSED state")

    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
        elif self.state == "HALF_OPEN":
            self.state = "OPEN"
            logger.warning("Circuit breaker opened during HALF_OPEN state")


class RetryMechanism:
    """Retry mechanism with exponential backoff."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0,
                 max_delay: float = 60.0, backoff_factor: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor

    def execute_with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic."""
        last_exception: Exception = Exception("Unknown error")

        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt == self.max_retries:
                    logger.error(f"Max retries ({self.max_retries}) exceeded: {e}")
                    raise e

                delay = min(self.base_delay * (self.backoff_factor ** attempt), self.max_delay)
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
                time.sleep(delay)

        # This should never be reached, but just in case
        raise last_exception


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for tool executions."""

    def __init__(self, max_requests: int, window_seconds: int, burst_limit: int = 5):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst_limit = burst_limit
        self.requests: Dict[str, deque] = defaultdict(deque)

    def is_allowed(self, connection_id: str) -> Tuple[bool, float]:
        """
        Check if a request is allowed for the given connection.

        Returns:
            Tuple of (allowed: bool, retry_after: float)
        """
        now = time.time()
        request_times = self.requests[connection_id]

        # Remove old requests outside the window
        while request_times and request_times[0] < now - self.window_seconds:
            request_times.popleft()

        # Check if under the limit
        if len(request_times) < self.max_requests:
            request_times.append(now)
            return True, 0.0

        # Calculate retry time
        oldest_request = request_times[0]
        retry_after = (oldest_request + self.window_seconds) - now

        return False, max(0.0, retry_after)


class ConnectionManager:
    """
    Enhanced connection manager for MCP/WebSocket connections with comprehensive error recovery.
    """

    def __init__(self, max_connections: int = 50, max_per_ip: int = 10,
                 connection_timeout: int = 3600, enable_ip_filtering: bool = True):
        self.max_connections = max_connections
        self.max_per_ip = max_per_ip
        self.connection_timeout = connection_timeout
        self.enable_ip_filtering = enable_ip_filtering

        # Connection tracking
        self.active_connections: Dict[str, ConnectionInfo] = {}
        self.connections_by_ip: Dict[str, Set[str]] = defaultdict(set)

        # Rate limiting
        self.rate_limiter = None

        # Error recovery components
        self.circuit_breaker = CircuitBreaker()
        self.retry_mechanism = RetryMechanism()

        # Performance monitoring
        self.connection_metrics = {
            'total_connections_created': 0,
            'total_connections_closed': 0,
            'total_errors': 0,
            'errors_by_category': defaultdict(int),
            'reconnection_attempts': 0,
            'successful_reconnections': 0
        }

        # Thread safety
        self.lock = threading.RLock()

        # Cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()

        logger.info(f"ConnectionManager initialized with max_connections={max_connections}, "
                   f"max_per_ip={max_per_ip}, timeout={connection_timeout}s")

    def set_rate_limiter(self, rate_limiter: SlidingWindowRateLimiter):
        """Set the rate limiter for tool executions."""
        self.rate_limiter = rate_limiter

    def _record_error(self, connection_id: str, error_type: ErrorCategory,
                      message: str, recoverable: bool = True):
        """Record an error for a connection."""
        try:
            if connection_id in self.active_connections:
                connection_info = self.active_connections[connection_id]
                error = ConnectionError(
                    error_type=error_type,
                    message=message,
                    timestamp=datetime.now(),
                    recoverable=recoverable,
                    retry_count=connection_info.reconnect_attempts
                )

                connection_info.error_history.append(error)
                connection_info.last_error = error
                connection_info.state = ConnectionState.FAILED

                # Keep only last 10 errors to prevent memory issues
                if len(connection_info.error_history) > 10:
                    connection_info.error_history = connection_info.error_history[-10:]

            # Update global metrics
            self.connection_metrics['total_errors'] += 1
            self.connection_metrics['errors_by_category'][error_type.value] += 1

            logger.warning(f"Error recorded for connection {connection_id}: {error_type.value} - {message}")

        except Exception as e:
            logger.error(f"Failed to record error for connection {connection_id}: {e}")

    def record_connection_error(self, connection_id: str, error: Exception,
                               context: str = "unknown") -> ErrorCategory:
        """Categorize and record a connection error."""
        error_type = self._categorize_error(error, context)
        self._record_error(connection_id, error_type, str(error))
        return error_type

    def _categorize_error(self, error: Exception, context: str) -> ErrorCategory:
        """Categorize an error based on type and context."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        # Network-related errors
        if any(keyword in error_str for keyword in ['connection', 'network', 'socket', 'timeout']):
            return ErrorCategory.NETWORK
        elif 'timeout' in error_type or 'timeout' in error_str:
            return ErrorCategory.TIMEOUT
        elif any(keyword in error_str for keyword in ['permission', 'access', 'forbidden', 'unauthorized']):
            return ErrorCategory.SECURITY
        elif any(keyword in error_str for keyword in ['resource', 'limit', 'capacity', 'memory']):
            return ErrorCategory.RESOURCE
        elif any(keyword in error_str for keyword in ['protocol', 'websocket', 'frame', 'message']):
            return ErrorCategory.PROTOCOL
        else:
            return ErrorCategory.UNKNOWN

    def add_connection(self, connection_id: str, client_ip: str,
                       user_agent: Optional[str] = None,
                       session_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Add a new connection with enhanced error recovery.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            with self.lock:
                now = datetime.now()

                # Check circuit breaker
                if self.circuit_breaker.state == "OPEN":
                    logger.warning(f"Connection rejected due to circuit breaker: {connection_id}")
                    return False, "Service temporarily unavailable"

                # Check total connection limit
                if len(self.active_connections) >= self.max_connections:
                    self._record_error(connection_id, ErrorCategory.RESOURCE,
                                     f"Maximum connections ({self.max_connections}) exceeded")
                    logger.warning(f"Connection limit exceeded: {len(self.active_connections)}/{self.max_connections}")
                    return False, f"Maximum connections ({self.max_connections}) exceeded"

                # Check per-IP limit
                if self.enable_ip_filtering:
                    ip_connections = self.connections_by_ip.get(client_ip, set())
                    if len(ip_connections) >= self.max_per_ip:
                        self._record_error(connection_id, ErrorCategory.SECURITY,
                                         f"Maximum connections per IP ({self.max_per_ip}) exceeded")
                        logger.warning(f"IP connection limit exceeded for {client_ip}: {len(ip_connections)}/{self.max_per_ip}")
                        return False, f"Maximum connections per IP ({self.max_per_ip}) exceeded"

                # Create connection info with enhanced tracking
                connection_info = ConnectionInfo(
                    connection_id=connection_id,
                    client_ip=client_ip,
                    connected_at=now,
                    last_activity=now,
                    user_agent=user_agent,
                    session_id=session_id,
                    state=ConnectionState.CONNECTED
                )

                # Add connection
                self.active_connections[connection_id] = connection_info
                self.connections_by_ip[client_ip].add(connection_id)

                # Update metrics
                self.connection_metrics['total_connections_created'] += 1

                logger.info(f"Connection established: {connection_id} from {client_ip}")
                return True, "Connection established"

        except Exception as e:
            self._record_error(connection_id, ErrorCategory.UNKNOWN, str(e))
            logger.error(f"Failed to add connection {connection_id}: {e}")
            return False, f"Connection failed: {str(e)}"

    def remove_connection(self, connection_id: str, reason: str = "normal_closure") -> bool:
        """
        Remove a connection with enhanced cleanup and state tracking.

        Returns:
            True if connection was removed, False if not found
        """
        try:
            with self.lock:
                if connection_id not in self.active_connections:
                    logger.debug(f"Attempted to remove non-existent connection: {connection_id}")
                    return False

                connection_info = self.active_connections[connection_id]
                client_ip = connection_info.client_ip

                # Update connection state
                connection_info.state = ConnectionState.CLOSED

                # Log connection closure with reason
                duration = (datetime.now() - connection_info.connected_at).total_seconds()
                logger.info(f"Connection closed: {connection_id} from {client_ip}, "
                           f"duration={duration:.2f}s, reason={reason}")

                # Remove from active connections
                del self.active_connections[connection_id]

                # Remove from IP tracking
                if client_ip in self.connections_by_ip:
                    self.connections_by_ip[client_ip].discard(connection_id)
                    if not self.connections_by_ip[client_ip]:
                        del self.connections_by_ip[client_ip]

                # Update metrics
                self.connection_metrics['total_connections_closed'] += 1

                return True

        except Exception as e:
            logger.error(f"Error removing connection {connection_id}: {e}")
            return False

    def update_activity(self, connection_id: str) -> bool:
        """
        Update the last activity time for a connection.

        Returns:
            True if connection exists and was updated, False otherwise
        """
        with self.lock:
            if connection_id not in self.active_connections:
                return False

            self.active_connections[connection_id].last_activity = datetime.now()
            return True

    def check_rate_limit(self, connection_id: str) -> Tuple[bool, float]:
        """
        Check if a tool execution is allowed for the connection.

        Returns:
            Tuple of (allowed: bool, retry_after: float)
        """
        if not self.rate_limiter:
            return True, 0.0

        with self.lock:
            if connection_id not in self.active_connections:
                return False, 0.0  # Connection doesn't exist

            return self.rate_limiter.is_allowed(connection_id)

    def attempt_reconnection(self, connection_id: str, client_ip: str,
                           user_agent: Optional[str] = None,
                           session_id: Optional[str] = None) -> Tuple[bool, str]:
        """Attempt to reconnect a previously failed connection."""
        try:
            with self.lock:
                # Check if connection exists and is in failed state
                if connection_id in self.active_connections:
                    connection_info = self.active_connections[connection_id]
                    if connection_info.state == ConnectionState.FAILED:
                        # Update reconnection attempts
                        connection_info.reconnect_attempts += 1
                        connection_info.state = ConnectionState.RECONNECTING

                        # Update metrics
                        self.connection_metrics['reconnection_attempts'] += 1

                        logger.info(f"Attempting reconnection for {connection_id} "
                                   f"(attempt {connection_info.reconnect_attempts})")

                        # Try to re-establish connection
                        success, message = self.add_connection(
                            connection_id, client_ip, user_agent, session_id
                        )

                        if success:
                            connection_info.state = ConnectionState.CONNECTED
                            connection_info.reconnect_attempts = 0  # Reset on success
                            self.connection_metrics['successful_reconnections'] += 1
                            logger.info(f"Reconnection successful for {connection_id}")
                        else:
                            connection_info.state = ConnectionState.FAILED
                            logger.warning(f"Reconnection failed for {connection_id}: {message}")

                        return success, message
                    else:
                        return False, f"Connection not in failed state: {connection_info.state.value}"
                else:
                    # New connection attempt
                    return self.add_connection(connection_id, client_ip, user_agent, session_id)

        except Exception as e:
            logger.error(f"Reconnection attempt failed for {connection_id}: {e}")
            return False, f"Reconnection failed: {str(e)}"

    def graceful_degradation_check(self) -> Dict[str, Any]:
        """Check system health and determine if graceful degradation is needed."""
        with self.lock:
            total_connections = len(self.active_connections)
            connection_utilization = total_connections / self.max_connections

            # Check error rates
            recent_errors = sum(self.connection_metrics['errors_by_category'].values())
            error_rate = recent_errors / max(1, self.connection_metrics['total_connections_created'])

            # Determine degradation level
            degradation_level = "normal"
            recommendations = []

            if connection_utilization > 0.9:
                degradation_level = "high_load"
                recommendations.append("Reduce connection acceptance rate")
            elif connection_utilization > 0.8:
                degradation_level = "moderate_load"
                recommendations.append("Monitor connection health closely")

            if error_rate > 0.1:  # More than 10% error rate
                degradation_level = "high_error_rate"
                recommendations.append("Enable circuit breaker protection")
                recommendations.append("Increase error recovery timeouts")

            if self.circuit_breaker.state == "OPEN":
                degradation_level = "circuit_open"
                recommendations.append("Service temporarily unavailable")
                recommendations.append("Check upstream service health")

            return {
                'degradation_level': degradation_level,
                'connection_utilization': connection_utilization,
                'error_rate': error_rate,
                'circuit_breaker_state': self.circuit_breaker.state,
                'recommendations': recommendations
            }

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics about active connections."""
        with self.lock:
            now = datetime.now()

            # Count connections by IP
            ip_counts = {}
            for ip, connections in self.connections_by_ip.items():
                ip_counts[ip] = len(connections)

            # Calculate average connection age
            total_age = 0.0
            if self.active_connections:
                for conn in self.active_connections.values():
                    age = (now - conn.connected_at).total_seconds()
                    total_age += age
                avg_age = total_age / len(self.active_connections)
            else:
                avg_age = 0.0

            # Count connections by state
            state_counts = defaultdict(int)
            for conn in self.active_connections.values():
                state_counts[conn.state.value] += 1

            # Get degradation status
            degradation_info = self.graceful_degradation_check()

            return {
                'total_connections': len(self.active_connections),
                'connections_by_ip': ip_counts,
                'connections_by_state': dict(state_counts),
                'max_connections': self.max_connections,
                'max_per_ip': self.max_per_ip,
                'average_connection_age_seconds': avg_age,
                'rate_limiting_enabled': self.rate_limiter is not None,
                'connection_metrics': self.connection_metrics.copy(),
                'degradation_status': degradation_info,
                'circuit_breaker_state': self.circuit_breaker.state
            }

    def _cleanup_loop(self):
        """Enhanced background thread to clean up expired connections and perform health checks."""
        consecutive_errors = 0
        max_consecutive_errors = 5

        while True:
            try:
                self._cleanup_expired_connections()
                self._perform_health_checks()
                consecutive_errors = 0  # Reset on successful run
                time.sleep(60)  # Check every minute
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Connection cleanup error (attempt {consecutive_errors}/{max_consecutive_errors}): {e}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.critical("Too many consecutive cleanup errors, entering degraded mode")
                    time.sleep(300)  # Wait 5 minutes before retrying
                    consecutive_errors = 0
                else:
                    time.sleep(30)  # Wait 30 seconds before retrying

    def _cleanup_expired_connections(self):
        """Remove connections that have exceeded the timeout with enhanced logging."""
        with self.lock:
            now = datetime.now()
            expired_connections = []
            failed_connections = []

            for connection_id, connection_info in self.active_connections.items():
                age = (now - connection_info.last_activity).total_seconds()

                # Check for expired connections
                if age > self.connection_timeout:
                    expired_connections.append((connection_id, age))

                # Check for connections with too many errors
                if (connection_info.state == ConnectionState.FAILED and
                    len(connection_info.error_history) > 5):
                    failed_connections.append(connection_id)

            # Remove expired connections
            for connection_id, age in expired_connections:
                self.remove_connection(connection_id, f"expired_after_{age:.0f}s")

            # Remove failed connections
            for connection_id in failed_connections:
                self.remove_connection(connection_id, "too_many_errors")

            if expired_connections or failed_connections:
                logger.info(f"Cleaned up {len(expired_connections)} expired and "
                           f"{len(failed_connections)} failed connections")

    def _perform_health_checks(self):
        """Perform periodic health checks on connections."""
        try:
            with self.lock:
                now = datetime.now()
                unhealthy_connections = []

                for connection_id, connection_info in self.active_connections.items():
                    # Check for stale connections (no activity for extended period)
                    inactivity_period = (now - connection_info.last_activity).total_seconds()
                    if inactivity_period > self.connection_timeout * 0.8:  # 80% of timeout
                        logger.debug(f"Connection {connection_id} showing signs of inactivity: {inactivity_period:.0f}s")

                    # Check for connections with high error rates
                    if connection_info.error_history:
                        recent_errors = [e for e in connection_info.error_history
                                       if (now - e.timestamp).total_seconds() < 300]  # Last 5 minutes
                        if len(recent_errors) > 3:
                            unhealthy_connections.append(connection_id)

                # Log health summary
                total_connections = len(self.active_connections)
                if total_connections > 0:
                    healthy_connections = total_connections - len(unhealthy_connections)
                    health_percentage = (healthy_connections / total_connections) * 100

                    if health_percentage < 80:
                        logger.warning(f"Connection health degraded: {health_percentage:.1f}% healthy "
                                     f"({healthy_connections}/{total_connections})")

                    # Update circuit breaker based on health
                    if health_percentage < 50 and self.circuit_breaker.state == "CLOSED":
                        logger.warning("Connection health critically low, opening circuit breaker")
                        self.circuit_breaker.state = "OPEN"

        except Exception as e:
            logger.error(f"Health check failed: {e}")


# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager


def initialize_connection_manager(config):
    """Initialize the global connection manager with configuration."""
    global _connection_manager

    connection_limits = config.connection_limits
    rate_limits = config.rate_limits

    _connection_manager = ConnectionManager(
        max_connections=connection_limits.max_concurrent_connections,
        max_per_ip=connection_limits.max_connections_per_ip,
        connection_timeout=connection_limits.connection_timeout,
        enable_ip_filtering=connection_limits.enable_ip_filtering
    )

    # Set up rate limiter if enabled
    if config.enable_rate_limiting:
        rate_limiter = SlidingWindowRateLimiter(
            max_requests=rate_limits.max_requests_per_minute,
            window_seconds=rate_limits.rate_limit_window_seconds,
            burst_limit=rate_limits.burst_limit
        )
        _connection_manager.set_rate_limiter(rate_limiter)

    return _connection_manager