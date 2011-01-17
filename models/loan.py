# orm
from sqlalchemy import Column, ForeignKey, Integer, Float, String

# db
from db.database import Base

# utils
from utils import *

class LoansTable(Base):
    """A loan from one user to another"""

    __tablename__ = 'loans'
    id = Column(Integer, primary_key=True)
    from_user = Column('from_user_id', Integer, ForeignKey('users.id'))
    to_user = Column('to_user_id', Integer, ForeignKey('users.id'))
    date = Column(Integer)
    account = Column('account_id', Integer, ForeignKey('accounts.id'))
    description = Column(String(50))
    amount = Column(Float(precision=2))

    def __init__(self, from_user=None, to_user=None, date=None, account=None, description=None, amount=None):
        self.from_user = from_user
        self.to_user = to_user
        self.date = date
        self.account = account
        self.description = description
        self.amount = amount