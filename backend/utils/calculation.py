import math

def calculate_refinance_savings(original_loan_amount, original_tenure_years, current_monthly_repayment, new_interest_rate=None, new_tenure_years=None):
    """
    Calculate potential refinance savings.
    """
    try:
        # Calculate the existing total cost of the loan
        total_existing_cost = current_monthly_repayment * original_tenure_years * 12

        # If new interest rate or tenure is not provided, use some assumptions
        if not new_interest_rate:
            new_interest_rate = 3.5  # Assume a default interest rate if not provided
        if not new_tenure_years:
            new_tenure_years = original_tenure_years  # Default to original tenure

        # Calculate new monthly repayment
        monthly_interest_rate = new_interest_rate / 100 / 12
        total_payments = new_tenure_years * 12
        new_monthly_repayment = original_loan_amount * (monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments) / ((1 + monthly_interest_rate) ** total_payments - 1)

        # Calculate total cost of the new loan
        total_new_cost = new_monthly_repayment * total_payments

        # Calculate savings
        monthly_savings = current_monthly_repayment - new_monthly_repayment
        yearly_savings = monthly_savings * 12
        lifetime_savings = total_existing_cost - total_new_cost
        years_saved = (original_tenure_years * 12 - total_payments) / 12  # Calculate the difference in loan duration

        return {
            'new_monthly_repayment': round(new_monthly_repayment, 2),
            'monthly_savings': round(monthly_savings, 2),
            'yearly_savings': round(yearly_savings, 2),
            'lifetime_savings': round(lifetime_savings, 2),
            'years_saved': round(years_saved, 2)
        }
    except Exception as e:
        logging.error(f"Error in refinance calculation: {e}")
        return None
