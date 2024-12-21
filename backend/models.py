from datetime import datetime
from backend.extensions import db  # ✅ Import db first
import pytz  # 🟢 Import pytz
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text

# Malaysia timezone
MYT = pytz.timezone('Asia/Kuala_Lumpur')

class ChatflowTemp(db.Model):
    __tablename__ = 'chatflow_temp'

    id = Column(Integer, primary_key=True, autoincrement=True)
    phone_number = Column(String(20), nullable=False, unique=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)  # ✅ Correct ForeignKey reference to users
    current_step = Column(String(50), nullable=True)
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
    mode = Column(String(20), nullable=False, default='flow')  # ✅ Default value set
    created_at = Column(DateTime, default=lambda: datetime.now(MYT))  # Consistent MYT
    updated_at = Column(DateTime, default=lambda: datetime.now(MYT), onupdate=lambda: datetime.now(MYT))


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    wa_id = db.Column(db.String(20), unique=True, index=True, nullable=False)
    phone_number = db.Column(db.String(20), unique=True, index=True, nullable=False) 
    name = db.Column(db.String(50), nullable=True)  
    age = db.Column(db.Integer, nullable=True)  
    current_step = db.Column(db.String(50), nullable=False, default='get_name')  
    
    # Use lazy='dynamic' for ChatLog relationship
    chat_logs = db.relationship('ChatLog', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    chatflows = db.relationship('ChatflowTemp', backref='user', cascade="all, delete-orphan")  
    
    leads = db.relationship('Lead', backref='user', cascade="all, delete-orphan")  
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MYT))  
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(MYT), onupdate=lambda: datetime.now(MYT))

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

    # New columns for savings and other details
    new_repayment = db.Column(db.Float, nullable=True)
    monthly_savings = db.Column(db.Float, nullable=True)
    yearly_savings = db.Column(db.Float, nullable=True)
    total_savings = db.Column(db.Float, nullable=True)
    years_saved = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MYT))  
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(MYT), onupdate=lambda: datetime.now(MYT))


class ChatLog(db.Model):  # Capital L
    __tablename__ = 'chat_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  # ✅ User reference
    message = db.Column(Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MYT), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(MYT), onupdate=lambda: datetime.now(MYT), nullable=False)


class BankRate(db.Model):
    __tablename__ = 'bank_rates'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    bank_name = db.Column(db.String(100), nullable=False)
    min_amount = db.Column(db.Float, nullable=False)
    max_amount = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(MYT))  
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(MYT), onupdate=lambda: datetime.now(MYT))
