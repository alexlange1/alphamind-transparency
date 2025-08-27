#!/usr/bin/env python3
"""
Professional logging setup with WandB integration
Inspired by Sturdy Subnet's monitoring approach
"""

import logging
import os
import sys
from typing import Optional
import wandb


class AlphamindLogger:
    """Enhanced logger with WandB integration"""
    
    def __init__(
        self,
        name: str,
        log_level: str = "INFO",
        use_wandb: bool = True,
        wandb_project: str = "alphamind-tao20",
        wandb_entity: Optional[str] = None
    ):
        self.name = name
        self.use_wandb = use_wandb
        
        # Setup standard logging
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Console handler with formatting
        if not self.logger.handlers:
            console_handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # Initialize WandB if requested
        if self.use_wandb:
            self._setup_wandb(wandb_project, wandb_entity)
    
    def _setup_wandb(self, project: str, entity: Optional[str]):
        """Setup WandB logging"""
        try:
            # Check if WandB is disabled via environment
            if os.getenv("WANDB_MODE") == "disabled":
                self.use_wandb = False
                self.logger.info("WandB disabled via WANDB_MODE environment variable")
                return
            
            # Initialize WandB
            wandb.init(
                project=project,
                entity=entity,
                name=f"{self.name}_{os.getpid()}",
                config={
                    "subnet": "alphamind-tao20",
                    "version": "1.0.0",
                    "node_type": self.name
                },
                tags=[self.name, "tao20", "bittensor"]
            )
            
            self.logger.info(f"WandB initialized for project: {project}")
            
        except Exception as e:
            self.logger.warning(f"Failed to initialize WandB: {e}")
            self.use_wandb = False
    
    def log_metrics(self, metrics: dict, step: Optional[int] = None):
        """Log metrics to both console and WandB"""
        # Console logging
        metrics_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
        self.logger.info(f"Metrics: {metrics_str}")
        
        # WandB logging
        if self.use_wandb:
            try:
                wandb.log(metrics, step=step)
            except Exception as e:
                self.logger.warning(f"Failed to log to WandB: {e}")
    
    def log_config(self, config: dict):
        """Log configuration"""
        self.logger.info(f"Configuration: {config}")
        
        if self.use_wandb:
            try:
                wandb.config.update(config)
            except Exception as e:
                self.logger.warning(f"Failed to log config to WandB: {e}")
    
    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)
    
    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)


def get_logger(
    name: str,
    log_level: str = "INFO",
    use_wandb: bool = True,
    wandb_project: str = "alphamind-tao20"
) -> AlphamindLogger:
    """Get configured logger instance"""
    return AlphamindLogger(
        name=name,
        log_level=log_level,
        use_wandb=use_wandb,
        wandb_project=wandb_project
    )
