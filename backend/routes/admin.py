# backend/routes/admin.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from decorators import admin_required
from extensions import db
from models import Lead, User
import logging

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

@admin_bp.route('/leads', methods=['GET'])
@jwt_required()
@admin_required
def get_all_leads():
    """
    Retrieves all leads. Accessible only to admins.
    """
    leads = Lead.query.all()
    leads_data = []
    for lead in leads:
        leads_data.append({
            'id': lead.id,
            'referrer': lead.referrer.name,
            'name': lead.name,
            'age': lead.age,
            'loan_amount': lead.loan_amount,
            'loan_tenure': lead.loan_tenure,
            'current_repayment': lead.current_repayment,
            'status': lead.status,
            'created_at': lead.created_at,
            'updated_at': lead.updated_at
        })
    return jsonify({'leads': leads_data}), 200

@admin_bp.route('/lead/<int:lead_id>', methods=['PUT'])
@jwt_required()
@admin_required
def update_lead_status(lead_id):
    """
    Updates the status of a specific lead. Accessible only to admins.
    """
    data = request.get_json()
    new_status = data.get('status')

    if not new_status:
        return jsonify({'message': 'Status is required.'}), 400

    lead = Lead.query.get(lead_id)
    if not lead:
        return jsonify({'message': 'Lead not found.'}), 404

    lead.status = new_status
    db.session.commit()

    return jsonify({'message': 'Lead status updated successfully.'}), 200

# Add more admin routes as needed
