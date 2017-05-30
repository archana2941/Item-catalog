# object-relational mapping
# using SQLAlchemy to create database

import sys

# this will help in our mapper code
from sqlalchemy import Column, ForeignKey, Integer, String

# this willbe used  in our configuration and class code
from sqlalchemy.ext.declarative import declarative_base

# to create foreign key relationships(Mapper code)
from sqlalchemy.orm import relationship

# used in configuration code at end of our file
from sqlalchemy import create_engine




Base = declarative_base()


# User Entity with id,picture,name, email attributes
class User(Base):

    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    picture = Column(String(250))
    name = Column(String(250), nullable=False)
    email = Column(String(250), nullable=False)
    

# Restaurant Entity with id,name, user_id,user attributes
class Restaurant(Base):

	#__tablename__ is having name of  table
    __tablename__ = 'restaurant'

    # Mapper code
    #(nullable =False means that column entry cannot be null)
    name = Column(String(250), nullable=False)
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User,cascade="delete")

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'name': self.name,
            'id': self.id,
        }


# MenuItem Entity with id,name,price course and many more attributes
class MenuItem(Base):
    __tablename__ = 'menu_item'

    # id is the primary key for menu_item table
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    price = Column(String(8))
    description = Column(String(250))
    course = Column(String(250))
    restaurant_id = Column(Integer, ForeignKey('restaurant.id'))
    restaurant = relationship(Restaurant,cascade="delete")
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User,cascade="delete")

    @property
    def serialize(self):
        """Return object data in easily serializeable format"""
        return {
            'name': self.name,
            'description': self.description,
            'id': self.id,
            'price': self.price,
            'course': self.course,
        }


# create_engine points to the database we will use
engine = create_engine('postgresql://catalog:sillypassword@localhost/catalog')


Base.metadata.create_all(engine)
