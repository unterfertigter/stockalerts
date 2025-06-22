import logging

from flask import Blueprint, redirect, render_template, request, url_for
from wtforms import BooleanField, FloatField, Form, validators

from config_manager import CONFIG_PATH, config_lock, save_config, shared_config

logger = logging.getLogger(__name__)

admin_ui = Blueprint("admin_ui", __name__)


class ThresholdForm(Form):
    upper_threshold = FloatField("Upper Threshold", [validators.Optional()])
    lower_threshold = FloatField("Lower Threshold", [validators.Optional()])
    active = BooleanField("Active")


@admin_ui.route("/", methods=["GET"])
def admin_page():
    # Render the admin UI with the current config
    with config_lock:
        config = list(shared_config)
    return render_template("admin.html", config=config)


@admin_ui.route("/update", methods=["POST"])
def update_threshold():
    # Handle updates to thresholds and active status from the admin UI
    isin = request.form["isin"]
    form = ThresholdForm(request.form)
    if not form.validate():
        logger.warning(f"Invalid input for ISIN {isin}: {form.errors}")
        return redirect(url_for("admin_ui.admin_page"))
    upper = form.upper_threshold.data
    lower = form.lower_threshold.data
    active = form.active.data
    with config_lock:
        for entry in shared_config:
            if entry["isin"] == isin:
                entry["upper_threshold"] = upper if upper is not None else None
                entry["lower_threshold"] = lower if lower is not None else None
                entry["active"] = bool(active)
        save_config(CONFIG_PATH, shared_config)
    logger.info(f"Config updated via admin UI for ISIN {isin}: upper={upper}, lower={lower}, active={active}")
    return redirect(url_for("admin_ui.admin_page"))
