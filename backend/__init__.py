# backend/utils/calculation.py

import math

def calculate_savings(loan_amount, loan_tenure, interest_rate):
    """
    Performs calculations to estimate savings from refinancing.

    Parameters:
        loan_amount (float): Original loan amount.
        loan_tenure (float): Original loan tenure in years.
        interest_rate (float): Current interest rate in percentage.

    Returns:
        dict: Contains calculated savings and new repayment details.
    """
    P = loan_amount
    r = interest_rate / 100 / 12  # Monthly interest rate
    n = loan_tenure * 12  # Total number of monthly payments

    # Current Monthly Repayment using the formula: M = P * r * (1 + r)^n / ((1 + r)^n - 1)
    try:
        current_monthly_repayment = P * r * math.pow(1 + r, n) / (math.pow(1 + r, n) - 1)
    except ZeroDivisionError:
        current_monthly_repayment = P / n

    # Define new interest rate after refinancing (e.g., 1% lower)
    new_interest_rate = max(interest_rate - 1.0, 0.5)  # Ensures a minimum rate

    new_r = new_interest_rate / 100 / 12
    new_monthly_repayment = P * new_r * math.pow(1 + new_r, n) / (math.pow(1 + new_r, n) - 1)

    # Calculate savings
    monthly_saving = current_monthly_repayment - new_monthly_repayment
    annual_saving = monthly_saving * 12
    total_saving = monthly_saving * n

    # Estimate years saved by refinancing
    if monthly_saving > 0:
        years_saved = total_saving / (annual_saving)  # Simplistic calculation
    else:
        years_saved = 0

    # Round values for presentation
    current_monthly_repayment = round(current_monthly_repayment, 2)
    new_monthly_repayment = round(new_monthly_repayment, 2)
    monthly_saving = round(monthly_saving, 2)
    annual_saving = round(annual_saving, 2)
    total_saving = round(total_saving, 2)
    years_saved = round(years_saved, 1)

    return {
        'current_monthly_repayment': current_monthly_repayment,
        'new_interest_rate': new_interest_rate,
        'new_monthly_repayment': new_monthly_repayment,
        'monthly_saving': monthly_saving,
        'annual_saving': annual_saving,
        'total_saving': total_saving,
        'years_saved': years_saved
    }
