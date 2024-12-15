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
            # 1⃣ Validate required inputs
            if not original_loan_amount or not original_tenure_years or not current_monthly_repayment:
                logging.error("\u274c Missing essential input data. Cannot proceed with calculation.")
                return {"error": "Missing essential loan information."}

            # 2⃣ Calculate the interest rate of the existing loan
            total_payments = original_tenure_years * 12  # Total number of payments (in months)
            try:
                monthly_interest_rate = compute_existing_loan_interest_rate(
                    original_loan_amount, 
                    current_monthly_repayment, 
                    total_payments
                )
                existing_interest_rate = round(monthly_interest_rate * 12 * 100, 2)  # Convert to APR
            except Exception as e:
                logging.error(f"\u274c Error calculating existing interest rate: {e}")
                return {"error": "Error calculating existing loan interest rate."}

            # 3⃣ Query BankRate for best rate for new refinance
            try:
                bank_rate = BankRate.query.filter(
                    BankRate.min_amount <= original_loan_amount,
                    BankRate.max_amount >= original_loan_amount
                ).order_by(BankRate.interest_rate).first()
            except Exception as e:
                logging.error(f"\u274c Error querying BankRate: {e}")
                return {"error": "Error querying BankRate."}

            if not bank_rate:
                logging.error(f"\u274c No bank rate found for loan amount: {original_loan_amount}")
                return {"error": "No bank rate found for this loan amount."}
            
            new_interest_rate = bank_rate.interest_rate
            
            if not new_tenure_years:
                new_tenure_years = original_tenure_years  # Assume new tenure is same as original if not provided

            # 4⃣ Calculate new monthly repayment using amortization formula
            monthly_interest_rate = new_interest_rate / 100 / 12  # Convert APR to monthly rate
            total_payments_new = new_tenure_years * 12  # Total payments for new loan
            
            try:
                if monthly_interest_rate == 0:
                    new_monthly_repayment = original_loan_amount / total_payments_new
                else:
                    new_monthly_repayment = original_loan_amount * (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments_new) / ((1 + monthly_interest_rate) ** total_payments_new - 1)
            except ZeroDivisionError as e:
                logging.error(f"\u274c ZeroDivisionError in monthly payment calculation: {e}")
                return {"error": "Error in monthly payment calculation due to zero division."}

            # 5⃣ Calculate the total cost of existing and new loans
            total_existing_cost = current_monthly_repayment * total_payments  # Current loan total cost
            total_new_cost = new_monthly_repayment * total_payments_new  # New loan total cost

            # 6⃣ Calculate savings
            monthly_savings = current_monthly_repayment - new_monthly_repayment  # Monthly difference
            yearly_savings = monthly_savings * 12  # Annual savings
            lifetime_savings = total_existing_cost - total_new_cost  # Total savings over the loan term
            total_months_saved = lifetime_savings / current_monthly_repayment if current_monthly_repayment > 0 else 0  # Total months saved
            years_saved = int(total_months_saved // 12)  # Convert to years
            months_saved = int(total_months_saved % 12)  # Get remaining months

            # 7⃣ Return the summary of savings
            return {
                'new_monthly_repayment': round(new_monthly_repayment, 2),
                'monthly_savings': round(monthly_savings, 2),
                'yearly_savings': round(yearly_savings, 2),
                'lifetime_savings': round(lifetime_savings, 2),
                'years_saved': f"{years_saved} year(s) {months_saved} month(s)",
                'existing_interest_rate': existing_interest_rate
            }

    except Exception as e:
        logging.exception(f"\u274c General error in refinance calculation: {e}")
        return {"error": "General error in refinance calculation."}


def compute_existing_loan_interest_rate(original_loan_amount, current_monthly_repayment, total_payments):
    """
    Calculate the effective interest rate of an existing loan using the amortization formula.
    """
    import sympy as sp
    i = sp.symbols('i')  # Interest rate per month
    equation = sp.Eq(
        current_monthly_repayment, 
        (original_loan_amount * (i * (1 + i)**total_payments)) / ((1 + i)**total_payments - 1)
    )
    
    try:
        # Solve for the interest rate
        solutions = sp.solve(equation, i)
        monthly_interest_rate = [sol.evalf() for sol in solutions if sol.is_real and sol > 0]
        if not monthly_interest_rate:
            raise ValueError(f"No real positive solution for interest rate found.")
        return float(monthly_interest_rate[0])
    except Exception as e:
        logging.error(f"\u274c Error solving interest rate equation: {e}")
        raise e
