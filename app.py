from flask import Flask, render_template, request, jsonify, session, url_for
import requests
import secrets
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# ✅ Vercel production settings
if os.environ.get('VERCEL_ENV') == 'production':
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )

# Static folder configuration
app.static_folder = 'static'
app.static_url_path = '/static'

# FamPay Configuration
FAMPAY_CONFIG = {
    'api_key': 'FAM_371735AC5A8C95B29EDB8EA7E7CD51DA57863D3C',
    'base_url': 'https://fampaygateway.site/api',
    'checkout_url': 'https://fampaygateway.site/checkout.php'
}

def create_order(amount):
    url = f"{FAMPAY_CONFIG['base_url']}/create_order.php"
    params = {'amount': amount, 'api_key': FAMPAY_CONFIG['api_key']}
    try:
        response = requests.get(url, params=params, timeout=30)
        return response.json()
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def verify_payment(order_id):
    url = f"{FAMPAY_CONFIG['base_url']}/verify.php"
    params = {'order_id': order_id, 'api_key': FAMPAY_CONFIG['api_key']}
    try:
        response = requests.get(url, params=params, timeout=30)
        return response.json()
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def generate_checkout_link(order_id):
    return f"{FAMPAY_CONFIG['checkout_url']}?order_id={order_id}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create-payment', methods=['POST'])
def create_payment_route():
    try:
        amount = request.form.get('amount')
        if not amount:
            return render_template('error.html', error='Amount is required')
        
        amount = float(amount)
        if amount <= 0:
            return render_template('error.html', error='Amount must be greater than 0')
        
        response = create_order(amount)
        
        if response.get('status') != 'success':
            return render_template('error.html', 
                                 error=response.get('message', 'Order creation failed'))
        
        data = response.get('data', {})
        order_id = data.get('order_id')
        
        session['order_id'] = order_id
        session['amount'] = amount
        
        checkout_link = generate_checkout_link(order_id)
        
        return render_template('payment.html',
                             order_id=order_id,
                             amount=amount,
                             upi_id=data.get('upi_id', 'N/A'),
                             qr_url=data.get('qr_url'),
                             expires_at=data.get('expires_at'),
                             checkout_link=checkout_link)
    
    except Exception as e:
        return render_template('error.html', error=str(e))

@app.route('/verify-payment')
def payment_verify():
    order_id = request.args.get('order_id') or session.get('order_id')
    if not order_id:
        return render_template('error.html', error='Order ID required')
    
    response = verify_payment(order_id)
    
    if response.get('status') == 'success':
        data = response.get('data', {})
        return render_template('success.html',
                             order_id=order_id,
                             amount=session.get('amount', 0),
                             utr=data.get('utr'),
                             payment_time=data.get('payment_time'))
    else:
        return render_template('payment_status.html',
                             order_id=order_id,
                             status='pending',
                             message='Payment is still pending. Please complete the payment.')

@app.route('/auto-verify', methods=['POST'])
def auto_verify():
    order_id = request.json.get('order_id') or session.get('order_id')
    if not order_id:
        return jsonify({'error': 'Order ID required'}), 400
    
    response = verify_payment(order_id)
    if response.get('status') == 'success':
        return jsonify({'status': 'verified', 'payment': response.get('data', {})})
    else:
        return jsonify({'status': 'pending', 'message': 'Payment not completed'})

# For Vercel serverless
app.debug = False

# This is required for Vercel
if __name__ == '__main__':
    app.run()
