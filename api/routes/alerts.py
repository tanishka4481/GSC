"""
PROVCHAIN — Alerts Route
=========================
GET /alerts — Get propagation anomaly alerts for a publisher.
POST /alerts/{alert_id}/acknowledge — Mark an alert as read.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from core.exceptions import StorageError
from monitoring.propagation_analyzer import get_alerts_for_owner, acknowledge_alert
from monitoring.models import AlertRecord

router = APIRouter(tags=["Monitoring"])


@router.get("/alerts", response_model=List[AlertRecord])
async def get_alerts(
    owner_id: str = Query(..., description="Publisher/owner ID to fetch alerts for"),
    acknowledged: Optional[bool] = Query(None, description="Filter by acknowledged status")
):
    """
    Get propagation anomaly alerts for the publisher.
    
    Returns alerts from Firestore generated during scan analysis.
    """
    try:
        alerts = get_alerts_for_owner(owner_id, acknowledged)
        return alerts
    except StorageError as e:
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/alerts/{alert_id}/acknowledge")
async def ack_alert(alert_id: str):
    """
    Mark an alert as acknowledged.
    """
    try:
        success = acknowledge_alert(alert_id)
        if not success:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"status": "success", "message": f"Alert {alert_id} acknowledged"}
    except StorageError as e:
        raise HTTPException(status_code=500, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
