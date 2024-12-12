import math
from ..models import Lead, BankRate
from ..extensions import db

def calculate_refinance_savings(phone_number=None, original_loan_amount=None, original_tenure_years=None, current_monthly_repayment=None, new_interest_rate=None, new_tenure_years=None):
    """
    Calculate potential refinance savings.
    If phone_number is provided, fetch loan info from the Lead table.
    Otherwise, it will use the provided arguments for ad-hoc calculations.
    """
    try:
        # Get data from Lead if phone_number is provided
        lead = None
        if phone_number:
            lead = Lead.query.filter_by(phone_number=phone_number).first()
        
        # Use Lead data if available
        if lead:
            original_loan_amount = lead.original_loan_amount
            original_tenure_years = lead.original_loan_tenure
            current_monthly_repayment = lead.current_repayment
        
        if not original_loan_amount or not original_tenure_years or not current_monthly_repayment:
            return {"error": "Insufficient data to calculate savings."}

        # If new interest rate or tenure is not provided, query the BankRate
        if not new_interest_rate:
            bank_rate = BankRate.query.filter(
                BankRate.min_amount <= original_loan_amount,
                BankRate.max_amount >= original_loan_amount
            ).order_by(BankRate.interest_rate).first()
            
            if not bank_rate:
                return {"error": "No bank rate found for this loan amount."}
            
            new_interest_rate = bank_rate.interest_rate
        
        if not new_tenure_years:
            new_tenure_years = original_tenure_years

        # Calculate new monthly repayment
        monthly_interest_rate = new_interest_rate / 100 / 12
        total_payments = new_tenure_years * 12
        new_monthly_repayment = original_loan_amount * (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments) / ((1 + monthly_interest_rate) ** total_payments - 1)

        # Calculate savings
        total_existing_cost = current_monthly_repayment * original_tenure_years * 12
        total_new_cost = new_monthly_repayment * total_payments
        monthly_savings = current_monthly_repayment - new_monthly_repayment
        yearly_savings = monthly_savings * 12
        lifetime_savings = total_existing_cost - total_new_cost
        years_saved = (original_tenure_years * 12 - total_payments) / 12

        # Update Lead data
        if lead:
            lead.new_repayment = new_monthly_repayment
            lead.monthly_savings = monthly_savings
            lead.yearly_savings = yearly_savings
            lead.total_savings = lifetime_savings
            lead.years_saved = round(years_saved, 2)
            db.session.commit()

        # Return the savings summary
        return {
            'new_monthly_repayment': round(new_monthly_repayment, 2),
            'monthly_savings': round(monthly_savings, 2),
            'yearly_savings': round(yearly_savings, 2),
            'lifetime_savings': round(lifetime_savings, 2),
            'years_saved': round(years_saved, 2)
        }
    except Exception as e:
        logging.error(f"Error in refinance calculation: {e}")
        return {"error": "Error in refinance calculation"}
