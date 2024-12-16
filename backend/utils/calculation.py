import logging
from flask import current_app
from backend.models import Lead, BankRate, User
from backend.extensions import db

def calculate_refinance_savings(
    phone_number=None, 
    original_loan_amount=None, 
    original_tenure_years=None, 
    current_monthly_repayment=None, 
    new_tenure_years=None
):
    """
    Calculate potential refinance savings.
    If phone_number is provided, fetch loan info from the Lead table.
    Otherwise, it will use the provided arguments for ad-hoc calculations.
    """
    try:
        with current_app.app_context():
            # Store the result data to return at the end
            result = {}

            # 1⃣ Validate required inputs
            if original_loan_amount is None or original_tenure_years is None or current_monthly_repayment is None:
                logging.error("❌ Missing essential input data. Cannot proceed with calculation.")
                return {"error": "Missing essential loan information."}

            logging.info(f"✅ Essential input received. Original Loan: {original_loan_amount}, Tenure: {original_tenure_years} years, Current Monthly Repayment: {current_monthly_repayment}")

            # 2⃣ Query BankRate for best rate for new refinance
            try:
                bank_rate = BankRate.query.filter(
                    BankRate.min_amount <= original_loan_amount,
                    BankRate.max_amount >= original_loan_amount
                ).order_by(BankRate.interest_rate).first()

                if not bank_rate:
                    raise ValueError(f"No bank rate found for loan amount: {original_loan_amount}")
                
                new_interest_rate = bank_rate.interest_rate
                result['new_interest_rate'] = new_interest_rate
                logging.info(f"✅ Bank rate found: {new_interest_rate}% for loan amount: {original_loan_amount}")
            except Exception as e:
                logging.error(f"❌ Error querying BankRate: {e}")
                return {"error": "Error querying BankRate."}

            # 3⃣ Calculate new monthly repayment using amortization formula
            try:
                if not new_tenure_years:
                    new_tenure_years = original_tenure_years  # Assume new tenure is same as original if not provided

                monthly_interest_rate = new_interest_rate / 100 / 12  # Convert APR to monthly rate
                total_payments_new = new_tenure_years * 12  # Total payments for new loan
                
                if monthly_interest_rate == 0:
                    new_monthly_repayment = original_loan_amount / total_payments_new
                else:
                    new_monthly_repayment = original_loan_amount * (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments_new) / ((1 + monthly_interest_rate) ** total_payments_new - 1)
                
                result['new_monthly_repayment'] = round(new_monthly_repayment, 2)
                logging.info(f"✅ New monthly repayment: {result['new_monthly_repayment']}")
            except Exception as e:
                logging.error(f"❌ Error calculating new monthly repayment: {e}")
                return {"error": "Error in monthly payment calculation."}

            # 4⃣ Calculate savings
            try:
                monthly_savings = current_monthly_repayment - new_monthly_repayment  # Monthly difference
                yearly_savings = monthly_savings * 12  # Annual savings
                total_existing_cost = current_monthly_repayment * original_tenure_years * 12
                total_new_cost = new_monthly_repayment * new_tenure_years * 12
                lifetime_savings = total_existing_cost - total_new_cost  # Total savings over the loan term

                result['monthly_savings'] = round(monthly_savings, 2)
                result['yearly_savings'] = round(yearly_savings, 2)
                result['lifetime_savings'] = round(lifetime_savings, 2)
                logging.info(f"✅ Monthly savings: {result['monthly_savings']}, Yearly savings: {result['yearly_savings']}, Lifetime savings: {result['lifetime_savings']}")
            except Exception as e:
                logging.error(f"❌ Error calculating savings: {e}")
                return {"error": "Error calculating savings."}

            # 5⃣ Return all the data we collected
            return result

    except Exception as e:
        logging.exception(f"❌ General error in refinance calculation: {e}")
        return {"error": "General error in refinance calculation."}
