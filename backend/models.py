from datetime import datetime
from .extensions import db

class User(db.Model):
    """Table to store system users."""
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    wa_id = db.Column(db.String(20), unique=True, nullable=False)  # WhatsApp ID for users
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Should store hashed passwords
    role = db.Column(db.String(50), nullable=False, default='user')  # Roles: user, admin, agent, referrer

    def __repr__(self):
        return f"<User {self.email}>"

class Lead(db.Model):
    """Table to store loan details for users and their refinancing lead data."""
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)  # User's phone number
    name = db.Column(db.String(100), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    original_loan_amount = db.Column(db.Float, nullable=True)
    original_loan_tenure = db.Column(db.Integer, nullable=True)
    current_repayment = db.Column(db.Float, nullable=True)
    remaining_tenure = db.Column(db.Integer, nullable=True)
    interest_rate = db.Column(db.Float, nullable=True)
    new_repayment = db.Column(db.Float, nullable=True)
    monthly_savings = db.Column(db.Float, nullable=True)
    yearly_savings = db.Column(db.Float, nullable=True)
    total_savings = db.Column(db.Float, nullable=True)
    years_saved = db.Column(db.Float, nullable=True)  # e.g., 1.3 years
    conversation_state = db.Column(db.String(50), nullable=False, default='START')  # Tracks chatbot flow state
    question_count = db.Column(db.Integer, nullable=True, default=0)  # To track user question count
    status = db.Column(db.String(50), nullable=False, default='New')  # Lead status (e.g., new, closed, etc.)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Lead {self.id} - {self.name}>"

class BankRate(db.Model):
    """Table to store interest rates from banks for use in calculations."""
    __tablename__ = 'bank_rates'
    id = db.Column(db.Integer, primary_key=True)
    bank_name = db.Column(db.String(100), nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)  # Annual interest rate in percentage
    min_amount = db.Column(db.Float, nullable=False)  # Minimum loan amount
    max_amount = db.Column(db.Float, nullable=False)  # Maximum loan amount
    tenure_options = db.Column(db.String(200), nullable=False)  # Comma-separated list of tenure options (years)

    def __repr__(self):
        return f"<BankRate {self.bank_name}>"

class ChatLog(db.Model):
    """Table to store chat logs to track user interaction with the chatbot."""
    __tablename__ = 'chat_logs'
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False)  # User's phone number
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
