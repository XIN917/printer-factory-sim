"""Simulation control API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import InventoryLog, ManufacturingOrder, OrderStatus, PurchaseOrder, PurchaseOrderStatus
from app.schemas.simulation import SimulationStatusResponse, ProductionStatsResponse
from app.services.daily_cycle import get_daily_processor
from app.services.event_logger import EventLogger
from app.services.production_engine import get_production_engine
from app.services.inventory_manager import get_inventory_manager
from app.utils.config_loader import load_config

router = APIRouter(prefix="/simulation", tags=["Simulation"])


# Persistent state stored in memory (in production, this would be in database)
_sim_state = {
    "current_day": 1,
    "running": False,
}


@router.get("/status", response_model=SimulationStatusResponse)
def get_simulation_status(db: Session = Depends(get_db)):
    """Get current simulation status."""
    return SimulationStatusResponse(
        current_day=_sim_state["current_day"],
        running=_sim_state["running"],
    )


@router.post("/advance")
def advance_day(db: Session = Depends(get_db)):
    """Advance simulation by one day."""
    current_day = _sim_state["current_day"]
    next_day = current_day + 1

    # Load config for demand generation parameters
    try:
        config = load_config("config/default_config.yaml")
    except FileNotFoundError:
        config = {}

    # Use the daily cycle processor to handle all day-advance events
    processor = get_daily_processor()
    results = processor.process_day_advance(db, next_day, config)

    # Update state
    _sim_state["current_day"] = next_day
    _sim_state["running"] = True

    # Log the day advance event
    EventLogger.log_event(
        db=db,
        day=next_day,
        event_type="DAY_ADVANCED",
        category="SYSTEM",
        description=f"Simulation advanced to day {next_day}",
        details={
            "deliveries_received": results["deliveries_processed"],
            "orders_created": results["orders_generated"],
            "orders_completed": results.get("total_produced", 0),
        },
    )

    return {
        "new_day": next_day,
        "deliveries_processed": results["deliveries_processed"],
        "orders_generated": results["orders_generated"],
        "production_completed": results.get("production_completed", []),
        "capacity_used": results.get("capacity_used", {}),
        "total_produced": results.get("total_produced", 0),
        "inventory_updates": results["inventory_updates"],
        "shortages_detected": results.get("shortages_detected", []),
    }


@router.post("/reset")
def reset_simulation(db: Session = Depends(get_db)):
    """Reset simulation to day 1."""
    from app.db import SessionLocal

    _sim_state["current_day"] = 1
    _sim_state["running"] = False

    # Reset all orders to pending
    db.query(ManufacturingOrder).update({
        "status": OrderStatus.PENDING,
        "released_day": None,
        "completed_day": None
    })

    # Cancel all pending purchase orders
    db.query(PurchaseOrder).filter(PurchaseOrder.status == PurchaseOrderStatus.PENDING).update(
        {"status": PurchaseOrderStatus.CANCELLED}
    )

    db.commit()

    # Log reset event
    EventLogger.log_event(
        db=db,
        day=1,
        event_type="SIMULATION_RESET",
        category="SYSTEM",
        description="Simulation reset to day 1",
    )

    return {"success": True, "message": "Simulation reset to day 1"}


@router.get("/config")
def get_simulation_config():
    """Get current simulation configuration."""
    try:
        config = load_config("config/default_config.yaml")
        return {
            "simulation": config.get("simulation", {}),
            "demand_generation": config.get("demand_generation", {}),
            "production": config.get("production", {}),
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Configuration file not found")


@router.get("/production-stats", response_model=ProductionStatsResponse)
def get_production_stats(db: Session = Depends(get_db)):
    """Get current production statistics."""
    production_engine = get_production_engine()
    stats = production_engine.get_production_statistics(db, _sim_state["current_day"])

    return ProductionStatsResponse(**stats)


@router.get("/shortages")
def get_material_shortages(db: Session = Depends(get_db)):
    """Get current material shortages for pending/released orders."""
    inventory_mgr = get_inventory_manager()
    shortages = inventory_mgr.detect_shortages(db)
    return {"shortages": shortages}


@router.get("/low-stock-alerts")
def get_low_stock_alerts(db: Session = Depends(get_db)):
    """Get low stock alerts based on future requirements."""
    inventory_mgr = get_inventory_manager()
    alerts = inventory_mgr.get_low_stock_alerts(db)
    return {"alerts": alerts}
