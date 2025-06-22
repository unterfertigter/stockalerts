import logging

from flask import Blueprint, flash, redirect, render_template, request, url_for
from wtforms import BooleanField, FloatField, Form, validators

from config_manager import config_lock, save_config, shared_config

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
    isin = request.form.get("isin")
    if not isin:
        flash("ISIN is missing from the form submission.", "error")
        return redirect(url_for("admin_ui.admin_page"))
    form = ThresholdForm(request.form)
    if not form.validate():
        flash(f"Invalid input for ISIN {isin}: {form.errors}", "error")
        return redirect(url_for("admin_ui.admin_page"))
    upper = form.upper_threshold.data
    lower = form.lower_threshold.data
    active = form.active.data
    with config_lock:
        for entry in shared_config:
            if entry["isin"] == isin:
                entry["upper_threshold"] = upper if upper is not None else None
                entry["lower_threshold"] = lower if lower is not None else None
                entry["active"] = active
                break
        save_config(shared_config)
    logger.info(f"Config updated via admin UI for ISIN {isin}: upper={upper}, lower={lower}, active={active}")
    return redirect(url_for("admin_ui.admin_page"))


@admin_ui.route("/add", methods=["POST"])
def add_isin():
    isin = request.form.get("new_isin", "").strip().upper()
    if not isin or len(isin) != 12 or not isin.isalnum():
        flash("Invalid ISIN. Must be 12 alphanumeric characters.", "error")
        return redirect(url_for("admin_ui.admin_page"))
    with config_lock:
        for entry in shared_config:
            if entry["isin"] == isin:
                flash(f"ISIN {isin} already exists.", "error")
                return redirect(url_for("admin_ui.admin_page"))
        shared_config.append(
            {
                "isin": isin,
                "upper_threshold": None,
                "lower_threshold": None,
                "active": True,
            }
        )
        save_config(shared_config)
    logger.info(f"Added new ISIN {isin} via admin UI.")
    flash(f"ISIN {isin} added.", "success")
    return redirect(url_for("admin_ui.admin_page"))


@admin_ui.route("/delete", methods=["POST"])
def delete_isin():
    isin = request.form.get("delete_isin", "").strip().upper()
    with config_lock:
        before = len(shared_config)
        shared_config[:] = [entry for entry in shared_config if entry["isin"] != isin]
        after = len(shared_config)
        save_config(shared_config)
    if after < before:
        logger.info(f"Deleted ISIN {isin} via admin UI.")
        flash(f"ISIN {isin} deleted.", "success")
    else:
        flash(f"ISIN {isin} not found.", "error")
    return redirect(url_for("admin_ui.admin_page"))
