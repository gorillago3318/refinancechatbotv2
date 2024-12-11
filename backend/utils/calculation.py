import math
from backend.models import BankRate
from backend.extensions import db


def calculate_savings(original_loan_amount, original_tenure, current_repayment, interest_rate):
    """ 
    Calculate the potential savings for the user based on the provided details.
    
    Args:
        original_loan_amount (float): The original loan amount
        original_tenure (int): The original tenure in years
        current_repayment (float): The current monthly repayment
        interest_rate (float): The best available interest rate
    
    Returns:
        tuple: new_repayment, monthly_savings, yearly_savings, total_savings
    """
    monthly_interest_rate = interest_rate / 100 / 12
    number_of_payments = original_tenure * 12
    
    if monthly_interest_rate == 0:
        new_repayment = original_loan_amount / number_of_payments
    else:
        new_repayment = (
            original_loan_amount 
            * (monthly_interest_rate * (1 + monthly_interest_rate) ** number_of_payments) 
            / ((1 + monthly_interest_rate) ** number_of_payments - 1)
        )
    
    monthly_savings = max(current_repayment - new_repayment, 0)
    yearly_savings = monthly_savings * 12
    total_savings = monthly_savings * number_of_payments

    return round(new_repayment, 2), round(monthly_savings, 2), round(yearly_savings, 2), round(total_savings, 2)


def format_years_saved(total_months):
    """ 
    Format the total savings in months into years and months. 
    Args:
        total_months (float): Total months saved
    
    Returns:
        str: Formatted years and months string
    """
    years = int(total_months // 12)
    months = int(total_months % 12)
    return f"{years} year(s) {months} month(s)"


def extract_number(text):
    """
    Extracts the first number (integer or decimal) from a string.
    
    Args:
        text (str): The input text
    
    Returns:
        float: The extracted number
    """
    import re
    match = re.search(r'\d+(\.\d+)?', text.replace(',', '').replace('k', '000'))
    if match:
        return float(match.group())
    return None


def find_best_bank_rate(loan_amount):
    """
    Finds the best interest rate from the BankRate table for the provided loan amount.
    
    Args:
        loan_amount (float): The loan amount
    
    Returns:
        float: The best interest rate available for the loan amount
    """
    bank_rates = BankRate.query.filter(
        BankRate.min_amount <= loan_amount,
        BankRate.max_amount >= loan_amount
    ).order_by(BankRate.interest_rate.asc()).first()
    
    if bank_rates:
        return bank_rates.interest_rate
    return 5.0  # Default rate if no bank rate is found


def convert_to_number(value):
    """
    Converts a string with optional 'k' or ',' into a number.
    
    Args:
        value (str): The input string containing the number
    
    Returns:
        float: The converted number
    """
    if not value:
        return 0
    value = value.lower().replace('k', '000').replace(',', '')
    try:
        return float(value)
    except ValueError:
        return 0


def calculate_monthly_repayment(loan_amount, tenure, interest_rate):
    """
    Calculate the monthly repayment for a given loan amount, tenure, and interest rate.
    
    Args:
        loan_amount (float): The total loan amount
        tenure (int): Loan tenure in years
        interest_rate (float): Interest rate as a percentage
    
    Returns:
        float: The calculated monthly repayment
    """
    monthly_interest_rate = interest_rate / 100 / 12
    number_of_payments = tenure * 12
    
    if monthly_interest_rate == 0:
        return round(loan_amount / number_of_payments, 2)
    
    monthly_payment = (
        loan_amount 
        * (monthly_interest_rate * (1 + monthly_interest_rate) ** number_of_payments) 
        / ((1 + monthly_interest_rate) ** number_of_payments - 1)
    )
    return round(monthly_payment, 2)
