from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List

from celery.result import AsyncResult
from app.api.deps import get_current_admin_user
from app.core.celery import celery_app

router = APIRouter()


@router.get("/status/{task_id}")
async def get_task_status(
    task_id: str,
    _=Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Get the status of a Celery task"""
    task = AsyncResult(task_id, app=celery_app)
    
    response = {
        "task_id": task_id,
        "status": task.status,
        "successful": task.successful(),
        "failed": task.failed(),
    }
    
    # Add result or error info if available
    if task.ready():
        if task.successful():
            response["result"] = task.get()
        else:
            response["error"] = str(task.result)
            
    return response


@router.get("/active")
async def get_active_tasks(
    _=Depends(get_current_admin_user)
) -> Dict[str, List[Dict[str, Any]]]:
    """Get currently active tasks by queue"""
    # Get active tasks from each worker
    inspect = celery_app.control.inspect()
    active = inspect.active() or {}
    
    # Group tasks by queue
    tasks_by_queue = {
        "queries": [],
        "sync": [],
        "cleanup": [],
        "other": []
    }
    
    for worker, tasks in active.items():
        for task in tasks:
            queue = task.get("delivery_info", {}).get("routing_key", "other")
            task_info = {
                "id": task["id"],
                "name": task["name"],
                "args": task["args"],
                "kwargs": task["kwargs"],
                "worker": worker,
                "started": task["time_start"],
            }
            tasks_by_queue.setdefault(queue, []).append(task_info)
    
    return tasks_by_queue


@router.get("/queues")
async def get_queue_stats(
    _=Depends(get_current_admin_user)
) -> Dict[str, Dict[str, Any]]:
    """Get statistics for each queue"""
    inspect = celery_app.control.inspect()
    
    # Get various task stats
    active = inspect.active() or {}
    reserved = inspect.reserved() or {}
    scheduled = inspect.scheduled() or {}
    
    # Initialize queue stats
    queues = {
        "queries": {"active": 0, "reserved": 0, "scheduled": 0},
        "sync": {"active": 0, "reserved": 0, "scheduled": 0},
        "cleanup": {"active": 0, "reserved": 0, "scheduled": 0},
        "other": {"active": 0, "reserved": 0, "scheduled": 0}
    }
    
    # Count active tasks
    for tasks in active.values():
        for task in tasks:
            queue = task.get("delivery_info", {}).get("routing_key", "other")
            queues.setdefault(queue, {"active": 0, "reserved": 0, "scheduled": 0})
            queues[queue]["active"] += 1
    
    # Count reserved tasks
    for tasks in reserved.values():
        for task in tasks:
            queue = task.get("delivery_info", {}).get("routing_key", "other")
            queues.setdefault(queue, {"active": 0, "reserved": 0, "scheduled": 0})
            queues[queue]["reserved"] += 1
    
    # Count scheduled tasks
    for tasks in scheduled.values():
        for task in tasks:
            queue = task.get("delivery_info", {}).get("routing_key", "other")
            queues.setdefault(queue, {"active": 0, "reserved": 0, "scheduled": 0})
            queues[queue]["scheduled"] += 1
    
    return queues


@router.get("/workers")
async def get_worker_stats(
    _=Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Get statistics for Celery workers"""
    inspect = celery_app.control.inspect()
    
    stats = inspect.stats() or {}
    ping = inspect.ping() or {}
    
    workers = {}
    for worker, worker_stats in stats.items():
        workers[worker] = {
            "status": "online" if worker in ping else "offline",
            "pool": worker_stats.get("pool", {}),
            "total_processes": worker_stats.get("pool", {}).get("max-concurrency", 0),
            "broker": worker_stats.get("broker", {}),
            "uptime": worker_stats.get("uptime", 0),
        }
    
    return {
        "total_workers": len(workers),
        "online_workers": len(ping),
        "workers": workers
    } 