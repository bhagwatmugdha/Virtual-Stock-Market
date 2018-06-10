from myapp import app, mysql
from flask import render_template, flash, request, redirect, url_for, session, logging
from passlib.hash import sha256_crypt
from functools import wraps
from forms import RegisterForm

# Index
@app.route('/')
def index():
	return  render_template('home.html')

# # About
# @app.route('/about')
# def about():
# 	return  render_template('about.html')

# Register
@app.route('/register', methods=['GET', 'POST'])
def register():
	form = RegisterForm(request.form)
	if request.method == 'POST' and form.validate():
		name = form.name.data
		lastname = form.lastname.data
		email = form.email.data
		username = form.username.data
		password = sha256_crypt.encrypt(str(form.password.data))

		# Create cursor, Execute query, Commit to DB
		cur = mysql.connection.cursor()

		cur.execute("INSERT INTO users(name , lastname, email, username, password) VALUES(%s, %s, %s, %s, %s)", (name, lastname, email, username, password))

		mysql.connection.commit()

		cur.close()

		flash('You are now registered and can log in', 'success')

		return redirect(url_for('login'))
	return render_template('register.html', form=form)

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'POST':
		# Get Form Fields (not using WTForms)
		username = request.form['username']
		password_candidate = request.form['password']

		# Create cursor
		cur = mysql.connection.cursor()

		# Get user by username
		result = cur.execute("SELECT * FROM users WHERE username = %s", [username])
		if result > 0:
			# Get stored hash
			data = cur.fetchone()
			password = data['password']

			# Compare passwords
			if sha256_crypt.verify(password_candidate, password):
				# Passed
				session['logged_in'] = True
				session['username'] = username
				session['id'] = data['id']
				session['cash'] = data['cash']

				flash('You are now logged in', 'success')
				return redirect(url_for('stocks'))
			else:
				error = 'Invlaid login'
				return render_template('login.html', error=error)
			# Close connection
			cur.close()
		else:
			error = 'Entered Userame not found'
			return render_template('login.html', error=error)
	return render_template('login.html')

# Check if user logged in
def is_logged_in(f):
	@wraps(f)
	def wrap(*args, **kwargs):
		if 'logged_in' in session:
			return f(*args, **kwargs)
		else:
			flash('Unauthorized, Please login', 'danger')
			return redirect(url_for('login'))
	return wrap

# Logout
@app.route('/logout')
@is_logged_in
def logout():
	session.clear()
	flash('You are now logged out', 'success')
	return redirect(url_for('login'))


# All Stocks
@app.route('/stocks')
def stocks():
	# Create cursor
	cur = mysql.connection.cursor()

	# Get all stocks
	result = cur.execute("SELECT * FROM stocks ORDER BY company")

	stocks = cur.fetchall()

	if result > 0:
		return render_template('stocks.html', stocks=stocks)
	else:
		msg = 'No Stocks Found'
		return render_template('stocks.html', msg=msg)
	# Close connection
	cur.close()


# My Stocks
@app.route('/myStocks')
@is_logged_in
def myStocks():
	# Create cursor
	cur = mysql.connection.cursor()

	# Get my stocks
	stock_result = cur.execute("SELECT transactions.ticker, SUM(volume) as myvolume, price as current_price FROM transactions LEFT JOIN stocks ON transactions.ticker=stocks.ticker WHERE id=%s GROUP BY ticker HAVING myvolume>0 ORDER BY ticker", (session['id'],))

	mystocks = cur.fetchall()

	# Get my transactions
	trans_result = cur.execute("SELECT * FROM transactions WHERE id=%s ORDER BY trans_date DESC", (session['id'],))

	mytransactions = cur.fetchall()


	if stock_result > 0 and trans_result > 0:
		return render_template('myStocks.html', mystocks=mystocks, mytransactions=mytransactions)
	elif trans_result > 0:
		msg = 'No Stocks Found'
		return render_template('myStocks.html', mytransactions=mytransactions, msg=msg)
	else:
		msg = 'No Stocks or Transactions found'
		return render_template('myStocks.html', msg=msg)
	# Close connection
	cur.close()


# Buy Stock
@app.route('/buy_stock/<string:ticker>/<int:price>/<int:avail_volume>', methods=['POST'])
@is_logged_in
def buy_stock(ticker, price, avail_volume):
	volume = int(request.form['volume'])
	bill = volume*price

	if(bill<=session['cash']):
		if(volume<=avail_volume):
			# Create cursor
			cur = mysql.connection.cursor()

			# Update user cash
			cur.execute("UPDATE users SET cash=cash-%s WHERE username=%s", (bill, session['username']))

			session['cash'] = session['cash']-bill

			# Update stock volume
			cur.execute("UPDATE stocks SET avail_volume=avail_volume-%s WHERE ticker=%s", (volume, ticker))

			# Add transaction log
			cur.execute("INSERT INTO transactions(ticker, volume, type, current_price, id) VALUES(%s, %s, %s, %s, %s)", (ticker, volume, 'Buy', price, session['id']))

			# Commit to DB
			mysql.connection.commit()

			# Close connection
			cur.close()

			flash(str(volume)+' '+ticker+' stocks Bought!', 'success')
		else:
			flash('Sorry, '+str(volume)+' '+ticker+' stocks not available!', 'danger')

	else:
		flash('Sorry, you do not have enough funds!', 'danger')

	return redirect(url_for('stocks'))


# Sell Stock
@app.route('/sell_stock/<string:ticker>/<int:current_price>/<int:myvolume>', methods=['POST'])
@is_logged_in
def sell_stock(ticker, current_price, myvolume):


	volume = int(request.form['volume'])
	credit = volume*current_price

	if(volume<=myvolume):
		# Create cursor
		cur = mysql.connection.cursor()

		# Update user cash
		cur.execute("UPDATE users SET cash=cash+%s WHERE username=%s", (credit, session['username']))

		session['cash'] = session['cash']+credit

		# Update stock volume
		cur.execute("UPDATE stocks SET avail_volume=avail_volume+%s WHERE ticker=%s", (volume, ticker))

		# Add transaction log
		cur.execute("INSERT INTO transactions(ticker, volume, type, current_price, id) VALUES(%s, %s, %s, %s, %s)", (ticker, -volume, 'Sell', current_price, session['id']))

		# Commit to DB
		mysql.connection.commit()

		# Close connection
		cur.close()

		flash(str(volume)+' '+ticker+' stocks Sold!', 'success')
	else:
		flash('You do not have enough, '+ticker+' stocks to sell', 'danger')


	return redirect(url_for('myStocks'))
