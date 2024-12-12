import logging
from ..models import Lead, BankRate
from ..extensions import db


def calculate_refinance_savings(
    phone_number=None, 
    original_loan_amount=None, 
    original_tenure_years=None, 
    current_monthly_repayment=None, 
    new_interest_rate=None, 
    new_tenure_years=None
):
    """
    Calculate potential refinance savings.
    If phone_number is provided, fetch loan info from the Lead table.
    Otherwise, it will use the provided arguments for ad-hoc calculations.
    """
    try:
        # 1️⃣ Get data from Lead if phone_number is provided
        lead = None
        if phone_number:
            lead = Lead.query.filter_by(phone_number=phone_number).first()
        
        # 2️⃣ Use Lead data if available, otherwise use provided arguments
        if lead:
            original_loan_amount = original_loan_amount or lead.original_loan_amount
            original_tenure_years = original_tenure_years or lead.original_loan_tenure
            current_monthly_repayment = current_monthly_repayment or lead.current_repayment
        
        # 3️⃣ Validate required inputs
        if not original_loan_amount or not original_tenure_years or not current_monthly_repayment:
            logging.error("❌ Insufficient data to calculate savings.")
            return {"error": "Insufficient data to calculate savings."}
        
        # 4️⃣ Query BankRate for best rate if new_interest_rate is not provided
        if not new_interest_rate:
            bank_rate = BankRate.query.filter(
                BankRate.min_amount <= original_loan_amount,
                BankRate.max_amount >= original_loan_amount
            ).order_by(BankRate.interest_rate).first()
            
            if not bank_rate:
                logging.error(f"❌ No bank rate found for loan amount: {original_loan_amount}")
                return {"error": "No bank rate found for this loan amount."}
            
            new_interest_rate = bank_rate.interest_rate
        
        if not new_tenure_years:
            new_tenure_years = original_tenure_years  # Assume new tenure is same as original if not provided

        # 5️⃣ Calculate new monthly repayment using amortization formula
        monthly_interest_rate = new_interest_rate / 100 / 12  # Convert APR to monthly rate
        total_payments = new_tenure_years * 12  # Total months of the loan
        try:
            new_monthly_repayment = original_loan_amount * (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments) / ((1 + monthly_interest_rate) ** total_payments - 1)
        except ZeroDivisionError as e:
            logging.error(f"❌ Error in monthly payment calculation: {e}")
            return {"error": "Error in monthly payment calculation."}

        # 6️⃣ Calculate the total cost of existing and new loans
        total_existing_cost = current_monthly_repayment * original_tenure_years * 12  # Current loan total cost
        total_new_cost = new_monthly_repayment * total_payments  # New loan total cost

        # 7️⃣ Calculate savings
        monthly_savings = current_monthly_repayment - new_monthly_repayment  # Monthly difference
        yearly_savings = monthly_savings * 12  # Annual savings
        lifetime_savings = total_existing_cost - total_new_cost  # Total savings over the loan term
        total_months_saved = lifetime_savings / current_monthly_repayment  # Total months equivalent of savings
        years_saved = int(total_months_saved // 12)  # Convert months to years
        months_saved = int(total_months_saved % 12)  # Remainder in months

        # 8️⃣ Update Lead data
        if lead:
            lead.new_repayment = new_monthly_repayment
            lead.monthly_savings = monthly_savings
            lead.yearly_savings = yearly_savings
            lead.total_savings = lifetime_savings
            lead.years_saved = years_saved + (months_saved / 12)  # Save precise value as years
            db.session.commit()

        # 9️⃣ Return the summary of savings
        return {
            'new_monthly_repayment': round(new_monthly_repayment, 2),
            'monthly_savings': round(monthly_savings, 2),
            'yearly_savings': round(yearly_savings, 2),
            'lifetime_savings': round(lifetime_savings, 2),
            'years_saved': f"{years_saved} year(s) {months_saved} month(s)"
        }

    except Exception as e:
        logging.error(f"❌ Error in refinance calculation: {e}")
        return {"error": "Error in refinance calculation."}
