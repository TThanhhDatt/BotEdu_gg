# logging_config.py - Simple Version
import logging
from rich.logging import RichHandler
from rich.console import Console

console = Console(force_terminal=True, width=120)

class ColoredLogger:
    """Wrapper class cung cấp các method với màu cố định"""
    
    def __init__(self, logger):
        self.logger = logger
    
    def debug(self, message, color="cyan"):
        self.logger.debug(f"🔍 [{color}]{message}[/{color}]")
    
    def info(self, message, color="bright_magenta"):
        self.logger.info(f"ℹ️  [{color}]{message}[/{color}]")
    
    def warning(self, message, color="orange3"):
        self.logger.warning(f"⚠️  [{color}]{message}[/{color}]")
    
    def error(self, message, color="bright_red"):
        self.logger.error(f"❌ [{color}]{message}[/{color}]")
    
    def critical(self, message, color="bold purple"):
        self.logger.critical(f"🚨 [{color}]{message}[/{color}]")
    
    def success(self, message):
        self.logger.info(f"✅ [bold green]{message}[/bold green]")
    
    def fail(self, message):
        self.logger.error(f"💥 [bold red on yellow]{message}[/bold red on yellow]")
    
    def highlight(self, message):
        self.logger.info(f"⭐ [bold yellow on blue]{message}[/bold yellow on blue]")
    
    def subtle(self, message):
        self.logger.info(f"[dim]{message}[/dim]")

def setup_logging(name):
    # Silence noisy third-party loggers
    for noisy_logger in ['urllib3', 'openai', 'langsmith', 'httpcore', 'httpx']:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Console handler với Rich
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True,
        rich_tracebacks=True
    )
    rich_handler.setLevel(logging.DEBUG)
    
    # File handler - QUAN TRỌNG: Không dùng Rich markup cho file!
    file_handler = logging.FileHandler("app.log", encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    
    # Formatter cho file (plain text)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    
    # Add handlers
    logger.addHandler(rich_handler)
    logger.addHandler(file_handler)
    
    return ColoredLogger(logger)

# Test function
def test_logging():
    logger = setup_logging("app.test")
    
    logger.debug("Debug message - should appear in console only")
    logger.info("Info message - should appear in both console and file")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.success("Success message")
    
    print("\n✅ Check app.log file!")
    
    # Show file contents
    try:
        with open("app.log", "r", encoding='utf-8') as f:
            print("\n📄 File contents:")
            print(f.read())
    except FileNotFoundError:
        print("❌ app.log file not found!")

if __name__ == "__main__":
    test_logging()