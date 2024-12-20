import logging  # ✅ Import logging to fix logging error

# Setup logging (this can be customized as needed)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from sqlalchemy import func
from backend.models import BankRate  # ✅ Import bank_rates to fix the "BankRate not defined" error

def calculate_refinance_savings(original_loan_amount, original_loan_tenure, current_repayment):
    """
    Calculate potential refinance savings using the provided inputs.
    """
    # 🔥 Default result with default values to prevent KeyError
    result = {
        'monthly_savings': 0.0, 
        'yearly_savings': 0.0,  # ✅ Default value for yearly savings
        'lifetime_savings': 0.0, 
        'new_monthly_repayment': 0.0,
        'years_saved': 0, 
        'months_saved': 0,
        'new_interest_rate': 0.0,
        'bank_name': ''
    }

    try:
        # 1️⃣ **Input Validation**
        if not original_loan_amount or not original_loan_tenure or not current_repayment:
            logging.error("❌ Missing essential input data. Cannot proceed with calculation.")
            return result  # 🔥 Return default result with 0s

        # 2️⃣ **Query the Best Bank Rate**
        bank_rate = BankRate.query.filter(
            BankRate.min_amount <= original_loan_amount,
            BankRate.max_amount >= original_loan_amount
        ).order_by(BankRate.interest_rate).first()

        if bank_rate:
            result['new_interest_rate'] = bank_rate.interest_rate
            result['bank_name'] = bank_rate.bank_name
            logging.info(f"✅ Bank rate found: {bank_rate.interest_rate}% for bank: {bank_rate.bank_name}")
        else:
            logging.error(f"❌ No bank rate found for loan amount: {original_loan_amount}")
            return result  # 🔥 Return default result with 0s

        # 3️⃣ **Calculate New Monthly Repayment**
        new_tenure_years = original_loan_tenure
        monthly_interest_rate = result['new_interest_rate'] / 100 / 12
        total_payments = new_tenure_years * 12

        if monthly_interest_rate == 0:
            new_monthly_repayment = original_loan_amount / total_payments
        else:
            new_monthly_repayment = original_loan_amount * (
                monthly_interest_rate * (1 + monthly_interest_rate) ** total_payments
            ) / ((1 + monthly_interest_rate) ** total_payments - 1)

        result['new_monthly_repayment'] = round(new_monthly_repayment, 2)
        logging.info(f"✅ New monthly repayment: {result['new_monthly_repayment']}")

        # 4️⃣ **Calculate Savings**
        monthly_savings = current_repayment - result['new_monthly_repayment']
        
        # ✅ **Calculate Yearly Savings**
        yearly_savings = monthly_savings * 12  # ✅ Directly calculate yearly savings from monthly savings
        
        # ✅ **Calculate Lifetime Savings**
        existing_total_cost = current_repayment * original_loan_tenure * 12
        new_total_cost = result['new_monthly_repayment'] * original_loan_tenure * 12
        lifetime_savings = existing_total_cost - new_total_cost

        # ✅ **Store Savings in the Result**
        result['monthly_savings'] = round(monthly_savings, 2)
        result['yearly_savings'] = round(yearly_savings, 2)  # ✅ Save yearly savings
        result['lifetime_savings'] = round(lifetime_savings, 2)
        logging.info(f"✅ Savings calculated. Monthly: {result['monthly_savings']}, Yearly: {result['yearly_savings']}, Lifetime: {result['lifetime_savings']}")

        # 5️⃣ **Calculate Years and Months Saved**
        if lifetime_savings > 0 and current_repayment > 0:
            total_months_saved = lifetime_savings / current_repayment
            years_saved = int(total_months_saved // 12)
            months_saved = int(total_months_saved % 12)
        else:
            years_saved = 0
            months_saved = 0

        result['years_saved'] = years_saved
        result['months_saved'] = months_saved
        logging.info(f"✅ Years saved: {result['years_saved']}, Months saved: {result['months_saved']}")

        return result

    except Exception as e:
        logging.error(f"❌ General error in refinance calculation: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")  # Optional for debugging
        return result  # 🔥 Return default result with 0s
