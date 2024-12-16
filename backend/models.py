import datetime
from backend.extensions import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    wa_id = db.Column(db.String(20), unique=True, index=True, nullable=False)  # WhatsApp ID (e.g., phone number)
    name = db.Column(db.String(50), nullable=True)  # User's name
    age = db.Column(db.Integer, nullable=True)  # User's age
    current_step = db.Column(db.String(50), nullable=False, default='get_name')  # The current step of the user's process
    
    # Relationship with Lead - One User can have multiple Leads
    leads = db.relationship('Lead', backref='user', cascade="all, delete-orphan")
    
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)  # Timestamp for user creation
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)  # Timestamp for user updates

    def __repr__(self):
        return f"<User {self.id} - {self.name} ({self.wa_id})>"

class Lead(db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True, nullable=False)  # Link to the User table
    property_reference = db.Column(db.String(50), nullable=True, unique=True)  # Unique identifier for the property (can be random)
    original_loan_amount = db.Column(db.Float, nullable=False)  # Original loan amount
    original_loan_tenure = db.Column(db.Integer, nullable=False)  # Tenure in years
    current_repayment = db.Column(db.Float, nullable=False)  # Current monthly repayment
    new_repayment = db.Column(db.Float, default=0.0, nullable=True)  # New monthly repayment
    monthly_savings = db.Column(db.Float, default=0.0, nullable=True)  # Savings per month
    yearly_savings = db.Column(db.Float, default=0.0, nullable=True)  # Savings per year
    total_savings = db.Column(db.Float, default=0.0, nullable=True)  # Total lifetime savings
    years_saved = db.Column(db.Float, default=0.0, nullable=True)  # Total number of years saved (in decimal)
    interest_rate = db.Column(db.Float, nullable=True)  # Interest rate
    remaining_tenure = db.Column(db.Integer, nullable=True)  # Remaining tenure of the loan

    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)  # Timestamp for lead creation
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)  # Timestamp for updates

    def __repr__(self):
        return f"<Lead {self.id} - {self.property_reference} (User ID: {self.user_id})>"

class ChatLog(db.Model):
    __tablename__ = 'chat_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True, nullable=False)  # Link to the User table
    message = db.Column(db.Text, nullable=False)  # The message content
    response = db.Column(db.Text, nullable=True)  # The bot's response to the message
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)  # Timestamp for log entry
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)  # Timestamp for updates

    def __repr__(self):
        return f"<ChatLog {self.id} - User ID: {self.user_id}>"

class BankRate(db.Model):
    __tablename__ = 'bank_rates'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    min_amount = db.Column(db.Float, nullable=False, index=True)  # Minimum amount for the rate
    max_amount = db.Column(db.Float, nullable=False, index=True)  # Maximum amount for the rate
    interest_rate = db.Column(db.Float, nullable=False)  # The rate for the loan amounts within min/max
    bank_name = db.Column(db.String(255), nullable=True)  # Added bank name

    def __repr__(self):
        return f"<BankRate {self.id} - {self.min_amount} to {self.max_amount} @ {self.interest_rate}% from {self.bank_name}>"
