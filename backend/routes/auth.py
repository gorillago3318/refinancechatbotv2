# backend/routes/auth.py

import os
from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from extensions import db
from models import User
from decorators import user_required, admin_required, agent_required, referrer_required
import logging

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Registers a new user.
    """
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'user')  # Default role is 'user'

    if not all([name, email, password]):
        return jsonify({'message': 'Name, email, and password are required.'}), 400

    if role not in ['user', 'admin', 'agent', 'referrer']:
        return jsonify({'message': 'Invalid role specified.'}), 400

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({'message': 'User with this email already exists.'}), 400

    hashed_password = generate_password_hash(password, method='sha256')
    new_user = User(
        name=name,
        email=email,
        password=hashed_password,
        role=role
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully.'}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Logs in a user and returns a JWT.
    """
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({'message': 'Email and password are required.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'User not found.'}), 404

    if check_password_hash(user.password, password):
        access_token = create_access_token(identity=user.id, additional_claims={"role": user.role})
        return jsonify({'access_token': access_token}), 200
    else:
        return jsonify({'message': 'Incorrect password.'}), 401

@auth_bp.route('/protected', methods=['GET'])
@jwt_required()
@user_required
def protected():
    """
    A protected route accessible only to users with 'user' role.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    return jsonify({'message': f'Hello, {user.name}! This is a protected route.'}), 200

# Similarly, define routes for admin, agent, and referrer if needed
