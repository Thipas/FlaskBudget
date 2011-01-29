#!/usr/bin/python
# -*- coding: utf -*-

# framework
from flask import Module, session, render_template, redirect, request, flash
from flask.helpers import url_for
from flaskext.sqlalchemy import Pagination

# presenters
from presenters.auth import login_required

# models
from db.database import db_session
from models.expenses import Expenses
from models.accounts import Accounts
from models.users import Users
from models.loans import Loans

# utils
from utils import *

expenses = Module(__name__)

''' Expenses '''
@expenses.route('/expenses/')
@expenses.route('/expenses/for/<date>')
@expenses.route('/expenses/in/<category>')
@expenses.route('/expenses/page/<int:page>')
@expenses.route('/expenses/for/<date>/in/<category>')
@expenses.route('/expenses/for/<date>/page/<int:page>')
@expenses.route('/expenses/in/<category>/page/<int:page>')
@expenses.route('/expenses/for/<date>/in/<category>/page/<int:page>')
@login_required
def index(date=None, category=None, page=1, items_per_page=10):
    current_user_id = session.get('logged_in_user')

    exp = Expenses(current_user_id)

    # fetch entries
    entries = exp.get_entries()

    # categories
    categories = exp.get_categories()
    # provided category?
    if category:
        # search for the slug
        category_id = exp.is_category(slug=category)
        if category_id:
            entries = exp.get_entries(category_id=category_id)

    # provided a date range?
    date_range = translate_date_range(date)
    if date_range:
        entries = exp.get_entries(date_from=date_range['low'], date_to=date_range['high'])
    # date ranges for the template
    date_ranges = get_date_ranges()

    # build a paginator
    paginator = Pagination(entries, page, items_per_page, entries.count(),
                               entries.offset((page - 1) * items_per_page).limit(items_per_page))

    return render_template('admin_show_expenses.html', **locals())

@expenses.route('/expense/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    error = None
    current_user_id = session.get('logged_in_user')

    acc_us = Accounts(current_user_id)
    exp_us = Expenses(current_user_id)
    usr = Users(current_user_id)

    if request.method == 'POST':
        # fetch values and check they are actually provided
        if 'amount' in request.form: amount = request.form['amount']
        else: error = 'You need to provide an amount'
        if 'date' in request.form: date = request.form['date']
        else: error = 'Not a valid date'
        if 'deduct_from' in request.form: account_id = request.form['deduct_from']
        else: error = 'You need to provide an account'
        if 'description' in request.form and request.form['description']: description = request.form['description']
        else: error = 'You need to provide a description'
        if 'category' in request.form: category_id = request.form['category']
        else: error = 'You need to provide a category'

        # 'heavier' checks
        if not error:
            # valid amount?
            if is_float(amount):
                # valid date?
                if is_date(date):
                    # valid account?
                    if acc_us.is_account(account_id=account_id):
                        # valid category?
                        if exp_us.is_category(id=category_id):

                            # is it a shared expense?
                            if 'is_shared' in request.form:
                                # fetch values and check they are actually provided
                                if 'split' in request.form: split = request.form['split']
                                else: error = 'You need to provide a % split'
                                if 'user' in request.form: shared_with_user = request.form['user']
                                else: error = 'You need to provide a user'

                                # 'heavier' checks
                                if not error:
                                    # valid percentage split?
                                    if is_percentage(split):
                                        # valid user sharing with?
                                        if usr.is_connection(user_id=shared_with_user):

                                            # figure out percentage split
                                            loaned_amount = (float(amount)*(100-float(split)))/100

                                            # create a loan
                                            loa = Loans(current_user_id)
                                            loan_id = loa.add_loan(other_user_id=shared_with_user, date=date,
                                                         account_id=account_id, description=description,
                                                         amount=loaned_amount)
                                            flash('Loan given')

                                            # add new expense (loaner)
                                            expense_id_us = exp_us.add_expense(date=date, category_id=category_id,
                                                                               account_id=account_id,
                                                                               amount=float(amount) - loaned_amount,
                                                                               description=description)

                                            # add new expenses (borrower)
                                            exp_them = Expenses(shared_with_user)
                                            expense_id_them = exp_them.add_expense(date=date, amount=loaned_amount,
                                                                                   description=description)

                                            # fudge loan 'account' monies
                                            acc_us.modify_loan_balance(amount=loaned_amount, with_user_id=shared_with_user)
                                            acc_them = Accounts(shared_with_user)
                                            acc_them.modify_loan_balance(amount=-float(loaned_amount),
                                                                         with_user_id=current_user_id)

                                            # link loan and the expenses (through us)
                                            exp_us.link_to_loan(expense_id=expense_id_us, loan_id=loan_id,
                                                                shared_with=shared_with_user, percentage=split)
                                            exp_us.link_to_loan(expense_id=expense_id_them, loan_id=loan_id,
                                                                shared_with=current_user_id, percentage=split)

                                        else: error = 'Not a valid user sharing with'
                                    else: error = 'Not a valid % split'

                            else:
                                # add new expense
                                exp_us.add_expense(date=date, category_id=category_id, account_id=account_id,
                                                   amount=amount, description=description)

                            if not error:
                                # debit from account
                                acc_us.modify_user_balance(amount=-float(amount), account_id=account_id)
                                
                                flash('Expense added')

                        else: error = 'Not a valid category'
                    else: error = 'Not a valid account'
                else: error = 'Not a valid date'
            else: error = 'Not a valid amount'

    # fetch user's categories, accounts and users
    categories = exp_us.get_categories()
    if not categories: error = 'You need to define at least one category'

    accounts = acc_us.get_accounts()
    if not accounts: error = 'You need to define at least one account'

    # fetch users from connections from us
    users = usr.get_connections()

    return render_template('admin_add_expense.html', **locals())

@expenses.route('/expense/edit/<expense_id>', methods=['GET', 'POST'])
@login_required
def edit_expense(expense_id):
    current_user_id = session.get('logged_in_user')

    exp_us = Expenses(current_user_id)

    # is it valid?
    expense = exp_us.get_expense(expense_id)
    if expense:
        error = None

        acc_us = Accounts(current_user_id)
        usr = Users(current_user_id)

        # fetch user's categories, accounts and users
        categories = exp_us.get_categories()
        if not categories: error = 'You need to define at least one category'

        accounts = acc_us.get_accounts()
        if not accounts: error = 'You need to define at least one account'

        # fetch users from connections from us
        users = usr.get_connections()

        # fudge the total for the expense if we have a shared expense
        if expense[1]:
            expense[0].amount = float(expense[0].amount) * (100/float(expense[3]))

        if request.method == 'POST':
            # fetch values and check they are actually provided
            if 'amount' in request.form: amount = request.form['amount']
            else: error = 'You need to provide an amount'
            if 'date' in request.form: date = request.form['date']
            else: error = 'Not a valid date'
            if 'deduct_from' in request.form: account_id = request.form['deduct_from']
            else: error = 'You need to provide an account'
            if 'description' in request.form and request.form['description']: description = request.form['description']
            else: error = 'You need to provide a description'
            if 'category' in request.form: category_id = request.form['category']
            else: error = 'You need to provide a category'

            # 'heavier' checks
            if not error:
                # valid amount?
                if is_float(amount):
                    # valid date?
                    if is_date(date):
                        # valid account?
                        if acc_us.is_account(account_id=account_id):
                            # valid category?
                            if exp_us.is_category(id=category_id):

                                # is it shared NOW?
                                if 'is_shared' in request.form: is_shared = True
                                # WAS it a shared expense?
                                if expense[1]:
                                    return __edit_shared_expense(**locals())
                                else:
                                    return __edit_simple_expense(**locals())

                            else: error = 'Not a valid category'
                        else: error = 'Not a valid account'
                    else: error = 'Not a valid date'
                else: error = 'Not a valid amount'

        # show the form
        return render_template('admin_edit_expense.html', **locals())

    else: return redirect(url_for('expenses.index'))

def __edit_simple_expense(current_user_id, exp_us, expense, acc_us, usr, date, description, account_id, amount, error,
                          category_id, categories, accounts, users, expense_id, is_shared=None):
    # is it a shared expense?
    if is_shared:
        # fetch values and check they are actually provided
        if 'split' in request.form: split = request.form['split']
        else: error = 'You need to provide a % split'
        if 'user' in request.form: shared_with_user = request.form['user']
        else: error = 'You need to provide a user'

        # 'heavier' checks
        if not error:
            # valid percentage split?
            if is_percentage(split):
                # valid user sharing with?
                if usr.is_connection(user_id=shared_with_user):

                    # figure out percentage split
                    loaned_amount = (float(amount)*(100-float(split)))/100

                    # create a loan
                    loa = Loans(current_user_id)
                    loan_id = loa.add_loan(other_user_id=shared_with_user, date=date, account_id=account_id,
                                           description=description, amount=loaned_amount)
                    flash('Loan given')

                    # credit our account back
                    acc_us.modify_user_balance(amount=expense[0].amount, account_id=expense[0].deduct_from)

                    # debit from account
                    acc_us.modify_user_balance(amount=-float(amount), account_id=account_id)

                    # edit expense (loaner - us)
                    exp_us.edit_expense(date=date, category_id=category_id, account_id=account_id,
                                                       amount=float(amount) - loaned_amount, description=description,
                                                       expense_id=expense_id)

                    # for non private users...
                    if not usr.is_private(shared_with_user):
                        exp_them = Expenses(shared_with_user)
                        acc_them = Accounts(shared_with_user)

                        # add new expenses (borrower)
                        expense_id_them = exp_them.add_expense(date=date, amount=loaned_amount, description=description)

                        # fudge loan 'account' monies
                        acc_them.modify_loan_balance(amount=-float(loaned_amount), with_user_id=current_user_id)


                    # fudge loan 'account' monies
                    acc_us.modify_loan_balance(amount=loaned_amount, with_user_id=shared_with_user)

                    # link loan and the expenses (through us)
                    exp_us.link_to_loan(expense_id=expense_id, loan_id=loan_id, shared_with=shared_with_user,
                                        percentage=split)

                    flash('Expense edited')

                    # for the view...
                    expense = exp_us.get_expense(expense_id=expense_id)
                    # fudge the total for the expense if we have a shared expense
                    if expense[1]:
                        expense[0].amount = float(expense[0].amount) * (100/float(expense[3]))

                else: error = 'Not a valid user sharing with'
            else: error = 'Not a valid % split'

    else:
        # credit our account back
        acc_us.modify_user_balance(amount=expense[0].amount, account_id=expense[0].deduct_from)

        # debit from account
        acc_us.modify_user_balance(amount=-float(amount), account_id=account_id)

        # edit expense
        exp_us.edit_expense(date=date, category_id=category_id, account_id=account_id, amount=amount,
                            description=description, expense_id=expense_id)

        flash('Expense edited')

    # show the form
    return render_template('admin_edit_expense.html', **locals())

def __edit_shared_expense(current_user_id, exp_us, expense, acc_us, usr, date, description, account_id, amount, error,
                          category_id, categories, accounts, users, expense_id, is_shared=None):
    # is it a shared expense?
    if is_shared:
        # fetch values and check they are actually provided
        if 'split' in request.form: split = request.form['split']
        else: error = 'You need to provide a % split'
        if 'user' in request.form: shared_with_user = request.form['user']
        else: error = 'You need to provide a user'

        # 'heavier' checks
        if not error:
            # valid percentage split?
            if is_percentage(split):
                # valid user sharing with?
                if usr.is_connection(user_id=shared_with_user):

                    # figure out percentage split
                    loaned_amount = (float(amount) * (100-float(split)))/100
                    loaned_then_amount = (float(expense[0].amount) * (100-float(expense[3])))/100

                    loa = Loans(current_user_id)
                    # are we sharing the expense with the same user as before?
                    if expense[2] == int(shared_with_user):

                        if not usr.is_private(user_id=shared_with_user): # only modify non private accounts
                            # TODO untested
                            exp_them = Expenses(shared_with_user)
                            acc_them = Accounts(shared_with_user)

                            # the user now and then is the same
                            expense_them = exp_them.get_expense(loan_id=expense[1])

                            # edit the loan
                            loa.edit_loan(other_user_id=shared_with_user, account_id=account_id, description=description,
                                          amount=loaned_amount, date=date, loan_id=expense[1])

                            # fudge loan 'account' monies
                            acc_us.modify_loan_balance(amount=-loaned_amount - loaned_then_amount,
                                                       with_user_id=shared_with_user)

                            # credit our account back
                            acc_us.modify_user_balance(amount=expense[0].amount, account_id=expense[0].deduct_from)

                            # debit from account
                            acc_us.modify_user_balance(amount=-float(amount), account_id=account_id)

                            # modify their loan and account status
                            acc_them.modify_loan_balance(amount=loaned_then_amount - loaned_amount,
                                                         with_user_id=current_user_id)

                            # edit their expense amount
                            exp_them.edit_expense(date=date, category_id=category_id, account_id=account_id,
                                                  amount=float(amount) - loaned_amount, description=description,
                                                  expense_id=expense_them[0].id)

                            exp_us.modify_loan_link_percentage(loan_id=expense[1], percentage=split)

                        else:
                            # edit the loan
                            loa.edit_loan(other_user_id=shared_with_user, account_id=account_id, description=description,
                                          amount=loaned_amount, date=date, loan_id=expense[1])

                            # fudge loan 'account' monies
                            acc_us.modify_loan_balance(amount=loaned_amount - loaned_then_amount,
                                                       with_user_id=shared_with_user)

                            # credit our account back
                            acc_us.modify_user_balance(amount=expense[0].amount, account_id=expense[0].deduct_from)

                            # debit from account
                            acc_us.modify_user_balance(amount=-float(amount), account_id=account_id)

                            exp_us.modify_loan_link_percentage(loan_id=expense[1], percentage=split)
                            
                    else:
                        if not usr.is_private(user_id=shared_with_user): # only modify non private accounts
                            # TODO untested
                            exp_them = Expenses(shared_with_user)
                            acc_them = Accounts(shared_with_user)

                            # the user now and then is the same
                            expense_them = exp_them.get_expense(loan_id=expense[1])

                            # edit the loan
                            loa.edit_loan(other_user_id=shared_with_user, account_id=account_id, description=description,
                                          amount=loaned_amount, date=date, loan_id=expense[1])

                            # fudge loan 'account' monies
                            acc_us.modify_loan_balance(amount=-loaned_amount - loaned_then_amount,
                                                       with_user_id=shared_with_user)

                            # credit our account back
                            acc_us.modify_user_balance(amount=expense[0].amount, account_id=expense[0].deduct_from)

                            # debit from account
                            acc_us.modify_user_balance(amount=-float(amount), account_id=account_id)

                            # modify their loan and account status
                            acc_them.modify_loan_balance(amount=loaned_then_amount - loaned_amount,
                                                         with_user_id=current_user_id)

                            # edit their expense amount
                            exp_them.edit_expense(date=date, category_id=category_id, account_id=account_id,
                                                  amount=float(amount) - loaned_amount, description=description,
                                                  expense_id=expense_them[0].id)

                            exp_us.modify_loan_link_percentage(loan_id=expense[1], percentage=split)

                        else:
                            # create a new loan
                            loan_id = loa.add_loan(other_user_id=shared_with_user, date=date, account_id=account_id,
                                           description=description, amount=loaned_amount)

                            # credit loan back
                            acc_us.modify_loan_balance(amount=-loaned_then_amount, with_user_id=expense[2])

                            # debit new loan
                            acc_us.modify_loan_balance(amount=loaned_amount, with_user_id=shared_with_user)

                            # credit our account back
                            acc_us.modify_user_balance(amount=expense[0].amount, account_id=expense[0].deduct_from)

                            # debit from account
                            acc_us.modify_user_balance(amount=-float(amount), account_id=account_id)

                            # remove the original loan - expense link
                            exp_us.unlink_loan(loan_id=expense[1])

                            # create new loan - expense link
                            exp_us.link_to_loan(expense_id=expense_id, loan_id=loan_id, shared_with=shared_with_user,
                                        percentage=split)

                            # remove original loan
                            loa.delete_loan(expense[1])

                    # edit expense (loaner - us)
                    exp_us.edit_expense(date=date, category_id=category_id, account_id=account_id,
                                                       amount=float(amount) - loaned_amount, description=description,
                                                       expense_id=expense_id)

                    # fudge the total for the expense if we have a shared expense after POST
                    expense = exp_us.get_expense(expense_id)
                    if expense[1]: expense[0].amount = float(expense[0].amount) * (100/float(expense[3]))

                    flash('Expense edited')

                else: error = 'Not a valid user sharing with'
            else: error = 'Not a valid % split'

    else: # shared expense that is no longer shared
        loa = Loans(current_user_id)

        # credit our loan account
        acc_us.modify_loan_balance(amount=-float(expense[0].amount) * ((100 - expense[3])/100), with_user_id=expense[2])

        if not usr.is_private(user_id=expense[2]): # only modify non private accounts
            exp_them = Expenses(expense[2])
            acc_them = Accounts(expense[2])

            # fetch their expense
            expense_them = exp_them.get_expense(loan_id=expense[1])

            # delete the shared user's expense
            exp_them.delete_expense(expense_id=expense_them[0].id)

            # delete their loan status towards us
            acc_them.modify_loan_balance(amount=float(expense[0].amount) * ((100 - float(expense[3]))/100),
                                         with_user_id=current_user_id)

        # unlink expenses to loan entries
        exp_us.unlink_loan(loan_id=expense[1])

        # delete the original loan
        loa.delete_loan(loan_id=expense[1])

        flash('Loan reverted')
        # credit our account back with the full amount (expense amount + loaned amount)
        acc_us.modify_user_balance(amount=float(expense[0].amount), account_id=expense[0].deduct_from)

        # debit from account
        acc_us.modify_user_balance(amount=-float(amount), account_id=account_id)

        # edit expense
        exp_us.edit_expense(date=date, category_id=category_id, account_id=account_id, amount=amount,
                            description=description, expense_id=expense_id)

        expense = exp_us.get_expense(expense_id=expense_id)

        flash('Expense edited')

    # show the form
    return render_template('admin_edit_expense.html', **locals())

@expenses.route('/expense/category/add', methods=['GET', 'POST'])
@login_required
def add_category():
    error = None
    if request.method == 'POST':
        new_category_name, current_user_id = request.form['name'], session.get('logged_in_user')

        exp = Expenses(current_user_id)

        # blank name?
        if new_category_name:
            # already exists?
            if not exp.is_category(name=new_category_name):

                # create category
                exp.add_category(new_category_name)
                flash('Expense category added')

            else: error = 'You already have a category under that name'
        else: error = 'You need to provide a name'

    return render_template('admin_add_expense_category.html', error=error)