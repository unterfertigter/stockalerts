import logging

from flask import Blueprint, jsonify, request

from config_manager import config_lock, save_config, shared_config

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__)


def validate_isin(isin):
    # Basic ISIN validation: 12 alphanumeric characters
    return isinstance(isin, str) and len(isin) == 12 and isin.isalnum()


@api.route("/api/config", methods=["GET"])
def api_get_config():
    # API endpoint to get the current config as JSON
    with config_lock:
        return jsonify(shared_config)


@api.route("/api/config", methods=["POST"])
def api_update_config():
    # API endpoint to update thresholds for a given ISIN
    data = request.json
    isin = data.get("isin")
    upper = data.get("upper_threshold")
    lower = data.get("lower_threshold")
    if not validate_isin(isin):
        logger.warning(f"Invalid ISIN received via API: {isin}")
        return {"status": "error", "message": "Invalid ISIN."}, 400
    try:
        upper = float(upper) if upper is not None else None
        lower = float(lower) if lower is not None else None
    except (TypeError, ValueError):
        logger.warning(f"Invalid threshold values for ISIN {isin}: upper={upper}, lower={lower}")
        return {"status": "error", "message": "Invalid threshold values."}, 400
    with config_lock:
        for entry in shared_config:
            if entry["isin"] == isin:
                entry["upper_threshold"] = upper
                entry["lower_threshold"] = lower
        save_config(shared_config)
    logger.info(f"Config updated via API for ISIN {isin}: upper={upper}, lower={lower}")
    return {"status": "ok"}
