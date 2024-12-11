from backend.extensions import db  # Ensure this import points to the correct location
from datetime import datetime

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    wa_id = db.Column(db.String(20), unique=True, nullable=False)  # WhatsApp ID for users
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Should store hashed passwords
    role = db.Column(db.String(50), nullable=False, default='user')  # Roles: user, admin, agent, referrer
    leads = db.relationship('Lead', backref='referrer', lazy=True)

    def __repr__(self):
        return f"<User {self.email}>"


class Lead(db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    referrer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
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
    years_saved = db.Column(db.Float, nullable=True)
    conversation_state = db.Column(db.String(50), nullable=False, default='START')
    question_count = db.Column(db.Integer, nullable=True, default=0)
    status = db.Column(db.String(50), nullable=False, default='New')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Lead {self.id} - {self.name}>"


class BankRate(db.Model):
    __tablename__ = 'bank_rates'

    id = db.Column(db.Integer, primary_key=True)
    bank_name = db.Column(db.String(100), nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)  # Annual interest rate in percentage
    min_amount = db.Column(db.Float, nullable=False)
    max_amount = db.Column(db.Float, nullable=False)
    tenure_options = db.Column(db.String(200), nullable=False)  # Comma-separated list of tenure options (years)

    def __repr__(self):
        return f"<BankRate {self.bank_name}>"
