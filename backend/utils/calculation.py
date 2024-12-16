import logging
from flask import current_app
from backend.models import BankRate
from backend.extensions import db

def calculate_refinance_savings(
    original_loan_amount=None, 
    original_loan_tenure=None, 
    current_monthly_repayment=None
):
    """
    Calculate potential refinance savings.
    Uses SQL to fetch the best available interest rate from the BankRate table 
    for the user's loan amount and then calculates the potential savings.
    
    Args:
        original_loan_amount (float): The original loan amount in RM.
        original_loan_tenure (int): The total tenure for the loan (in years).
        current_monthly_repayment (float): The user's current monthly repayment amount.

    Returns:
        dict: Returns a dictionary with new repayment details and savings info.
    """
    try:
        with current_app.app_context():
            result = {}  # Store the result data to return at the end

            # 1⃣ **Input Validation**
            if original_loan_amount is None or original_loan_tenure is None or current_monthly_repayment is None:
                logging.error("❌ Missing essential input data. Cannot proceed with calculation.")
                return {"error": "Missing essential loan information."}

            logging.info(f"✅ Inputs received. Loan: {original_loan_amount}, Tenure: {original_loan_tenure} years, Current Repayment: {current_monthly_repayment}")

            # 2⃣ **Query the Best Bank Rate**
            try:
                bank_rate = BankRate.query.filter(
                    BankRate.min_amount <= original_loan_amount,
                    BankRate.max_amount >= original_loan_amount
                ).order_by(BankRate.interest_rate).first()

                if bank_rate:
                    result['new_interest_rate'] = bank_rate.interest_rate
                    result['bank_name'] = bank_rate.bank_name  # Include bank name
                    logging.info(f"✅ Bank rate found: {bank_rate.interest_rate}% for bank: {bank_rate.bank_name}")
                else:
                    logging.error(f"❌ No bank rate found for loan amount: {original_loan_amount}")
                    return {"error": "No bank rate available for this loan amount."}
            except Exception as e:
                logging.error(f"❌ Error querying BankRate: {e}")
                return {"error": "Error querying BankRate."}

            # 3⃣ **Calculate New Monthly Repayment**
            try:
                # Set the new tenure to be the same as the original tenure
                new_tenure_years = original_loan_tenure  
                monthly_interest_rate = result['new_interest_rate'] / 100 / 12  # Convert APR to monthly rate
                total_payments = new_tenure_years * 12  # Total number of payments for new loan

                if monthly_interest_rate == 0:
                    new_monthly_repayment = original_loan_amount / total_payments
                else:
                    # Amortization formula for fixed monthly payments
                    new_monthly_repayment = original_loan_amount * (
                        monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments
                    ) / ((1 + monthly_interest_rate) ** total_payments - 1)
                
                result['new_monthly_repayment'] = round(new_monthly_repayment, 2)
                logging.info(f"✅ New monthly repayment: {result['new_monthly_repayment']}")
            except Exception as e:
                logging.error(f"❌ Error calculating new monthly repayment: {e}")
                return {"error": "Error in monthly payment calculation."}

            # 4⃣ **Calculate Savings**
            try:
                # Calculate potential savings
                monthly_savings = current_monthly_repayment - result['new_monthly_repayment']
                yearly_savings = monthly_savings * 12
                existing_total_cost = current_monthly_repayment * original_loan_tenure * 12
                new_total_cost = result['new_monthly_repayment'] * original_loan_tenure * 12
                lifetime_savings = existing_total_cost - new_total_cost

                # Calculate years and months saved based on lifetime savings
                if lifetime_savings > 0 and current_monthly_repayment > 0:
                    total_months_saved = lifetime_savings / current_monthly_repayment
                    years_saved = int(total_months_saved // 12)  # Number of full years saved
                    months_saved = int(total_months_saved % 12)  # Remaining months after accounting for years
                else:
                    years_saved = 0
                    months_saved = 0

                result['monthly_savings'] = round(monthly_savings, 2)
                result['yearly_savings'] = round(yearly_savings, 2)
                result['lifetime_savings'] = round(lifetime_savings, 2)
                result['years_saved'] = years_saved
                result['months_saved'] = months_saved

                logging.info(f"✅ Savings calculated. Monthly: {result['monthly_savings']}, Yearly: {result['yearly_savings']}, Lifetime: {result['lifetime_savings']}, Years Saved: {years_saved}, Months Saved: {months_saved}")
            except Exception as e:
                logging.error(f"❌ Error calculating savings: {e}")
                return {"error": "Error calculating savings."}

            # 5⃣ **Return Results**
            return result

    except Exception as e:
        logging.error(f"❌ General error in refinance calculation: {e}")
        return {"error": "General error in refinance calculation."}
