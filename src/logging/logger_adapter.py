"""Logger adapter to make different logger types compatible with BotLogger interface."""

from typing import Any, Dict, Optional


class LoggerAdapter:
    """Adapter to make any logger compatible with BotLogger interface.
    
    This adapter wraps loggers that don't have the log_info, log_error, log_warning
    methods and provides a compatible interface.
    """
    
    def __init__(self, logger):
        """Initialize the adapter with any logger.
        
        Args:
            logger: Any logger object (LumibotLogger, Python logger, etc.)
        """
        self.logger = logger
        
    def log_info(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log an info message.
        
        Args:
            message: Log message
            context: Optional context dictionary for structured data
        """
        if hasattr(self.logger, 'log_info'):
            self.logger.log_info(message, context)
        elif hasattr(self.logger, 'info'):
            context_str = self._format_context(context) if context else ""
            self.logger.info(f"{message}{context_str}")
        else:
            # Fallback to print if no logging method available
            print(f"INFO: {message}")
    
    def log_warning(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log a warning message.
        
        Args:
            message: Log message
            context: Optional context dictionary for structured data
        """
        if hasattr(self.logger, 'log_warning'):
            self.logger.log_warning(message, context)
        elif hasattr(self.logger, 'warning'):
            context_str = self._format_context(context) if context else ""
            self.logger.warning(f"{message}{context_str}")
        else:
            print(f"WARNING: {message}")
    
    def log_error(
        self,
        message: str,
        error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Log an error message.
        
        Args:
            message: Log message
            error: Optional exception object
            context: Optional context dictionary for structured data
        """
        if hasattr(self.logger, 'log_error'):
            self.logger.log_error(message, error, context)
        elif hasattr(self.logger, 'error'):
            context_str = self._format_context(context) if context else ""
            error_str = f" | Error: {type(error).__name__}: {str(error)}" if error else ""
            self.logger.error(f"{message}{context_str}{error_str}")
        else:
            print(f"ERROR: {message}")
    
    def log_debug(self, message: str, context: Optional[Dict[str, Any]] = None):
        """Log a debug message.
        
        Args:
            message: Log message
            context: Optional context dictionary for structured data
        """
        if hasattr(self.logger, 'log_debug'):
            self.logger.log_debug(message, context)
        elif hasattr(self.logger, 'debug'):
            context_str = self._format_context(context) if context else ""
            self.logger.debug(f"{message}{context_str}")
        else:
            pass  # Skip debug messages if no logger available
    
    def _format_context(self, context: Optional[Dict[str, Any]]) -> str:
        """Format context dictionary for logging.
        
        Args:
            context: Context dictionary
            
        Returns:
            Formatted context string
        """
        if not context:
            return ""
        
        context_parts = []
        for key, value in context.items():
            # Mask sensitive keys
            if any(
                sensitive in key.lower() for sensitive in ["key", "secret", "password", "token"]
            ):
                value = "***MASKED***"
            context_parts.append(f"{key}={value}")
        
        return " | " + " | ".join(context_parts) if context_parts else ""
