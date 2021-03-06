#!/usr/bin/python
# -*- coding: utf -*-

# orm
from sqlalchemy import Column, ForeignKey, Integer, String, Float
from sqlalchemy.sql.expression import and_, asc

# db
from db.database import db_session
from db.database import Base

# utils
from datetime import datetime, date

class Totals():
    '''Totals for a given user'''

    user = None

    def __init__(self, user):
        self.user = user

    def get_totals(self, wayback=5):
        # generate today's month/year string
        m = MonthYear("today")

        # generate a list of month/year strings
        l = [m.substract(x) for x in range(wayback)]

        # pass it as an IS IN query to totals and return
        return TotalsTable.query\
        .filter(and_(TotalsTable.user == self.user, TotalsTable.month.in_(l)))\
        .order_by(asc(TotalsTable.id)).all()

    def update_expense(self, amount, date):
        # generate a month/year string
        m = MonthYear(date)

        # get the corresponding entry
        t = TotalsTable.query\
        .filter(and_(TotalsTable.user == self.user, TotalsTable.month == str(m))).first()

        if not t:
            # brand spanking new
            t = TotalsTable(self.user, str(m), amount, 0)
        else:
            # update the total
            t.expenses += float(amount)

        # save
        db_session.add(t)
        db_session.commit()

    def update_income(self, amount, date):
        # generate a month/year string
        m = MonthYear(date)

        # get the corresponding entry
        t = TotalsTable.query\
        .filter(and_(TotalsTable.user == self.user, TotalsTable.month == str(m))).first()

        if not t:
            # brand spanking new
            t = TotalsTable(self.user, str(m), 0, amount)
        else:
            # update the total
            t.income += float(amount)

        # save
        db_session.add(t)
        db_session.commit()

class MonthYear():
    '''Represents a wrapper around month/year string'''

    date = None

    def __init__(self, date):
        # setup as a custom month from an entry date string or generate one from today's date
        if date == "today":
            self.date = datetime.now().strftime("%Y-%m")
        else:
            dt = datetime.strptime(date, "%Y-%m-%d")
            self.date = dt.strftime("%Y-%m")

    def __repr__(self):
        # return a string representation of the month
        return self.date

    def substract(self, months):
        # perform arithmetic on a date, -1 will get a correct previous month etc.
        month = int(self.date[-2:]) - months
        year = int(self.date[:4])
        if (month < 1):
            # end of year
            month += 12
            year -= 1

        # convert back, return
        return date(year, month, 1).strftime("%Y-%m")

class TotalsTable(Base):
    """Monthly expense/income totals for a user"""

    __tablename__ = 'totals'
    id = Column(Integer, primary_key=True)
    user = Column('user_id', Integer, ForeignKey('users.id'))
    month = Column(String(10))
    expenses = Column(Float(precision=2))
    income = Column(Float(precision=2))

    def __init__(self, user=None, month=None, expenses=None, income=None):
        self.user = user
        self.month = month
        self.expenses = expenses
        self.income = income