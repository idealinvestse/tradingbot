"""MLflow integration for model versioning and tracking."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import mlflow
import mlflow.sklearn
from pydantic import BaseModel

from app.strategies.utils import get_json_logger

logger = get_json_logger("mlflow_manager")


class MLflowConfig(BaseModel):
    """MLflow configuration."""
    
    tracking_uri: str = "mlruns"
    experiment_name: str = "trading_strategies"
    registry_uri: Optional[str] = None
    artifact_location: Optional[str] = None


class ModelVersionManager:
    """Manage model versions with MLflow."""
    
    def __init__(self, config: MLflowConfig = None):
        """Initialize model version manager."""
        self.config = config or MLflowConfig()
        self._setup_mlflow()
        
    def _setup_mlflow(self):
        """Setup MLflow configuration."""
        mlflow.set_tracking_uri(self.config.tracking_uri)
        mlflow.set_experiment(self.config.experiment_name)
        if self.config.registry_uri:
            mlflow.set_registry_uri(self.config.registry_uri)
    
    def start_run(self, run_name: str = None) -> str:
        """Start a new MLflow run."""
        run = mlflow.start_run(run_name=run_name)
        logger.info(f"Started MLflow run: {run.info.run_id}")
        return run.info.run_id
    
    def log_params(self, params: Dict[str, Any]):
        """Log parameters."""
        for key, value in params.items():
            mlflow.log_param(key, value)
    
    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None):
        """Log metrics."""
        for key, value in metrics.items():
            mlflow.log_metric(key, value, step=step)
    
    def log_model(self, model: Any, artifact_path: str, model_name: str = None):
        """Log model artifact."""
        mlflow.sklearn.log_model(model, artifact_path)
        
        if model_name:
            # Register model
            model_uri = f"runs:/{mlflow.active_run().info.run_id}/{artifact_path}"
            mlflow.register_model(model_uri, model_name)
            logger.info(f"Model registered: {model_name}")
    
    def end_run(self):
        """End current run."""
        mlflow.end_run()
        logger.info("MLflow run ended")
    
    def load_model(self, model_name: str, version: str = "latest") -> Any:
        """Load model from registry."""
        if version == "latest":
            model_uri = f"models:/{model_name}/latest"
        else:
            model_uri = f"models:/{model_name}/{version}"
        
        model = mlflow.sklearn.load_model(model_uri)
        logger.info(f"Loaded model: {model_name} v{version}")
        return model
    
    def compare_models(self, model_names: list) -> Dict:
        """Compare multiple model versions."""
        comparison = {}
        
        for model_name in model_names:
            client = mlflow.tracking.MlflowClient()
            versions = client.search_model_versions(f"name='{model_name}'")
            
            comparison[model_name] = {
                "versions": len(versions),
                "latest_version": versions[-1].version if versions else None,
                "latest_metrics": self._get_run_metrics(versions[-1].run_id) if versions else {}
            }
        
        return comparison
    
    def _get_run_metrics(self, run_id: str) -> Dict:
        """Get metrics for a specific run."""
        client = mlflow.tracking.MlflowClient()
        run = client.get_run(run_id)
        return run.data.metrics


class ExperimentTracker:
    """Track experiments and hyperparameters."""
    
    def __init__(self, experiment_name: str):
        """Initialize experiment tracker."""
        self.experiment_name = experiment_name
        self.manager = ModelVersionManager()
        
    def track_strategy_training(self, strategy_name: str, params: Dict, metrics: Dict, model: Any = None):
        """Track strategy training session."""
        run_name = f"{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        with mlflow.start_run(run_name=run_name):
            # Log parameters
            mlflow.log_params(params)
            
            # Log metrics
            for metric_name, value in metrics.items():
                mlflow.log_metric(metric_name, value)
            
            # Log model if provided
            if model:
                mlflow.sklearn.log_model(model, "model")
            
            # Log additional artifacts
            mlflow.log_dict(params, "params.json")
            mlflow.log_dict(metrics, "metrics.json")
            
            logger.info(f"Tracked experiment: {run_name}")
    
    def get_best_run(self, metric: str = "profit_total", ascending: bool = False) -> Dict:
        """Get best run based on metric."""
        client = mlflow.tracking.MlflowClient()
        experiment = client.get_experiment_by_name(self.experiment_name)
        
        if not experiment:
            return {}
        
        runs = client.search_runs(experiment.experiment_id)
        
        if not runs:
            return {}
        
        # Sort by metric
        sorted_runs = sorted(runs, 
                           key=lambda x: x.data.metrics.get(metric, 0),
                           reverse=not ascending)
        
        best_run = sorted_runs[0]
        
        return {
            "run_id": best_run.info.run_id,
            "params": best_run.data.params,
            "metrics": best_run.data.metrics,
            "start_time": best_run.info.start_time,
            "status": best_run.info.status
        }
