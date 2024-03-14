from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, UUID, String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    UUID = Column(UUID(as_uuid=True), default=uuid4, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    about_me = Column(String, nullable=True)
    likes = Column(Integer, default=0)
    role = Column(String, default='user')

    posts = relationship('Post', back_populates='owner')


class Post(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True, index=True)
    owner_UUID = Column(UUID(as_uuid=True), ForeignKey('users.UUID'))
    owner_username = Column(String, nullable=False)
    title = Column(String, unique=True, nullable=False)
    content = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    likes = Column(Integer, default=0)

    owner = relationship('User', back_populates='posts')
    like = relationship('Like', back_populates='post')


class Like(Base):
    __tablename__ = 'likes'

    id = Column(Integer, primary_key=True, index=True)
    user_UUID = Column(UUID(as_uuid=True), ForeignKey('users.UUID'))
    post_id = Column(Integer, ForeignKey('posts.id'))

    user = relationship('User')
    post = relationship('Post', back_populates='like')
