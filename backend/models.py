from datetime import datetime
from backend.extensions import db  # ✅ Import db first
from sqlalchemy import Column, Integer, String, DateTime, Float

class ChatflowTemp(db.Model):
    __tablename__ = 'chatflow_temp'

    id = Column(Integer, primary_key=True)
    phone_number = Column(String(20), nullable=False, unique=True)
    current_step = Column(String(50), nullable=True)  # <--- ADD THIS COLUMN
    language_code = Column(String(10), nullable=True)
    name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    original_loan_amount = Column(Float, nullable=True)
    original_loan_tenure = Column(Integer, nullable=True)
    current_repayment = Column(Float, nullable=True)
    interest_rate = Column(Float, nullable=True)
    remaining_tenure = Column(Integer, nullable=True)
    last_question_time = Column(DateTime, nullable=True)
    gpt_query_count = Column(Integer, nullable=True)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    wa_id = db.Column(db.String(20), unique=True, index=True, nullable=False)
    phone_number = db.Column(db.String(20), unique=True, index=True, nullable=False) 
    name = db.Column(db.String(50), nullable=True)  
    age = db.Column(db.Integer, nullable=True)  
    current_step = db.Column(db.String(50), nullable=False, default='get_name')  
    leads = db.relationship('Lead', backref='user', cascade="all, delete-orphan")  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  

class Lead(db.Model):
    __tablename__ = 'leads'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True, nullable=False)  
    phone_number = db.Column(db.String(20), nullable=False)  
    name = db.Column(db.String(50), nullable=False)  
    property_reference = db.Column(db.String(50), nullable=True, unique=True)  
    original_loan_amount = db.Column(db.Float, nullable=False)  
    original_loan_tenure = db.Column(db.Integer, nullable=False)  
    current_repayment = db.Column(db.Float, nullable=False)

    # Add the new column here:
    new_repayment = db.Column(db.Float, nullable=True)  # Or False if it's always needed

    created_at = db.Column(db.DateTime, default=datetime.utcnow)  
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChatLog(db.Model):
    __tablename__ = 'chat_logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True, nullable=False)  
    message = db.Column(db.Text, nullable=False)  
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  

class BankRate(db.Model):
    __tablename__ = 'bank_rates'  # This matches the table name you see in psql.

    id = db.Column(db.Integer, primary_key=True)
    bank_name = db.Column(db.String(100), nullable=False)
    min_amount = db.Column(db.Float, nullable=False)
    max_amount = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)
