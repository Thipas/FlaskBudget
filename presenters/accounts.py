# framework
from flask import Module, session, render_template, redirect, request, flash, url_for
from flaskext.sqlalchemy import Pagination

# presenters
from presenters.auth import login_required

# models
from models.accounts import Accounts

# utils
from utils import *

accounts = Module(__name__)

''' Accounts '''
@accounts.route('/account-transfers/')
@accounts.route('/account-transfers/page/<int:page>')
@accounts.route('/account-transfers/for/<date>')
@accounts.route('/account-transfers/for/<date>/page/<int:page>')
@accounts.route('/account-transfers/with/<account>')
@accounts.route('/account-transfers/with/<account>/page/<int:page>')
@accounts.route('/account-transfers/with/<account>/for/<date>')
@accounts.route('/account-transfers/with/<account>/for/<date>/page/<int:page>')
@login_required
def show_transfers(account=None, date=None, page=1, items_per_page=10):
    current_user_id = session.get('logged_in_user')

    acc = Accounts(current_user_id)

    # fetch account transfers
    transfers = acc.get_account_transfers()

    # provided a date range?
    date_range = translate_date_range(date)
    if date_range:
        transfers = acc.get_account_transfers(date_from=date_range['low'], date_to=date_range['high'])
    # date ranges for the template
    date_ranges = get_date_ranges()

    # fetch accounts
    accounts = acc.get_accounts()

    # provided an account?
    if account:
        # valid slug?
        if acc.is_account(account_slug=account):
            transfers = acc.get_account_transfers(account_slug=account)

    # build a paginator
    paginator = Pagination(transfers, page, items_per_page, transfers.count(),
                           transfers.offset((page - 1) * items_per_page).limit(items_per_page))

    return render_template('admin_show_transfers.html', **locals())

@accounts.route('/account/add', methods=['GET', 'POST'])
@login_required
def add_account():
    error = None
    if request.method == 'POST':
        new_account_name, account_type, account_balance, current_user_id =\
        request.form['name'], request.form['type'], request.form['balance'], session.get('logged_in_user')

        # blank name?
        if new_account_name:
            # type?
            if account_type == 'asset' or account_type == 'liability':\
                # if balance blank, pass in 0
                if not account_balance: account_balance = 0
                # is balance a valid float?
                if is_float(account_balance):

                    acc = Accounts(current_user_id)
                    # already exists?
                    if not acc.is_account(account_slug=new_account_name):

                        # create new account
                        acc.add_account(name=new_account_name, type=account_type, balance=account_balance)

                        flash('Account added')

                    else: error = 'You already have an account under that name'
                else: error = 'The initial balance needs to be a floating number'
            else: error = 'The account needs to either be an asset or a liability'
        else: error = 'You need to provide a name for the account'

    return render_template('admin_add_account.html', **locals())

@accounts.route('/account/transfer', methods=['GET', 'POST'])
@login_required
def add_transfer():
    error = None
    current_user_id = session.get('logged_in_user')

    acc = Accounts(current_user_id)

    if request.method == 'POST':
        # fetch values and check they are actually provided
        if 'date' in request.form: date = request.form['date']
        else: error = 'You need to provide a date'
        if 'amount' in request.form: amount = request.form['amount']
        else: error = 'You need to provide an amount'
        if 'deduct_from' in request.form: deduct_from_account = request.form['deduct_from']
        else: error = 'You need to provide an account to deduct from'
        if 'credit_to' in request.form: credit_to_account = request.form['credit_to']
        else: error = 'You need to provide an account to credit to'

        # 'heavier' checks
        if not error:
            # source and target the same?
            if not deduct_from_account == credit_to_account:
                # valid amount?
                if is_float(amount):
                    # valid date?
                    if is_date(date):
                        # valid debit account?
                        if acc.is_account(account_id=deduct_from_account):
                            # valid credit account?
                            if acc.is_account(account_id=credit_to_account):

                                # add a new transfer row
                                acc.add_account_transfer(date=date, deduct_from_account=deduct_from_account,
                                                         credit_to_account=credit_to_account, amount=amount)

                                # modify accounts
                                acc.modify_account_balance(deduct_from_account, -float(amount))
                                acc.modify_account_balance(credit_to_account, amount)

                                flash('Monies transferred')

                            else: error = 'Not a valid target account'
                        else: error = 'Not a valid source account'
                    else: error = 'Not a valid date'
                else: error = 'Not a valid amount'
            else: error = 'Source and target accounts cannot be the same'

    accounts = acc.get_accounts()

    return render_template('admin_add_transfer.html', **locals())

@accounts.route('/account/transfer/edit/<transfer_id>', methods=['GET', 'POST'])
@login_required
def edit_transfer(transfer_id):
    current_user_id = session.get('logged_in_user')

    acc = Accounts(current_user_id)
    accounts = acc.get_accounts()

    # is it valid?
    transfer = acc.get_transfer(transfer_id)
    if transfer:

        if request.method == 'POST': # POST
            error = None
            
            # fetch values and check they are actually provided
            if 'date' in request.form: date = request.form['date']
            else: error = 'You need to provide a date'
            if 'amount' in request.form: amount = request.form['amount']
            else: error = 'You need to provide an amount'
            if 'deduct_from' in request.form: deduct_from_account = request.form['deduct_from']
            else: error = 'You need to provide an account to deduct from'
            if 'credit_to' in request.form: credit_to_account = request.form['credit_to']
            else: error = 'You need to provide an account to credit to'

            # 'heavier' checks
            if not error:
                # source and target the same?
                if not deduct_from_account == credit_to_account:
                    # valid amount?
                    if is_float(amount):
                        # valid date?
                        if is_date(date):
                            # valid debit account?
                            if acc.is_account(account_id=deduct_from_account):
                                # valid credit account?
                                if acc.is_account(account_id=credit_to_account):

                                    # modify accounts to original state
                                    acc.modify_account_balance(transfer.from_account, transfer.amount)
                                    acc.modify_account_balance(transfer.to_account, -float(transfer.amount))

                                    # new state
                                    acc.modify_account_balance(deduct_from_account, -float(amount))
                                    acc.modify_account_balance(credit_to_account, amount)

                                    # edit transfer row
                                    transfer = acc.edit_account_transfer(date=date, deduct_from_account=deduct_from_account,
                                                             credit_to_account=credit_to_account, amount=amount,
                                                             transfer_id=transfer_id)

                                    flash('Transfer edited')

                                else: error = 'Not a valid target account'
                            else: error = 'Not a valid source account'
                        else: error = 'Not a valid date'
                    else: error = 'Not a valid amount'
                else: error = 'Source and target accounts cannot be the same'

        return render_template('admin_edit_transfer.html', **locals())

    else: return redirect(url_for('accounts.show_transfers'))